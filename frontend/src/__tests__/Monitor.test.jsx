import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { STATUS_COLOR, ALARM_STATUS_TEXT } from '../utils/constants'

const mocks = vi.hoisted(() => ({
  fetchDevices: vi.fn(),
  fetchAreas: vi.fn(),
  fetchAlarms: vi.fn(),
  simulateAlarm: vi.fn(),
}))

vi.mock('../api', () => mocks)

import Monitor from '../pages/Monitor'

const deviceData = {
  total: 2,
  items: [
    { id: 1, name: '烟感A', device_type: 'smoke', status: 'alarm', area_id: 10, x: 20, y: 20 },
    { id: 2, name: '温感B', device_type: 'temp', status: 'normal', area_id: 10, x: 50, y: 50 },
  ],
}

beforeEach(() => {
  mocks.fetchDevices.mockReset().mockResolvedValue(deviceData)
  mocks.fetchAreas.mockReset().mockResolvedValue([{ id: 10, name: '一层' }])
  mocks.fetchAlarms.mockReset().mockResolvedValue({
    total: 1,
    items: [
      {
        id: 100,
        device_id: 1,
        fire_type: 'electrical',
        trigger_at: '2024-01-01T00:00:00Z',
        device: { name: '烟感A', status: 'alarm', area: { name: '一层' } },
      },
    ],
  })
  mocks.simulateAlarm.mockReset().mockResolvedValue({})
})

