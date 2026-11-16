import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import dayjs from 'dayjs'
import { message } from 'antd'

const mockUseAuth = vi.hoisted(() => ({ useAuth: vi.fn() }))
const mocks = vi.hoisted(() => ({
  fetchDashboard: vi.fn(),
  fetchAlarmDetails: vi.fn(),
  exportData: vi.fn(),
}))

vi.mock('../context/AuthContext', () => mockUseAuth)
vi.mock('../api', () => mocks)
vi.mock('echarts-for-react', () => ({ default: () => null }))

import Stats from '../pages/Stats'

const dash = {
  alarm_total: 10,
  alarm_true: 6,
  alarm_false: 4,
  device_total: 100,
  plan_total: 5,
  drill_total: 3,
  emergency_total: 2,
  device_status: { normal: 80, alarm: 2, fault: 1, masked: 0 },
  alarm_trend: [{ date: '2026-09-01', count: 1 }],
  false_alarm_rate: 40,
  patrol_done_rate: 80,
}

beforeEach(() => {
  mockUseAuth.useAuth.mockReset().mockReturnValue({ user: { role: 'supervisor' } })
  mocks.fetchDashboard.mockReset().mockResolvedValue(dash)
  mocks.fetchAlarmDetails.mockReset().mockResolvedValue({ total: 0, items: [] })
  mocks.exportData.mockReset().mockResolvedValue({ data: new Blob() })
  vi.spyOn(message, 'success').mockImplementation(() => {})
  vi.spyOn(message, 'error').mockImplementation(() => {})
})

describe('Stats 统计报表', () => {
  it('初始加载 dashboard 不携带时间筛选', async () => {
    render(<Stats />)
    await screen.findByText('报警总数')
    expect(mocks.fetchDashboard).toHaveBeenCalledWith({})
    expect(mocks.fetchAlarmDetails).toHaveBeenCalledWith({})
  })

  it('选择时间范围后透传 from/to 重新加载 dashboard 与报警明细', async () => {
    const user = userEvent.setup()
    render(<Stats />)
    await screen.findByText('报警总数')
    mocks.fetchDashboard.mockClear()
    mocks.fetchAlarmDetails.mockClear()

    const startInput = screen.getByPlaceholderText('开始日期')
    await user.click(startInput)

    const dropdown = document.querySelector('.ant-picker-dropdown')
    const now = dayjs()
    const dayCells = () => within(dropdown).getAllByText('1')
    await user.click(dayCells()[0])

    const twoCells = () => within(dropdown).getAllByText('2')
    await user.click(twoCells()[0])

    const from = now.date(1).format('YYYY-MM-DD')
    const to = now.date(2).format('YYYY-MM-DD')
    await waitFor(() =>
      expect(mocks.fetchDashboard).toHaveBeenCalledWith({ from, to }),
    )
    expect(mocks.fetchAlarmDetails).toHaveBeenCalledWith({ from, to })
  })

  it('supervisor 可看到导出按钮', async () => {
    render(<Stats />)
    await screen.findByText('报警总数')
    expect(screen.getByRole('button', { name: /导出报警Excel/ })).toBeInTheDocument()
  })

  it('导出报警Excel 调用 exportData 并触发下载', async () => {
    const user = userEvent.setup()
    const origCreate = URL.createObjectURL
    const origRevoke = URL.revokeObjectURL
    URL.createObjectURL = vi.fn(() => 'blob:fake')
    URL.revokeObjectURL = vi.fn()
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    try {
      render(<Stats />)
      await screen.findByText('报警总数')
      await user.click(screen.getByRole('button', { name: /导出报警Excel/ }))
      await waitFor(() =>
        expect(mocks.exportData).toHaveBeenCalledWith('excel', 'alarms', {}),
      )
      await waitFor(() => expect(message.success).toHaveBeenCalledWith('导出成功'))
    } finally {
      URL.createObjectURL = origCreate
      URL.revokeObjectURL = origRevoke
      clickSpy.mockRestore()
    }
  })

  it('导出失败时提示错误', async () => {
    const user = userEvent.setup()
    mocks.exportData.mockRejectedValue({})
    render(<Stats />)
    await screen.findByText('报警总数')
    await user.click(screen.getByRole('button', { name: /导出报警Excel/ }))
    await waitFor(() => expect(message.error).toHaveBeenCalledWith('导出失败'))
  })

  it('报警明细渲染后端返回的 {total,items} 数据', async () => {
    mocks.fetchAlarmDetails.mockReset().mockResolvedValue({
      total: 2,
      items: [
        { id: 1, device_no: 'D-001', device_name: '烟感A', fire_type: 'electrical', trigger_at: '2026-09-01T10:00:00', status: 'pending', false_reason: null },
        { id: 2, device_no: 'D-002', device_name: '温感B', fire_type: 'ordinary', trigger_at: '2026-09-01T11:00:00', status: 'confirmed_false', false_reason: '烹饪油烟' },
      ],
    })
    render(<Stats />)
    expect(await screen.findByText('烟感A')).toBeInTheDocument()
    expect(screen.getByText('温感B')).toBeInTheDocument()
    expect(screen.getByText('烹饪油烟')).toBeInTheDocument()
  })

  it('报警明细为空时后端返回 {total:0,items:[]} 不渲染表格行', async () => {
    mocks.fetchAlarmDetails.mockReset().mockResolvedValue({ total: 0, items: [] })
    render(<Stats />)
    await screen.findByText('报警总数')
    await waitFor(() => expect(mocks.fetchAlarmDetails).toHaveBeenCalled())
    expect(screen.queryByText('D-003')).toBeNull()
  })

  it('非 supervisor 不显示导出按钮并提示仅主管可用', async () => {
    mockUseAuth.useAuth.mockReturnValue({ user: { role: 'duty' } })
    render(<Stats />)
    await screen.findByText('报警总数')
    expect(screen.queryByRole('button', { name: /导出报警Excel/ })).toBeNull()
    expect(screen.getByText('导出功能仅主管可用')).toBeInTheDocument()
  })
})
