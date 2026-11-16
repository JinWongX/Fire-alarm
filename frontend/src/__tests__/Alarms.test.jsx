import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, within, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { message, Modal } from 'antd'

const mocks = vi.hoisted(() => ({
  fetchAlarms: vi.fn(),
  confirmAlarm: vi.fn(),
}))

vi.mock('../api', () => mocks)

import Alarms from '../pages/Alarms'

const pendingAlarm = {
  id: 1,
  device_id: 1,
  fire_type: 'electrical',
  trigger_at: '2024-01-01T08:00:00Z',
  status: 'pending',
  scene: '走廊烟雾',
  false_reason: null,
  device: { name: '烟感A', area: { name: '一层' } },
}

function renderPage() {
  return render(
    <MemoryRouter>
      <Alarms />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mocks.fetchAlarms.mockReset().mockResolvedValue({ total: 1, items: [pendingAlarm] })
  mocks.confirmAlarm.mockReset().mockResolvedValue({})
  vi.spyOn(message, 'success').mockImplementation(() => {})
  vi.spyOn(message, 'error').mockImplementation(() => {})
})

describe('Alarms', () => {
  it('渲染待确认报警并显示操作按钮', async () => {
    renderPage()
    expect(await screen.findByText('烟感A')).toBeInTheDocument()
    expect(screen.getByText('电气火灾')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '确认真实' })).toBeInTheDocument()
    expect(document.querySelector('.ant-btn-dangerous')).toBeTruthy()
  })

  it('误报未填写原因时不调用 confirmAlarm 并提示必填', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('烟感A')
    await waitFor(() => expect(document.querySelector('.ant-spin-blur')).toBeNull())

    await user.click(document.querySelector('.ant-btn-dangerous'))
    const dialog = await screen.findByRole('dialog')
    // onConfirm 中 validateFields() 为异步 Promise，其 reject 触发的错误渲染更新
    // 会逃逸 act（rc-field-form Field），用 act 包裹提交点击确保文案稳定渲染
    await act(async () => {
      await user.click(within(dialog).getByRole('button', { name: '确认为误报' }))
    })

    expect(await within(dialog).findByText('请填写误报原因')).toBeInTheDocument()
    expect(mocks.confirmAlarm).not.toHaveBeenCalled()
  })

  it('填写误报原因后调用 confirmAlarm(result=false)', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('烟感A')
    await waitFor(() => expect(document.querySelector('.ant-spin-blur')).toBeNull())

    await user.click(document.querySelector('.ant-btn-dangerous'))
    const dialog = await screen.findByRole('dialog')
    await user.type(
      within(dialog).getByPlaceholderText('如：烹饪油烟、设备误触发等'),
      '烹饪油烟',
    )
    await user.click(within(dialog).getByRole('button', { name: '确认为误报' }))

    await waitFor(() =>
      expect(mocks.confirmAlarm).toHaveBeenCalledWith(1, {
        result: 'false',
        false_reason: '烹饪油烟',
      }),
    )
  })

  it('填写现场描述后调用 confirmAlarm(result=true)', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('烟感A')
    await waitFor(() => expect(document.querySelector('.ant-spin-blur')).toBeNull())

    await user.click(screen.getByRole('button', { name: '确认真实' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(
      within(dialog).getByPlaceholderText('描述现场情况、火势及对应扑救措施'),
      '发现明火',
    )
    await user.click(within(dialog).getByRole('button', { name: '确认真实' }))

    await waitFor(() =>
      expect(mocks.confirmAlarm).toHaveBeenCalledWith(1, { result: 'true', scene: '发现明火' }),
    )
  })

  it('已确认报警显示确认文案而非操作按钮', async () => {
    mocks.fetchAlarms.mockResolvedValue({
      total: 1,
      items: [{ ...pendingAlarm, id: 2, status: 'confirmed_real', confirm_by: '张三' }],
    })
    renderPage()
    expect(await screen.findByText(/已确认（张三）/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '确认真实' })).toBeNull()
  })

  it('确认真实后若自动创建处置单则弹出引导', async () => {
    const user = userEvent.setup()
    mocks.confirmAlarm.mockResolvedValue({ emergency: { id: 9, title: '处置单A' } })
    const modalSpy = vi.spyOn(Modal, 'confirm').mockImplementation(() => {})
    try {
      renderPage()
      await screen.findByText('烟感A')
      await waitFor(() => expect(document.querySelector('.ant-spin-blur')).toBeNull())
      await user.click(screen.getByRole('button', { name: '确认真实' }))
      const dialog = await screen.findByRole('dialog')
      await user.type(
        within(dialog).getByPlaceholderText('描述现场情况、火势及对应扑救措施'),
        '发现明火',
      )
      await user.click(within(dialog).getByRole('button', { name: '确认真实' }))
      await waitFor(() =>
        expect(mocks.confirmAlarm).toHaveBeenCalledWith(1, { result: 'true', scene: '发现明火' }),
      )
      expect(modalSpy).toHaveBeenCalled()
    } finally {
      modalSpy.mockRestore()
    }
  })
})