describe('Monitor', () => {
  it('渲染设备统计、地图标签与最新报警列表', async () => {
    render(<Monitor />)

    await waitFor(
      () => expect(screen.getAllByText('烟感A').length).toBeGreaterThan(0),
      { timeout: 3000 },
    )

    expect(screen.getAllByText('报警').length).toBeGreaterThan(0)

    const circles = document.querySelectorAll('svg circle')
    expect(circles.length).toBeGreaterThan(0)
    const deviceCircles = Array.from(circles).filter(
      (c) => c.getAttribute('fill') !== 'transparent',
    )
    expect(deviceCircles.length).toBe(2)
    expect(deviceCircles[0].getAttribute('fill')).toBe(STATUS_COLOR.alarm)

    expect(await screen.findByText(/电气火灾/)).toBeInTheDocument()
    expect(screen.getByText('最新报警（最近10条）')).toBeInTheDocument()

    expect(mocks.fetchDevices).toHaveBeenCalledWith({ page: 1, page_size: 500 })
    expect(mocks.fetchAreas).toHaveBeenCalled()
    expect(mocks.fetchAlarms).toHaveBeenCalledWith({ page: 1, page_size: 10 })
  })

  it('最新报警列表使用报警自身状态标签（而非设备状态）', async () => {
    mocks.fetchAlarms.mockResolvedValue({
      total: 1,
      items: [
        {
          id: 200,
          device_id: 1,
          status: 'pending',
          fire_type: 'electrical',
          trigger_at: '2024-01-01T00:00:00Z',
          device: { name: '烟感A', status: 'alarm', area: { name: '一层' } },
        },
      ],
    })
    render(<Monitor />)
    await waitFor(
      () => expect(screen.getAllByText('烟感A').length).toBeGreaterThan(0),
      { timeout: 3000 },
    )

    const tag = await screen.findByText(ALARM_STATUS_TEXT.pending)
    expect(tag).toBeInTheDocument()
    expect(tag.closest('.ant-tag').getAttribute('style')).toContain('rgb(250, 173, 20)')
  })

  it('触发模拟报警时调用 simulateAlarm 并携带设备与火灾类型', async () => {
    const user = userEvent.setup()
    render(<Monitor />)

    await waitFor(
      () => expect(screen.getAllByText('烟感A').length).toBeGreaterThan(0),
      { timeout: 3000 },
    )

    const selector = screen
      .getByText('选择要触发报警的设备')
      .closest('.ant-select')
    expect(selector).toBeTruthy()
    selector.querySelector('.ant-select-selector').dispatchEvent(
      new MouseEvent('mousedown', { bubbles: true }),
    )
    const option = await screen.findByText('烟感A（烟感探测器）')
    await user.click(option)

    await user.click(screen.getByRole('button', { name: '触发模拟报警' }))

    await waitFor(() =>
      expect(mocks.simulateAlarm).toHaveBeenCalledWith(
        expect.objectContaining({ device_id: 1, fire_type: 'ordinary' }),
      ),
    )
  })

  it('按设备类型筛选后地图仅保留对应设备图标', async () => {
    const user = userEvent.setup()
    render(<Monitor />)
    await waitFor(
      () => expect(screen.getAllByText('烟感A').length).toBeGreaterThan(0),
      { timeout: 3000 },
    )
    expect(document.querySelectorAll('.device-node').length).toBe(2)

    const typeFilter = screen.getByText('按设备类型筛选').closest('.ant-select')
    typeFilter.querySelector('.ant-select-selector').dispatchEvent(
      new MouseEvent('mousedown', { bubbles: true }),
    )
    const option = await screen.findByText('烟感探测器')
    await user.click(option)

    await waitFor(() => {
      const nodes = document.querySelectorAll('.device-node')
      expect(nodes.length).toBe(1)
    })
  })

  it('点击设备图标弹出详情（名称/类型/状态/坐标/区域）', async () => {
    render(<Monitor />)
    await waitFor(
      () => expect(screen.getAllByText('烟感A').length).toBeGreaterThan(0),
      { timeout: 3000 },
    )

    fireEvent.click(document.querySelectorAll('.device-node')[0])

    const dialog = await screen.findByRole('dialog')
    expect(withinDialog(dialog, '设备名称')).toBeInTheDocument()
    expect(withinDialog(dialog, '烟感探测器')).toBeInTheDocument()
    expect(withinDialog(dialog, '报警')).toBeInTheDocument()
    expect(withinDialog(dialog, '20, 20')).toBeInTheDocument()
    expect(withinDialog(dialog, '一层')).toBeInTheDocument()
  })

  it('按区域切换视图后仅显示所选区域设备', async () => {
    const user = userEvent.setup()
    mocks.fetchAreas.mockResolvedValue([
      { id: 10, name: '一层' },
      { id: 20, name: '二层' },
    ])
    mocks.fetchDevices.mockResolvedValue({
      total: 3,
      items: [
        { id: 1, name: '烟感A', device_type: 'smoke', status: 'alarm', area_id: 10, x: 20, y: 20 },
        { id: 2, name: '温感B', device_type: 'temp', status: 'normal', area_id: 10, x: 50, y: 50 },
        { id: 3, name: '喷淋C', device_type: 'sprinkler', status: 'normal', area_id: 20, x: 30, y: 30 },
      ],
    })
    render(<Monitor />)
    await waitFor(
      () => expect(document.querySelectorAll('.device-node').length).toBe(3),
      { timeout: 3000 },
    )

    const areaFilter = screen.getByText('按区域查看').closest('.ant-select')
    areaFilter.querySelector('.ant-select-selector').dispatchEvent(
      new MouseEvent('mousedown', { bubbles: true }),
    )
    const dropdown = await waitFor(() => {
      const el = document.querySelector('.ant-select-dropdown:not(.ant-select-dropdown-hidden)')
      if (!el) throw new Error('dropdown not open')
      return el
    })
    const option = await within(dropdown).findByText('二层')
    await user.click(option)

    await waitFor(() => {
      const nodes = document.querySelectorAll('.device-node')
      expect(nodes.length).toBe(1)
    })
  })

  it('填写现场场景后提交时以字符串传递 scene', async () => {
    const user = userEvent.setup()
    render(<Monitor />)
    await waitFor(
      () => expect(screen.getAllByText('烟感A').length).toBeGreaterThan(0),
      { timeout: 3000 },
    )

    const devSel = screen
      .getByText('选择要触发报警的设备')
      .closest('.ant-select')
    devSel.querySelector('.ant-select-selector').dispatchEvent(
      new MouseEvent('mousedown', { bubbles: true }),
    )
    await user.click(await screen.findByText('烟感A（烟感探测器）'))

    const sceneSel = screen.getByText('选择现场场景').closest('.ant-select')
    sceneSel.querySelector('.ant-select-selector').dispatchEvent(
      new MouseEvent('mousedown', { bubbles: true }),
    )
    await waitFor(() => {
      const opts = Array.from(document.querySelectorAll('.ant-select-item-option')).filter(
        (el) => el.textContent === '走廊烟雾弥漫',
      )
      if (!opts.length) throw new Error('scene option not open')
      return opts[0]
    })
    await user.click(
      Array.from(document.querySelectorAll('.ant-select-item-option')).find(
        (el) => el.textContent === '走廊烟雾弥漫',
      ),
    )

    await user.click(screen.getByRole('button', { name: '触发模拟报警' }))
    await waitFor(() =>
      expect(mocks.simulateAlarm).toHaveBeenCalledWith(
        expect.objectContaining({ device_id: 1, scene: '走廊烟雾弥漫' }),
      ),
    )
  })

  it('加载失败时展示错误提示', async () => {
    mocks.fetchDevices.mockRejectedValue(new Error('boom'))
    render(<Monitor />)
    expect(await screen.findByText('监控数据加载失败')).toBeInTheDocument()
  })

  it('页面重新可见时恢复轮询并立即刷新', async () => {
    render(<Monitor />)
    await waitFor(() => expect(mocks.fetchDevices).toHaveBeenCalled(), { timeout: 3000 })
    mocks.fetchDevices.mockClear()

    Object.defineProperty(document, 'hidden', { value: true, configurable: true })
    document.dispatchEvent(new Event('visibilitychange'))
    Object.defineProperty(document, 'hidden', { value: false, configurable: true })
    document.dispatchEvent(new Event('visibilitychange'))

    await waitFor(() => expect(mocks.fetchDevices).toHaveBeenCalled())
  })
})

function withinDialog(dialog, text) {
  return Array.from(dialog.querySelectorAll('*')).find((el) => el.textContent === text) || null
}