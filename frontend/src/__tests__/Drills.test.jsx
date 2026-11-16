import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { message } from 'antd'

const mocks = vi.hoisted(() => ({
  fetchDrills: vi.fn(),
  createDrill: vi.fn(),
  updateDrill: vi.fn(),
  deleteDrill: vi.fn(),
  finishDrill: vi.fn(),
  fetchAreas: vi.fn(),
}))

vi.mock('../api', () => mocks)

import Drills from '../pages/Drills'

const planned = {
  id: 1,
  title: '逃生演练',
  drill_type: '疏散演练',
  area_id: 10,
  plan_date: '2026-09-01',
  duration: 30,
  status: 'planned',
  score: null,
  evaluate: '',
}
const done = {
  id: 2,
  title: '灭火演练',
  drill_type: '灭火演练',
  status: 'done',
  score: 90,
  evaluate: '良好',
}

beforeEach(() => {
  mocks.fetchDrills.mockReset().mockResolvedValue([planned, done])
  mocks.fetchAreas.mockReset().mockResolvedValue([{ id: 10, name: '一层' }])
  ;['createDrill', 'updateDrill', 'deleteDrill', 'finishDrill'].forEach((k) =>
    mocks[k].mockReset().mockResolvedValue({}),
  )
  vi.spyOn(message, 'success').mockImplementation(() => {})
  vi.spyOn(message, 'error').mockImplementation(() => {})
})

describe('Drills 消防演练', () => {
  it('渲染列表：待开展/已完成状态、评分与评估列', async () => {
    render(<Drills />)
    await screen.findByText('逃生演练')
    expect(screen.getAllByText('灭火演练').length).toBeGreaterThan(0)
    expect(screen.getByText('待开展')).toBeInTheDocument()
    expect(screen.getByText('已完成')).toBeInTheDocument()
    expect(screen.getByText('90')).toBeInTheDocument()
    expect(mocks.fetchDrills).toHaveBeenCalled()
    expect(mocks.fetchAreas).toHaveBeenCalled()
  })

  it('新增演练：填写标题后保存调用 createDrill', async () => {
    const user = userEvent.setup()
    render(<Drills />)
    await screen.findByText('逃生演练')
    await user.click(screen.getByRole('button', { name: /新增演练/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('标题'), '夜间演练')
    await user.click(dialog.querySelector('.ant-modal-footer .ant-btn-primary'))
    await waitFor(() =>
      expect(mocks.createDrill).toHaveBeenCalledWith(
        expect.objectContaining({ title: '夜间演练' }),
      ),
    )
  })

  it('编辑演练：回显并调用 updateDrill 而非 createDrill', async () => {
    const user = userEvent.setup()
    render(<Drills />)
    const title = await screen.findByText('逃生演练')
    const row = title.closest('tr')
    await user.click(within(row).getByRole('button', { name: 'edit' }))
    const dialog = await screen.findByRole('dialog')
    const titleInput = within(dialog).getByLabelText('标题')
    expect(titleInput.value).toBe('逃生演练')
    await user.click(dialog.querySelector('.ant-modal-footer .ant-btn-primary'))
    await waitFor(() =>
      expect(mocks.updateDrill).toHaveBeenCalledWith(1, expect.objectContaining({ title: '逃生演练' })),
    )
    expect(mocks.createDrill).not.toHaveBeenCalled()
  })

  it('完成演练：填写评分与评估后调用 finishDrill', async () => {
    const user = userEvent.setup()
    render(<Drills />)
    const title = await screen.findByText('逃生演练')
    await user.click(within(title.closest('tr')).getByRole('button', { name: /完成演练/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('评分（0-100）'), '95')
    await user.type(within(dialog).getByLabelText('评估'), '组织有序')
    await user.click(dialog.querySelector('.ant-modal-footer .ant-btn-primary'))
    await waitFor(() =>
      expect(mocks.finishDrill).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ score: 95, evaluate: '组织有序' }),
      ),
    )
  })

  it('已完成演练的“完成演练”按钮禁用', async () => {
    render(<Drills />)
    await screen.findByText('逃生演练')
    const doneRows = screen.getAllByText('灭火演练')
    const doneRow = doneRows.find((el) => el.closest('tr'))
    const buttons = within(doneRow.closest('tr')).getAllByRole('button', { name: /完成演练/ })
    expect(buttons[0]).toBeDisabled()
  })

  it('删除演练触发 deleteDrill 并提示', async () => {
    const user = userEvent.setup()
    render(<Drills />)
    await screen.findByText('逃生演练')
    await user.click(screen.getAllByRole('button', { name: 'delete' })[0])
    const popover = await screen.findByRole('tooltip')
    const confirmBtn = popover.querySelector('.ant-popconfirm-buttons .ant-btn-primary')
    await user.click(confirmBtn)
    await waitFor(() => expect(mocks.deleteDrill).toHaveBeenCalledWith(1))
    expect(message.success).toHaveBeenCalledWith('已删除')
  })

  it('保存失败时提示错误', async () => {
    const user = userEvent.setup()
    mocks.createDrill.mockRejectedValue({ response: { data: { detail: '服务异常' } } })
    render(<Drills />)
    await screen.findByText('逃生演练')
    await user.click(screen.getByRole('button', { name: /新增演练/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('标题'), '失败演练')
    await user.click(dialog.querySelector('.ant-modal-footer .ant-btn-primary'))
    await waitFor(() => expect(message.error).toHaveBeenCalledWith('服务异常'))
  })
})