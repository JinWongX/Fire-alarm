import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { message } from 'antd'

const mocks = vi.hoisted(() => ({
  fetchPlans: vi.fn(),
  createPlan: vi.fn(),
  updatePlan: vi.fn(),
  deletePlan: vi.fn(),
  executePlan: vi.fn(),
  fetchAreas: vi.fn(),
}))

vi.mock('../api', () => mocks)

import Plans from '../pages/Plans'

beforeEach(() => {
  mocks.fetchPlans.mockReset().mockResolvedValue([])
  mocks.fetchAreas.mockReset().mockResolvedValue([])
  ;['createPlan', 'updatePlan', 'deletePlan', 'executePlan'].forEach((k) =>
    mocks[k].mockReset().mockResolvedValue({}),
  )
  vi.spyOn(message, 'success').mockImplementation(() => {})
  vi.spyOn(message, 'error').mockImplementation(() => {})
  vi.spyOn(message, 'warning').mockImplementation(() => {})
})

describe('Plans 联动预案', () => {
  it('火灾类型下拉包含“其他”(other) 选项', async () => {
    const user = userEvent.setup()
    render(<Plans />)
    await screen.findByText('新增预案')

    await user.click(screen.getByRole('button', { name: /新增预案/ }))
    await screen.findByRole('dialog')

    const fireTypeSelect = screen.getByText('普通火灾').closest('.ant-select')
    fireTypeSelect.querySelector('.ant-select-selector').dispatchEvent(
      new MouseEvent('mousedown', { bubbles: true }),
    )

    expect(await screen.findByText('其他')).toBeInTheDocument()
    expect(await screen.findByText('电气火灾')).toBeInTheDocument()
    expect(await screen.findByText('油类火灾')).toBeInTheDocument()
  })

  it('新增预案：填名称+添加联动动作后保存调用 createPlan', async () => {
    const user = userEvent.setup()
    render(<Plans />)
    await screen.findByText('新增预案')
    await user.click(screen.getByRole('button', { name: /新增预案/ }))
    let dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('预案名称'), '夜间联动预案')

    await user.click(screen.getByRole('button', { name: /添加联动动作/ }))
    const actionSelect = within(dialog)
      .getByText('选择联动动作')
      .closest('.ant-select')
    actionSelect.querySelector('.ant-select-selector').dispatchEvent(
      new MouseEvent('mousedown', { bubbles: true }),
    )
    await user.click(await screen.findByText('启动排烟'))

    dialog = await screen.findByRole('dialog')
    await user.click(dialog.querySelector('.ant-modal-footer .ant-btn-primary'))

    await waitFor(() =>
      expect(mocks.createPlan).toHaveBeenCalledWith(
        expect.objectContaining({
          name: '夜间联动预案',
          enabled: true,
          actions: [{ action_type: 'smoke_exhaust', action_name: '启动排烟' }],
        }),
      ),
    )
  })

  it('新增预案无联动动作时提示 warning 并阻止提交', async () => {
    const user = userEvent.setup()
    render(<Plans />)
    await screen.findByText('新增预案')
    await user.click(screen.getByRole('button', { name: /新增预案/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('预案名称'), '空动作预案')
    await user.click(dialog.querySelector('.ant-modal-footer .ant-btn-primary'))
    await waitFor(() =>
      expect(message.warning).toHaveBeenCalledWith('至少需要一条联动动作'),
    )
    expect(mocks.createPlan).not.toHaveBeenCalled()
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
  })

  it('编辑预案：回填并调用 updatePlan 与联动动作', async () => {
    mocks.fetchPlans.mockResolvedValue([
      {
        id: 1,
        name: 'A区预案',
        area_id: 10,
        fire_type: 'electrical',
        enabled: true,
        actions: [{ action_type: 'fire_door', action_name: '关闭防火门' }],
      },
    ])
    const user = userEvent.setup()
    render(<Plans />)
    await screen.findByText('A区预案')
    await user.click(screen.getByRole('button', { name: 'edit' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByLabelText('预案名称').value).toBe('A区预案')
    await user.click(dialog.querySelector('.ant-modal-footer .ant-btn-primary'))
    await waitFor(() =>
      expect(mocks.updatePlan).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ name: 'A区预案' }),
      ),
    )
    expect(mocks.createPlan).not.toHaveBeenCalled()
  })

  it('手动执行：调用 executePlan 并展示执行结果弹窗', async () => {
    mocks.executePlan.mockResolvedValue({
      run: { id: 9, status: 'success', trigger_type: 'manual', trigger_at: '2026-09-01T00:00:00' },
    })
    mocks.fetchPlans.mockResolvedValue([{ id: 1, name: 'A区预案', actions: [], enabled: true }])
    const user = userEvent.setup()
    render(<Plans />)
    await screen.findByText('A区预案')
    await user.click(screen.getByRole('button', { name: /手动执行/ }))
    await waitFor(() => expect(mocks.executePlan).toHaveBeenCalledWith(1))
    expect(await screen.findByText(/联动执行 ID/)).toBeInTheDocument()
    expect(screen.getByText('success')).toBeInTheDocument()
    expect(screen.getAllByText('手动执行').length).toBeGreaterThan(0)
    expect(message.success).toHaveBeenCalledWith('预案手动执行成功')
  })

  it('手动执行失败时提示错误', async () => {
    mocks.executePlan.mockRejectedValue({ response: { data: { detail: '执行超时' } } })
    mocks.fetchPlans.mockResolvedValue([{ id: 1, name: 'A区预案', actions: [], enabled: true }])
    vi.spyOn(message, 'error').mockImplementation(() => {})
    const user = userEvent.setup()
    render(<Plans />)
    await screen.findByText('A区预案')
    await user.click(screen.getByRole('button', { name: /手动执行/ }))
    await waitFor(() => expect(message.error).toHaveBeenCalledWith('执行超时'))
  })

  it('删除预案触发 deletePlan', async () => {
    mocks.fetchPlans.mockResolvedValue([{ id: 1, name: '待删预案', actions: [], enabled: true }])
    const user = userEvent.setup()
    render(<Plans />)
    await screen.findByText('待删预案')
    await user.click(screen.getByRole('button', { name: 'delete' }))
    const popover = await screen.findByRole('tooltip')
    const confirmBtn = popover.querySelector('.ant-popconfirm-buttons .ant-btn-primary')
    await user.click(confirmBtn)
    await waitFor(() => expect(mocks.deletePlan).toHaveBeenCalledWith(1))
  })
})
