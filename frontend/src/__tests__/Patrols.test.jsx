import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, within, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { message } from 'antd'

const mocks = vi.hoisted(() => ({
  fetchPatrols: vi.fn(),
  fetchPatrolSummary: vi.fn(),
  createPatrol: vi.fn(),
  submitPatrolResult: vi.fn(),
  fetchDevices: vi.fn(),
  fetchAreas: vi.fn(),
}))

vi.mock('../api', () => mocks)

import Patrols from '../pages/Patrols'

const overdueItem = {
  id: 1,
  device_id: 1,
  area_id: 10,
  scheduled_date: '2024-01-01',
  status: 'pending',
  overdue: true,
}
const normalItem = {
  id: 2,
  device_id: 2,
  area_id: 10,
  scheduled_date: '2024-01-02',
  status: 'normal',
  overdue: false,
  patrol_by: '张三',
}

beforeEach(() => {
  mocks.fetchPatrols.mockReset().mockResolvedValue([overdueItem, normalItem])
  mocks.fetchPatrolSummary.mockReset().mockResolvedValue({ total: 2, done: 1, abnormal: 0, done_rate: 50 })
  mocks.createPatrol.mockReset().mockResolvedValue({})
  mocks.submitPatrolResult.mockReset().mockResolvedValue({})
  mocks.fetchDevices.mockReset().mockResolvedValue({
    items: [
      { id: 1, name: '烟感A' },
      { id: 2, name: '温感B' },
    ],
  })
  mocks.fetchAreas.mockReset().mockResolvedValue([{ id: 10, name: '一层' }])
  vi.spyOn(message, 'success').mockImplementation(() => {})
  vi.spyOn(message, 'error').mockImplementation(() => {})
})

describe('Patrols 巡检', () => {
  it('列表对 overdue 行显示“逾期”标签', async () => {
    render(<Patrols />)
    await screen.findByText('烟感A', undefined, { timeout: 5000 })

    const overdueTag = await screen.findAllByText('逾期')
    expect(overdueTag.length).toBeGreaterThan(0)
  })

  it('异常结果未填说明与建议时校验拦截，不提交', async () => {
    const user = userEvent.setup()
    render(<Patrols />)
    await screen.findByText('烟感A', undefined, { timeout: 5000 })
    await waitFor(() => expect(document.querySelector('.ant-spin-blur')).toBeNull())

    const resultBtns = screen.getAllByRole('button', { name: /录入结果/ })
    await user.click(resultBtns[0])
    const dialog = await screen.findByRole('dialog')

    await user.click(within(dialog).getByText('异常'))
    await waitFor(() =>
      expect(within(dialog).getByRole('radio', { name: /异常/ })).toBeChecked(),
    )
    // onResult 中 validateFields() 为异步 Promise，其 reject 会触发 rc-field-form
    // Field 的错误渲染更新；用 act 包裹提交点击，确保这些更新在 act 内 flush，
    // 避免错误文案偶发渲染不及时（并发负载下逃逸 act 导致不显示）。
    await act(async () => {
      await user.click(within(dialog).getByRole('button', { name: /提交结果/ }))
    })

    expect(await within(dialog).findByText('异常时请填写异常说明')).toBeInTheDocument()
    expect(await within(dialog).findByText('异常时请填写整改建议')).toBeInTheDocument()
    expect(mocks.submitPatrolResult).not.toHaveBeenCalled()
  })

  it('异常时填写说明与建议后调用 submitPatrolResult', async () => {
    const user = userEvent.setup()
    render(<Patrols />)
    await screen.findByText('烟感A', undefined, { timeout: 5000 })
    await waitFor(() => expect(document.querySelector('.ant-spin-blur')).toBeNull())

    const resultBtns = screen.getAllByRole('button', { name: /录入结果/ })
    await user.click(resultBtns[0])
    const dialog = await screen.findByRole('dialog')

    await user.click(within(dialog).getByText('异常'))
    await waitFor(() =>
      expect(within(dialog).getByRole('radio', { name: /异常/ })).toBeChecked(),
    )
    await user.type(within(dialog).getByPlaceholderText('说明巡检情况'), '设备老化冒烟')
    await user.type(within(dialog).getByPlaceholderText('如有异常请填写整改建议'), '建议更换设备')
    await user.click(within(dialog).getByRole('button', { name: /提交结果/ }))

    await waitFor(() =>
      expect(mocks.submitPatrolResult).toHaveBeenCalledWith(1, {
        status: 'abnormal',
        result: '设备老化冒烟',
        suggest: '建议更换设备',
      }),
    )
  })
})
