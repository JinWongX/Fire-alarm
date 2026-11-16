import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AuthProvider, useAuth } from '../context/AuthContext'

const mockApiLogin = vi.hoisted(() => vi.fn())

vi.mock('../api', () => ({
  login: (...a) => mockApiLogin(...a),
}))

function Consumer() {
  const { user, login, logout } = useAuth()
  return (
    <div>
      <span data-testid="user">{user ? user.username : 'NULL'}</span>
      <button onClick={async () => login('admin', '123')}>doLogin</button>
      <button onClick={logout}>doLogout</button>
    </div>
  )
}

beforeEach(() => {
  localStorage.clear()
  mockApiLogin.mockReset()
})

describe('AuthContext', () => {
  it('未登录态初始 user 为 null', () => {
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    )
    expect(screen.getByTestId('user')).toHaveTextContent('NULL')
  })

  it('登录成功后写入 token/user 并更新 user', async () => {
    mockApiLogin.mockResolvedValue({
      token: 'tk-1',
      user: { username: 'admin', role: 'supervisor' },
    })
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    )
    await userEvent.click(screen.getByText('doLogin'))

    expect(mockApiLogin).toHaveBeenCalledWith('admin', '123')
    expect(await screen.findByTestId('user')).toHaveTextContent('admin')
    expect(localStorage.getItem('token')).toBe('tk-1')
    expect(JSON.parse(localStorage.getItem('user')).username).toBe('admin')
  })

  it('登出后清空 storage 与 user', async () => {
    const user = { username: 'admin', role: 'supervisor' }
    localStorage.setItem('token', 'tk-1')
    localStorage.setItem('user', JSON.stringify(user))
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    )
    expect(screen.getByTestId('user')).toHaveTextContent('admin')

    await userEvent.click(screen.getByText('doLogout'))
    expect(screen.getByTestId('user')).toHaveTextContent('NULL')
    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()
  })
})