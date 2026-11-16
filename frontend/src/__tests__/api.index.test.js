import { describe, it, expect, beforeEach, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('../api/client', () => ({
  default: {
    get: (...a) => mocks.get(...a),
    post: (...a) => mocks.post(...a),
    put: (...a) => mocks.put(...a),
    delete: (...a) => mocks.delete(...a),
  },
}))

import * as api from '../api'

function ok(getter) {
  getter.mockResolvedValue({ data: { ok: true } })
}

beforeEach(() => {
  Object.values(mocks).forEach((m) => m.mockReset())
  ok(mocks.get)
  ok(mocks.post)
  ok(mocks.put)
  ok(mocks.delete)
})

describe('api/index 各接口函数', () => {
  it('login: POST /auth/login 带账户与密码', async () => {
    await api.login('admin', '123')
    expect(mocks.post).toHaveBeenCalledWith('/auth/login', {
      username: 'admin',
      password: '123',
    })
  })

  it('fetchDevices: GET /devices 并透传查询参数', async () => {
    await api.fetchDevices({ page: 1, page_size: 10, status: 'alarm' })
    expect(mocks.get).toHaveBeenCalledWith('/devices', {
      params: { page: 1, page_size: 10, status: 'alarm' },
    })
  })

  it('createDevice / updateDevice / updateDeviceStatus / deleteDevice', async () => {
    await api.createDevice({ name: 'D1' })
    expect(mocks.post).toHaveBeenCalledWith('/devices', { name: 'D1' })

    await api.updateDevice(7, { name: 'D2' })
    expect(mocks.put).toHaveBeenCalledWith('/devices/7', { name: 'D2' })

    await api.updateDeviceStatus(7, 'fault')
    expect(mocks.put).toHaveBeenCalledWith('/devices/7/status', { status: 'fault' })

    await api.deleteDevice(9)
    expect(mocks.delete).toHaveBeenCalledWith('/devices/9')
  })

  it('模拟报警与报警确认接口', async () => {
    await api.simulateAlarm({ device_id: 3, fire_type: 'oil' })
    expect(mocks.post).toHaveBeenCalledWith('/alarms/simulate', {
      device_id: 3,
      fire_type: 'oil',
    })

    await api.fetchAlarms({ page: 1 })
    expect(mocks.get).toHaveBeenCalledWith('/alarms', { params: { page: 1 } })

    await api.confirmAlarm(11, { result: 'true', scene: 'x' })
    expect(mocks.post).toHaveBeenCalledWith('/alarms/11/confirm', {
      result: 'true',
      scene: 'x',
    })
  })

  it('预案相关接口', async () => {
    await api.fetchPlanActions()
    expect(mocks.get).toHaveBeenCalledWith('/plans/actions')
    await api.fetchPlans()
    expect(mocks.get).toHaveBeenCalledWith('/plans')
    await api.createPlan({ name: 'p' })
    expect(mocks.post).toHaveBeenCalledWith('/plans', { name: 'p' })
    await api.updatePlan(2, { name: 'p2' })
    expect(mocks.put).toHaveBeenCalledWith('/plans/2', { name: 'p2' })
    await api.deletePlan(3)
    expect(mocks.delete).toHaveBeenCalledWith('/plans/3')
    await api.executePlan(4)
    expect(mocks.post).toHaveBeenCalledWith('/plans/4/execute')
  })

  it('联动、应急、巡检、维修、演练接口', async () => {
    await api.fetchRuns({ page: 1 })
    expect(mocks.get).toHaveBeenCalledWith('/linkage/runs', { params: { page: 1 } })
    await api.fetchRunDetail(5)
    expect(mocks.get).toHaveBeenCalledWith('/linkage/runs/5')

    await api.fetchEmergencies()
    expect(mocks.get).toHaveBeenCalledWith('/emergencies')
    await api.fetchEmergency(1)
    expect(mocks.get).toHaveBeenCalledWith('/emergencies/1')
    await api.createEmergency({ title: 'e' })
    expect(mocks.post).toHaveBeenCalledWith('/emergencies', { title: 'e' })
    await api.addEmergencyRecord(1, { note: 'n' })
    expect(mocks.post).toHaveBeenCalledWith('/emergencies/1/records', { note: 'n' })
    await api.closeEmergency(1, { result: 'ok' })
    expect(mocks.post).toHaveBeenCalledWith('/emergencies/1/close', { result: 'ok' })

    await api.fetchPatrols()
    expect(mocks.get).toHaveBeenCalledWith('/patrols')
    await api.fetchPatrolSummary()
    expect(mocks.get).toHaveBeenCalledWith('/patrols/summary')
    await api.createPatrol({ x: 1 })
    expect(mocks.post).toHaveBeenCalledWith('/patrols', { x: 1 })
    await api.submitPatrolResult(2, { r: true })
    expect(mocks.post).toHaveBeenCalledWith('/patrols/2/result', { r: true })

    await api.fetchRepairs()
    expect(mocks.get).toHaveBeenCalledWith('/repairs')
    await api.createRepair({ d: 1 })
    expect(mocks.post).toHaveBeenCalledWith('/repairs', { d: 1 })
    await api.startRepair(3)
    expect(mocks.post).toHaveBeenCalledWith('/repairs/3/start')
    await api.finishRepair(4, { note: 'x' })
    expect(mocks.post).toHaveBeenCalledWith('/repairs/4/finish', { note: 'x' })

    await api.fetchDrills()
    expect(mocks.get).toHaveBeenCalledWith('/drills')
    await api.createDrill({ t: 't' })
    expect(mocks.post).toHaveBeenCalledWith('/drills', { t: 't' })
    await api.updateDrill(6, { t: 't2' })
    expect(mocks.put).toHaveBeenCalledWith('/drills/6', { t: 't2' })
    await api.deleteDrill(7)
    expect(mocks.delete).toHaveBeenCalledWith('/drills/7')
    await api.finishDrill(8, { score: 90 })
    expect(mocks.post).toHaveBeenCalledWith('/drills/8/finish', { score: 90 })
  })

  it('统计与导出接口', async () => {
    await api.fetchDashboard()
    expect(mocks.get).toHaveBeenCalledWith('/stats/dashboard', { params: undefined })
    await api.fetchAlarmDetails()
    expect(mocks.get).toHaveBeenCalledWith('/stats/alarms', { params: undefined })

    mocks.get.mockResolvedValue({ data: new Blob() })
    await api.exportData('excel', 'alarm')
    expect(mocks.get).toHaveBeenCalledWith('/stats/export', {
      params: { type: 'excel', data: 'alarm' },
      responseType: 'blob',
    })
  })

  it('统计接口透传 from/to 时间筛选，导出同样带上', async () => {
    mocks.get.mockResolvedValue({ data: { ok: true } })
    await api.fetchDashboard({ from: '2024-01-01', to: '2024-01-31' })
    expect(mocks.get).toHaveBeenCalledWith('/stats/dashboard', {
      params: { from: '2024-01-01', to: '2024-01-31' },
    })

    await api.fetchAlarmDetails({ from: '2024-01-01' })
    expect(mocks.get).toHaveBeenCalledWith('/stats/alarms', {
      params: { from: '2024-01-01' },
    })

    mocks.get.mockResolvedValue({ data: new Blob() })
    await api.exportData('excel', 'alarms', { from: '2024-01-01', to: '2024-01-31' })
    expect(mocks.get).toHaveBeenCalledWith('/stats/export', {
      params: { type: 'excel', data: 'alarms', from: '2024-01-01', to: '2024-01-31' },
      responseType: 'blob',
    })
  })

  it('用户管理接口：列表/新增/编辑/重置密码', async () => {
    await api.fetchUsers()
    expect(mocks.get).toHaveBeenCalledWith('/users')

    await api.createUser({ username: 'u', role: 'duty', password: 'x' })
    expect(mocks.post).toHaveBeenCalledWith('/users', {
      username: 'u',
      role: 'duty',
      password: 'x',
    })

    await api.updateUser(3, { role: 'supervisor', is_active: false })
    expect(mocks.put).toHaveBeenCalledWith('/users/3', {
      role: 'supervisor',
      is_active: false,
    })

    await api.resetUserPassword(3, { password: 'newpw' })
    expect(mocks.post).toHaveBeenCalledWith('/users/3/reset_password', { password: 'newpw' })
  })
})