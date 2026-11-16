import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { message } from 'antd'

const mocks = vi.hoisted(() => ({
  fetchEmergencies: vi.fn(),
  fetchEmergency: vi.fn(),
  createEmergency: vi.fn(),
  addEmergencyRecord: vi.fn(),
  closeEmergency: vi.fn(),
  fetchAlarms: vi.fn(),
}))

vi.mock('../api', () => mocks)

import Emergencies from '../pages/Emergencies'

const activeItem = { id: 1, title: 'A区火灾处置', alarm_id: 5, start_at: '2026-09-01T10:00:00', status: 'active', result: '' }
const closedItem = { id: 2, title: 'B区处置', status: 'closed', result: '已扑灭' }

const activeDetail = {
  id: 1,
  title: 'A区火灾处置',
  status: 'active',
  alarm: { id: 5, device: { name: '烟感A' } },
  start_at: '2026-09-01T10:00:00',
  closed_at: null,
  result: '',
  records: [{ time: '10:05', person: '张三', content: '到场' }],
}

beforeEach(() => {
  mocks.fetchEmergencies.mockReset().mockResolvedValue([activeItem, closedItem])
  mocks.fetchEmergency.mockReset().mockResolvedValue(activeDetail)
  mocks.fetchAlarms.mockReset().mockResolvedValue({
    items: [{ id: 5, device: { name: '烟感A' }, fire_type: 'electrical' }],
  })
  ;['createEmergency', 'addEmergencyRecord', 'closeEmergency'].forEach((k) =>
    mocks[k].mockReset().mockResolvedValue({}),
  )
  vi.spyOn(message, 'success').mockImplementation(() => {})
  vi.spyOn(message, 'error').mockImplementation(() => {})
})

describe('Emergencies 应急处置', () => {
  it('渲染列表：处置中/已闭环中文状态与处置结果列', async () => {
    render(<Emergencies />)
    await screen.findByText('A区火灾处置')
    expect(screen.getByText('处置中')).toBeInTheDocument()
    expect(screen.getByText('已闭环')).toBeInTheDocument()
    expect(screen.getByText('报警 #5')).toBeInTheDocument()
    expect(mocks.fetchAlarms).toHaveBeenCalledWith({ status: 'pending', page: 1, page_size: 100 })
  })

  it('新增处置单：选择待确认报警并填写标题后创建', async () => {
    const user = userEvent.setup()
    render(<Emergencies />)
    await screen.findByText('A区火灾处置')
    await user.click(screen.getByRole('button', { name: /新增处置单/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByPlaceholderText('如：A区一层消防处置'), 'C区处置单')
    await user.click(dialog.querySelector('.ant-modal-footer .ant-btn-primary'))
    await waitFor(() =>
      expect(mocks.createEmergency).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'C区处置单' }),
      ),
    )
  })

  it('打开详情展示处置记录并可添加记录', async () => {
    const user = userEvent.setup()
    render(<Emergencies />)
    await screen.findByText('A区火灾处置')
    fireEvent.click(screen.getAllByRole('button', { name: /详情/ })[0])
    await screen.findByText('到场')
    fireEvent.click(await screen.findByRole('button', { name: /添加处置记录/ }))
    const recModal = await screen.findByText(/添加处置记录 · #/)
    const record = recModal.closest('.ant-modal')
    const timeInput = record.querySelector('input')
    const content = record.querySelector('textarea')
    await user.type(timeInput, '10:30')
    await user.type(content, '出水灭火')
    fireEvent.click(record.querySelector('.ant-modal-footer .ant-btn-primary'))
    await waitFor(() =>
      expect(mocks.addEmergencyRecord).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ time: '10:30', content: '出水灭火' }),
      ),
    )
  })

  it('活动处置单可闭环，调用 closeEmergency', async () => {
    const user = userEvent.setup()
    render(<Emergencies />)
    await screen.findByText('A区火灾处置')
    fireEvent.click(screen.getAllByRole('button', { name: /详情/ })[0])
    await screen.findByText('到场')
    fireEvent.click(await screen.findByRole('button', { name: /闭环（结束处置）/ }))
    const result = await screen.findByPlaceholderText('填写本次处置的最终结果')
    const closeDialog = result.closest('.ant-modal')
    await user.type(result, '处置完毕')
    fireEvent.click(closeDialog.querySelector('.ant-modal-footer .ant-btn-primary'))
    await waitFor(() =>
      expect(mocks.closeEmergency).toHaveBeenCalledWith(1, { result: '处置完毕' }),
    )
  })

  it('已闭环详情无底部操作按钮', async () => {
    const user = userEvent.setup()
    mocks.fetchEmergency.mockResolvedValue({ ...activeDetail, status: 'closed', closed_at: '2026-09-02', closed_by: '李四', result: '已扑灭' })
    render(<Emergencies />)
    await screen.findByText('A区火灾处置')
    await user.click(screen.getAllByRole('button', { name: /详情/ })[1])
    expect(await screen.findByText(/李四/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /闭环（结束处置）/ })).toBeNull()
    expect(within(document.querySelector('.ant-modal-body')).getByText('已扑灭')).toBeInTheDocument()
  })

  it('详情拉取失败时提示错误', async () => {
    mocks.fetchEmergency.mockRejectedValue({ response: { data: { detail: '详情不存在' } } })
    render(<Emergencies />)
    await screen.findByText('A区火灾处置')
    fireEvent.click(screen.getAllByRole('button', { name: /详情/ })[0])
    await waitFor(() => expect(message.error).toHaveBeenCalledWith('详情不存在'))
  })
})