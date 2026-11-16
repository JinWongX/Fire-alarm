import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const mockUseAuth = vi.hoisted(() => ({ useAuth: vi.fn() }))
vi.mock('../context/AuthContext', () => mockUseAuth)

import MainLayout, { menuConfig } from '../components/MainLayout'
import RequireAuth from '../components/RequireAuth'

function renderLayout(user) {
  mockUseAuth.useAuth.mockReturnValue({ user, logout: vi.fn() })
  return render(
    <MemoryRouter initialEntries={['/monitor']}>
      <Routes>
        <Route path="*" element={<MainLayout />} />
      </Routes>
    </MemoryRouter>,
  )
}

const supervisorOnly = ['联动预案', '消防演练', '统计报表', '用户管理']

beforeEach(() => {
  mockUseAuth.useAuth.mockReset().mockReturnValue({ user: null, logout: vi.fn() })
})

describe('MainLayout 角色菜单', () => {
  it('supervisor 展示全部菜单（含统计与用户管理）', () => {
    renderLayout({ username: 'admin', real_name: '主管A', role: 'supervisor' })

    expect(screen.getByText('消防联动控制')).toBeInTheDocument()
    expect(screen.getByText('实时监控')).toBeInTheDocument()
    expect(screen.getByText('设备档案')).toBeInTheDocument()
    expect(screen.getByText('报警管理')).toBeInTheDocument()
    expect(screen.getByText('联动预案')).toBeInTheDocument()
    expect(screen.getByText('联动执行记录')).toBeInTheDocument()
    expect(screen.getByText('应急处置')).toBeInTheDocument()
    expect(screen.getByText('设备巡检')).toBeInTheDocument()
    expect(screen.getByText('维修管理')).toBeInTheDocument()
    expect(screen.getByText('消防演练')).toBeInTheDocument()
    expect(screen.getByText('统计报表')).toBeInTheDocument()
    expect(screen.getByText('用户管理')).toBeInTheDocument()
    expect(screen.getByText('主管A')).toBeInTheDocument()
  })

  it('duty 展示设备档案，但不展示预案/演练/统计/用户管理菜单', () => {
    renderLayout({ username: 'duty', role: 'duty' })

    expect(screen.getByText('实时监控')).toBeInTheDocument()
    expect(screen.getByText('设备档案')).toBeInTheDocument()
    expect(screen.getByText('报警管理')).toBeInTheDocument()
    expect(screen.getByText('联动执行记录')).toBeInTheDocument()
    expect(screen.getByText('应急处置')).toBeInTheDocument()
    supervisorOnly.forEach((label) => {
      expect(screen.queryByText(label)).toBeNull()
    })
  })

  it('maintenance 不展示统计、预案、演练与用户管理菜单', () => {
    renderLayout({ username: 'maintain', role: 'maintenance' })

    expect(screen.getByText('实时监控')).toBeInTheDocument()
    expect(screen.getByText('设备档案')).toBeInTheDocument()
    expect(screen.getByText('设备巡检')).toBeInTheDocument()
    expect(screen.getByText('维修管理')).toBeInTheDocument()
    ;['统计报表', '联动预案', '消防演练', '用户管理'].forEach((label) => {
      expect(screen.queryByText(label)).toBeNull()
    })
  })

  it('菜单矩阵与 PRD 权限一致（supervisor 全量 / duty 无统计预案演练用户管理 / maintenance 无统计预案演练用户管理）', () => {
    const labelOf = (key) => menuConfig.find((m) => m.key === key)?.label
    const labelsFor = {
      supervisor: ['实时监控', '设备档案', '报警管理', '联动预案', '联动执行记录', '应急处置', '设备巡检', '维修管理', '消防演练', '统计报表', '用户管理'],
      duty: ['实时监控', '设备档案', '报警管理', '联动执行记录', '应急处置'],
      maintenance: ['实时监控', '设备档案', '设备巡检', '维修管理'],
    }
    Object.entries(labelsFor).forEach(([role, expected]) => {
      const visible = menuConfig.filter((m) => m.roles.includes(role)).map((m) => m.label)
      expect(visible.sort()).toEqual(expected.sort())
    })
    // 角色集的完整性：所有已定义的菜单路径 role 归属与权限模块一致
    expect(labelOf('/stats')).toBe('统计报表')
    expect(menuConfig.find((m) => m.key === '/users').roles).toEqual(['supervisor'])
    expect(menuConfig.find((m) => m.key === '/stats').roles).toEqual(['supervisor'])
  })

  it('点击退出登录时调用 logout 并跳转 /login', async () => {
    const user = userEvent.setup()
    const logout = vi.fn()
    mockUseAuth.useAuth.mockReturnValue({ user: { username: 'admin', role: 'supervisor' }, logout })
    render(
      <MemoryRouter initialEntries={['/monitor']}>
        <Routes>
          <Route path="*" element={<MainLayout />} />
          <Route path="/login" element={<div>LOGIN_PAGE</div>} />
        </Routes>
      </MemoryRouter>,
    )
    await user.click(screen.getByText('admin'))
    await user.click(await screen.findByText('退出登录'))
    expect(logout).toHaveBeenCalled()
    expect(await screen.findByText('LOGIN_PAGE')).toBeInTheDocument()
  })
})

describe('RequireAuth 路由守卫', () => {
  it('未登录跳转到 /login', () => {
    mockUseAuth.useAuth.mockReturnValue({ user: null })
    render(
      <MemoryRouter initialEntries={['/monitor']}>
        <Routes>
          <Route path="/login" element={<div>LOGIN_PAGE</div>} />
          <Route
            path="/monitor"
            element={
              <RequireAuth>
                <div>SECURE_CONTENT</div>
              </RequireAuth>
            }
          />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByText('LOGIN_PAGE')).toBeInTheDocument()
    expect(screen.queryByText('SECURE_CONTENT')).toBeNull()
  })

  it('已登录渲染受保护内容', () => {
    mockUseAuth.useAuth.mockReturnValue({ user: { username: 'admin' } })
    render(
      <MemoryRouter initialEntries={['/monitor']}>
        <Routes>
          <Route path="/login" element={<div>LOGIN_PAGE</div>} />
          <Route
            path="/monitor"
            element={
              <RequireAuth>
                <div>SECURE_CONTENT</div>
              </RequireAuth>
            }
          />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByText('SECURE_CONTENT')).toBeInTheDocument()
    expect(screen.queryByText('LOGIN_PAGE')).toBeNull()
  })

  it('无权限角色访问高权限页面时重定向到默认页（不显示内容）', () => {
    mockUseAuth.useAuth.mockReturnValue({ user: { username: 'duty', role: 'duty' } })
    render(
      <MemoryRouter initialEntries={['/stats']}>
        <Routes>
          <Route path="/login" element={<div>LOGIN_PAGE</div>} />
          <Route path="/monitor" element={<div>MONITOR_HOME</div>} />
          <Route
            path="/stats"
            element={
              <RequireAuth roles={['supervisor']}>
                <div>STATS_CONTENT</div>
              </RequireAuth>
            }
          />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.queryByText('STATS_CONTENT')).toBeNull()
    expect(screen.getByText('MONITOR_HOME')).toBeInTheDocument()
  })
})