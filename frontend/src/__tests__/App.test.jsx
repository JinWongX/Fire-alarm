import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const mockUseAuth = vi.hoisted(() => ({ useAuth: vi.fn() }))

vi.mock('../context/AuthContext', () => mockUseAuth)

async function pageMock(name) {
  const { jsx } = await import('react/jsx-runtime')
  return {
    default: () => jsx('div', { 'data-testid': `page-${name}`, children: `PAGE_${name}` }),
  }
}

vi.mock('../pages/Login', async () => pageMock('Login'))
vi.mock('../pages/Monitor', async () => pageMock('Monitor'))
vi.mock('../pages/Devices', async () => pageMock('Devices'))
vi.mock('../pages/Alarms', async () => pageMock('Alarms'))
vi.mock('../pages/Plans', async () => pageMock('Plans'))
vi.mock('../pages/Linkage', async () => pageMock('Linkage'))
vi.mock('../pages/Emergencies', async () => pageMock('Emergencies'))
vi.mock('../pages/Patrols', async () => pageMock('Patrols'))
vi.mock('../pages/Repairs', async () => pageMock('Repairs'))
vi.mock('../pages/Drills', async () => pageMock('Drills'))
vi.mock('../pages/Stats', async () => pageMock('Stats'))
vi.mock('../pages/Users', async () => pageMock('Users'))

import App from '../App'

function renderAt(route, user) {
  mockUseAuth.useAuth.mockReturnValue({ user })
  return render(
    <MemoryRouter initialEntries={[route]}>
      <App />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockUseAuth.useAuth.mockReset()
})

describe('App 路由', () => {
  it('已登录访问 / 时经 HomeRedirect 进入受保护布局（user 存在分支）', async () => {
    renderAt('/', { user: { username: 'admin', role: 'supervisor' } })
    expect(await screen.findByText('消防联动控制')).toBeInTheDocument()
  })

  it('未登录访问 / 时跳转到 /login（HomeRedirect 不存在 user 分支）', () => {
    renderAt('/', null)
    expect(screen.getByTestId('page-Login')).toBeInTheDocument()
  })

  it('已登录打开受保护子路由时守卫放行并渲染布局', async () => {
    renderAt('/devices', { user: { username: 'admin', role: 'supervisor' } })
    expect(await screen.findByText('消防联动控制')).toBeInTheDocument()
  })

  it('/login 直接渲染登录页', () => {
    renderAt('/login', null)
    expect(screen.getByTestId('page-Login')).toBeInTheDocument()
  })

  it('未知路径命中 * 兜底并重定向到受保护布局', async () => {
    renderAt('/no-such-path', { user: { username: 'admin', role: 'supervisor' } })
    expect(await screen.findByText('消防联动控制')).toBeInTheDocument()
  })
})