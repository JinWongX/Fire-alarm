import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { message } from 'antd'

const mockUseAuth = vi.hoisted(() => ({ useAuth: vi.fn() }))
const mocks = vi.hoisted(() => ({
  fetchDevices: vi.fn(),
  fetchAreas: vi.fn(),
  createDevice: vi.fn(),
  updateDevice: vi.fn(),
  updateDeviceStatus: vi.fn(),
  deleteDevice: vi.fn(),
}))

vi.mock('../context/AuthContext', () => mockUseAuth)
vi.mock('../api', () => mocks)

import Devices from '../pages/Devices'

const device = {
  id: 1,
  device_no: 'D-001',
  name: '烟感A',
  device_type: 'smoke',
  area_id: 10,
  x: 20,
  y: 30,
  install_date: '2024-01-01',
  status: 'normal',
  remark: '',
  area: { id: 10, name: '一层' },
}

beforeEach(() => {
  mockUseAuth.useAuth.mockReset().mockReturnValue({ user: { role: 'supervisor' } })
  mocks.fetchDevices.mockReset().mockResolvedValue({ total: 1, items: [device] })
  mocks.fetchAreas.mockReset().mockResolvedValue([{ id: 10, name: '一层' }])
  ;['createDevice', 'updateDevice', 'updateDeviceStatus', 'deleteDevice'].forEach((k) =>
    mocks[k].mockReset().mockResolvedValue({}),
  )
  vi.spyOn(message, 'success').mockImplementation(() => {})
  vi.spyOn(message, 'error').mockImplementation(() => {})
})

describe('Devices', () => {
  it('渲染设备列表（类型/状态中文映射）', async () => {
    render(<Devices />)
    expect(await screen.findByText('烟感A')).toBeInTheDocument()
    expect(screen.getByText('D-001')).toBeInTheDocument()
    expect(screen.getByText('烟感探测器')).toBeInTheDocument()
    expect(screen.getAllByText('正常').length).toBeGreaterThan(0)
  })

  it('新增设备的抽屉包含所有表单字段', async () => {
    const user = userEvent.setup()
    render(<Devices />)
    await user.click(await screen.findByRole('button', { name: /新增设备/ }))

    await waitFor(() => {
      expect(screen.getByLabelText('设备编号')).toBeInTheDocument()
      expect(screen.getByLabelText('设备名称')).toBeInTheDocument()
      expect(screen.getByLabelText('设备类型')).toBeInTheDocument()
      expect(screen.getByLabelText('所属区域')).toBeInTheDocument()
      expect(screen.getAllByText('X 坐标').length).toBeGreaterThan(0)
      expect(screen.getAllByText('安装日期').length).toBeGreaterThan(0)
      expect(screen.getAllByText('状态').length).toBeGreaterThan(0)
      expect(screen.getAllByText('备注').length).toBeGreaterThan(0)
    })
  })

  it('编辑设备时表单回填原数据', async () => {
    const user = userEvent.setup()
    render(<Devices />)
    await screen.findByText('烟感A')
    await waitFor(() => expect(document.querySelector('.ant-spin-blur')).toBeNull())
    const editBtn = await screen.findByRole('button', { name: /编辑/ })
    await user.click(editBtn)

    await waitFor(() => {
      expect(screen.getByLabelText('设备编号')).toHaveValue('D-001')
      expect(screen.getByLabelText('设备名称')).toHaveValue('烟感A')
    })
  })

  it('编辑提交时透传 status 字段', async () => {
    const user = userEvent.setup()
    render(<Devices />)
    await screen.findByText('烟感A')
    await waitFor(() => expect(document.querySelector('.ant-spin-blur')).toBeNull())
    await user.click(await screen.findByRole('button', { name: /编辑/ }))
    await waitFor(() => expect(screen.getByLabelText('设备名称')).toHaveValue('烟感A'))

    const saveBtn = await waitFor(() => {
      const btn = Array.from(document.querySelectorAll('button')).find(
        (b) => b.textContent.replace(/\s+/g, '') === '保存',
      )
      if (!btn) throw new Error('save button not found')
      return btn
    })
    await user.click(saveBtn)

    await waitFor(() =>
      expect(mocks.updateDevice).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ status: 'normal' }),
      ),
    )
  })

  it('主管确认删除后调用 deleteDevice', async () => {
    const user = userEvent.setup()
    render(<Devices />)
    await screen.findByText('烟感A')
    await waitFor(() => expect(document.querySelector('.ant-spin-blur')).toBeNull())

    const delBtn = document.querySelector('.ant-btn-dangerous')
    expect(delBtn).toBeTruthy()
    await user.click(delBtn)

    const okBtn = await screen.findByRole('button', { name: /确定|OK/i })
    await user.click(okBtn)

    await waitFor(() => expect(mocks.deleteDevice).toHaveBeenCalledWith(1))
  })

  it('非主管不显示删除按钮', async () => {
    mockUseAuth.useAuth.mockReturnValue({ user: { role: 'maintenance' } })
    render(<Devices />)
    await screen.findByText('烟感A')
    expect(document.querySelector('.ant-btn-dangerous')).toBeNull()
  })

  it('新增设备填写并保存调用 createDevice', async () => {
    const user = userEvent.setup()
    render(<Devices />)
    await user.click(await screen.findByRole('button', { name: /新增设备/ }))
    await waitFor(() => expect(screen.getByLabelText('设备编号')).toBeInTheDocument())
    await user.type(screen.getByLabelText('设备编号'), 'D-002')
    await user.type(screen.getByLabelText('设备名称'), '温感C')
    const typeSelect = screen.getByLabelText('设备类型').closest('.ant-select')
    await user.click(typeSelect.querySelector('.ant-select-selector'))
    await user.click(await screen.findByText('温感探测器'))
    const saveBtn = Array.from(document.querySelectorAll('button')).find(
      (b) => b.textContent.replace(/\s+/g, '') === '保存',
    )
    await user.click(saveBtn)
    await waitFor(() =>
      expect(mocks.createDevice).toHaveBeenCalledWith(
        expect.objectContaining({ device_no: 'D-002', name: '温感C' }),
      ),
    )
  })

  it('行内切换设备状态调用 updateDeviceStatus', async () => {
    const user = userEvent.setup()
    render(<Devices />)
    await screen.findByText('烟感A')
    await waitFor(() => expect(document.querySelector('.ant-spin-blur')).toBeNull())
    const statusSelect = Array.from(document.querySelectorAll('.ant-select')).find(
      (sel) => sel.textContent.includes('正常'),
    )
    await user.click(statusSelect.querySelector('.ant-select-selector'))
    await user.click(await screen.findByText('故障'))
    await waitFor(() => expect(mocks.updateDeviceStatus).toHaveBeenCalledWith(1, 'fault'))
  })

  it('输入关键字防抖后请求携带 keyword 参数（不做本地过滤）', async () => {
    const user = userEvent.setup()
    render(<Devices />)
    await screen.findByText('烟感A')
    const search = screen.getByPlaceholderText('搜索名称/编号/区域')
    await user.type(search, '烟感')
    await waitFor(
      () =>
        expect(mocks.fetchDevices).toHaveBeenCalledWith(
          expect.objectContaining({ keyword: '烟感', page: 1, page_size: 10 }),
        ),
      { timeout: 3000 },
    )
  })
})