import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { message } from 'antd'

const mockUseAuth = vi.hoisted(() => ({
  useAuth: vi.fn(),
}))

vi.mock('../context/AuthContext', () => mockUseAuth)

import Login from '../pages/Login'

function setup(loginImpl) {
  const login = vi.fn(loginImpl)
  mockUseAuth.useAuth.mockReturnValue({ login })
  render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>,
  )
  return { login }
}

beforeEach(() => {
  mockUseAuth.useAuth.mockReset().mockReturnValue({ login: vi.fn() })
  vi.spyOn(message, 'success').mockImplementation(() => {})
  vi.spyOn(message, 'error').mockImplementation(() => {})
  vi.spyOn(message, 'warning').mockImplementation(() => {})
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('Login', () => {
  it('渲染登录表单（账号/密码/登录按钮）', () => {
    setup(() => Promise.resolve({}))
    expect(screen.getByPlaceholderText('账号')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('密码')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /登\s*录/ })).toBeInTheDocument()
  })

  it('提交表单时使用输入的账号密码调用 login', async () => {
    const user = userEvent.setup()
    const { login } = setup(() => Promise.resolve({ username: 'admin' }))
    await user.type(screen.getByPlaceholderText('账号'), 'admin')
    await user.type(screen.getByPlaceholderText('密码'), '123456')
    await user.click(screen.getByRole('button', { name: /登\s*录/ }))

    await waitFor(() => expect(login).toHaveBeenCalledWith('admin', '123456'))
  })

  it('登录失败时提示错误信息', async () => {
    const user = userEvent.setup()
    const err = { response: { data: { detail: '账号或密码错误' } } }
    setup(() => Promise.reject(err))
    await user.type(screen.getByPlaceholderText('账号'), 'admin')
    await user.type(screen.getByPlaceholderText('密码'), 'wrong')
    await user.click(screen.getByRole('button', { name: /登\s*录/ }))

    await waitFor(() => {
      expect(message.error).toHaveBeenCalledWith('账号或密码错误')
    })
  })

  it('点击演示账号按钮填充账号与密码', async () => {
    const user = userEvent.setup()
    setup(() => Promise.resolve({}))
    await user.click(screen.getByRole('button', { name: /值班员\(duty\)/ }))
    await waitFor(() => {
      expect(screen.getByPlaceholderText('账号')).toHaveValue('duty')
      expect(screen.getByPlaceholderText('密码')).toHaveValue('123456')
    })
  })
})