import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { message } from 'antd'

const mocks = vi.hoisted(() => ({
  fetchRepairs: vi.fn(),
  startRepair: vi.fn(),
  finishRepair: vi.fn(),
  fetchDevices: vi.fn(),
}))

vi.mock('../api', () => mocks)

import Repairs from '../pages/Repairs'

const pending = { id: 1, device_id: 1, title: '烟感离线', description: '检测不到', status: 'pending', creator: '张三', created_at: '2026-09-01', result: '' }
const inProgress = { id: 2, device_id: 99, title: '喷淋维修', status: 'in_progress' }
const done = { id: 3, device_id: 1, title: '已修', status: 'done', result: '更换完成' }

beforeEach(() => {
  mocks.fetchRepairs.mockReset().mockResolvedValue([pending, inProgress, done])
  mocks.startRepair.mockReset().mockResolvedValue({})
  mocks.finishRepair.mockReset().mockResolvedValue({})
  mocks.fetchDevices.mockReset().mockResolvedValue({ items: [{ id: 1, name: '烟感A' }] })
  vi.spyOn(message, 'success').mockImplementation(() => {})
  vi.spyOn(message, 'error').mockImplementation(() => {})
})

describe('Repairs 维修管理', () => {
  it('渲染列表：设备名/标题/状态中文/结果列', async () => {
    render(<Repairs />)
    await screen.findByText('烟感离线')
    expect(screen.getAllByText('烟感A').length).toBeGreaterThan(0)
    expect(screen.getByText('待维修')).toBeInTheDocument()
    expect(screen.getByText('维修中')).toBeInTheDocument()
    expect(screen.getByText('已完成')).toBeInTheDocument()
    expect(screen.getByText('更换完成')).toBeInTheDocument()
  })

  it('未知设备 ID 回退为“设备#id”', async () => {
    render(<Repairs />)
    await screen.findByText('烟感离线')
    expect(screen.getByText('设备#99')).toBeInTheDocument()
  })

  it('待维修可“开始维修”并调用 startRepair', async () => {
    render(<Repairs />)
    await screen.findByText('烟感离线')
    await waitFor(() => expect(document.querySelector('.ant-spin-blur')).toBeNull())
    fireEvent.click(screen.getByRole('button', { name: /开始维修/ }))
    await waitFor(() => expect(mocks.startRepair).toHaveBeenCalledWith(1))
    await waitFor(() => expect(message.success).toHaveBeenCalledWith('维修已开始'))
  })

  it('维修中可“完成维修”填写结果后调用 finishRepair', async () => {
    const user = userEvent.setup()
    render(<Repairs />)
    await screen.findByText('烟感离线')
    await waitFor(() => expect(document.querySelector('.ant-spin-blur')).toBeNull())
    fireEvent.click(screen.getByRole('button', { name: /完成维修/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByPlaceholderText('填写维修结果'), '更换主板')
    await user.click(dialog.querySelector('.ant-modal-footer .ant-btn-primary'))
    await waitFor(() =>
      expect(mocks.finishRepair).toHaveBeenCalledWith(2, { result: '更换主板' }),
    )
  })

  it('已完成维修不显示操作按钮', async () => {
    render(<Repairs />)
    await screen.findByText('烟感离线')
    const startButtons = screen.queryAllByRole('button', { name: /开始维修/ })
    const finishButtons = screen.queryAllByRole('button', { name: /完成维修/ })
    // 仅列出待维修开始 1 个、维修中完成 1 个，已完成无按钮
    expect(startButtons.length).toBe(1)
    expect(finishButtons.length).toBe(1)
  })

  it('开始维修失败时提示错误', async () => {
    mocks.startRepair.mockRejectedValue({ response: { data: { detail: '无权操作' } } })
    render(<Repairs />)
    await screen.findByText('烟感离线')
    await waitFor(() => expect(document.querySelector('.ant-spin-blur')).toBeNull())
    fireEvent.click(screen.getByRole('button', { name: /开始维修/ }))
    await waitFor(() => expect(message.error).toHaveBeenCalledWith('无权操作'))
  })
})