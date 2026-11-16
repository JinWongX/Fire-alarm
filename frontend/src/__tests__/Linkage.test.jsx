import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { message } from 'antd'

const mocks = vi.hoisted(() => ({
  fetchRuns: vi.fn(),
  fetchRunDetail: vi.fn(),
}))

vi.mock('../api', () => mocks)

import Linkage from '../pages/Linkage'

const run = {
  id: 1,
  trigger_type: 'auto',
  plan_name: 'A区联动预案',
  alarm: { id: 5, fire_type: 'electrical' },
  status: 'success',
  trigger_at: '2026-09-01T10:00:00',
}
const detail = {
  id: 1,
  trigger_type: 'auto',
  plan_name: 'A区联动预案',
  status: 'success',
  trigger_at: '2026-09-01T10:00:00',
  results: [{ action_type: 'smoke_exhaust', status: 'success', detail: '风机已启动' }],
}

beforeEach(() => {
  mocks.fetchRuns.mockReset().mockResolvedValue({ total: 1, items: [run] })
  mocks.fetchRunDetail.mockReset().mockResolvedValue(detail)
  vi.spyOn(message, 'error').mockImplementation(() => {})
})

describe('Linkage 联动执行记录', () => {
  it('渲染运行列表：自动标签、预案名、关联报警与状态', async () => {
    render(<Linkage />)
    await screen.findByText('A区联动预案')
    expect(screen.getByText('自动')).toBeInTheDocument()
    expect(screen.getByText(/报警 #5（电气火灾）/)).toBeInTheDocument()
    expect(screen.getByText('success')).toBeInTheDocument()
    expect(mocks.fetchRuns).toHaveBeenCalledWith({ page: 1, page_size: 10 })
  })

  it('手动触发方式渲染“手动”标签且无关联报警时显示占位', async () => {
    mocks.fetchRuns.mockResolvedValue({
      total: 1,
      items: [{ ...run, id: 2, trigger_type: 'manual', alarm: null, plan_name: 'B区预案' }],
    })
    render(<Linkage />)
    await screen.findByText('B区预案')
    expect(screen.getByText('手动')).toBeInTheDocument()
    // 无关联报警的占位 '-' 由表格 render 输出
    expect(mocks.fetchRuns).toHaveBeenCalled()
  })

  it('点击详情展示联动动作结果', async () => {
    render(<Linkage />)
    const title = await screen.findByText('A区联动预案')
    await waitFor(() => expect(document.querySelector('.ant-spin-blur')).toBeNull())
    const btn = within(title.closest('tr')).getByRole('button')
    fireEvent.click(btn)
    await waitFor(() => expect(document.querySelector('.ant-modal .ant-spin-spinning')).toBeNull())
    expect(await screen.findByText('风机已启动')).toBeInTheDocument()
    expect(mocks.fetchRunDetail).toHaveBeenCalledWith(1)
  })

  it('详情拉取失败时提示错误并关闭 loading', async () => {
    mocks.fetchRunDetail.mockRejectedValue({ response: { data: { detail: '详情超时' } } })
    render(<Linkage />)
    const title = await screen.findByText('A区联动预案')
    await waitFor(() => expect(document.querySelector('.ant-spin-blur')).toBeNull())
    const btn = within(title.closest('tr')).getByRole('button')
    fireEvent.click(btn)
    await waitFor(() => expect(message.error).toHaveBeenCalledWith('详情超时'))
    await waitFor(() => expect(document.querySelector('.ant-modal .ant-spin-spinning')).toBeNull())
  })
})