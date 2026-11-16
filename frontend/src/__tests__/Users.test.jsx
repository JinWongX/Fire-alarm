import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { message } from 'antd'

const mocks = vi.hoisted(() => ({
  fetchUsers: vi.fn(),
  createUser: vi.fn(),
  updateUser: vi.fn(),
  resetUserPassword: vi.fn(),
}))

vi.mock('../api', () => mocks)

import Users from '../pages/Users'

const users = [
  { id: 1, username: 'admin', real_name: '主管A', role: 'supervisor', is_active: true },
  { id: 2, username: 'duty', real_name: '', role: 'duty', is_active: true },
  { id: 3, username: 'off', real_name: '停用B', role: 'maintenance', is_active: false },
]

beforeEach(() => {
  mocks.fetchUsers.mockReset().mockResolvedValue(users)
  ;['createUser', 'updateUser', 'resetUserPassword'].forEach((k) =>
    mocks[k].mockReset().mockResolvedValue({}),
  )
  vi.spyOn(message, 'success').mockImplementation(() => {})
  vi.spyOn(message, 'error').mockImplementation(() => {})
})

describe('Users 用户管理', () => {
  it('渲染用户列表（用户名/姓名/角色/启用状态）', async () => {
    render(<Users />)
    expect(await screen.findByText('admin')).toBeInTheDocument()
    expect(screen.getByText('主管A')).toBeInTheDocument()
    expect(screen.getByText('值班员')).toBeInTheDocument()
    expect(screen.getByText('维保员')).toBeInTheDocument()
    expect(mocks.fetchUsers).toHaveBeenCalled()
  })

  it('新增用户提交 username/real_name/role/password', async () => {
    const user = userEvent.setup()
    render(<Users />)
    await screen.findByText('admin')

    await user.click(screen.getByRole('button', { name: /新增用户/ }))
    const dialog = await screen.findByRole('dialog')

    await user.type(within(dialog).getByPlaceholderText('登录账号'), 'newuser')
    await user.type(within(dialog).getByPlaceholderText('真实姓名（可选）'), '新用户')

    const roleSelect = screen.getByText('选择角色').closest('.ant-select')
    await user.click(roleSelect.querySelector('.ant-select-selector'))
    const dropdown = await waitFor(() => {
      const el = document.querySelector('.ant-select-dropdown:not(.ant-select-dropdown-hidden)')
      if (!el) throw new Error('dropdown not open')
      return el
    })
    const roleOption = await within(dropdown).findByText('值班员')
    await user.click(roleOption)

    await user.type(within(dialog).getByPlaceholderText('至少 6 位'), '123456')
    await user.click(dialog.querySelector('.ant-modal-footer .ant-btn-primary'))

    await waitFor(() =>
      expect(mocks.createUser).toHaveBeenCalledWith({
        username: 'newuser',
        real_name: '新用户',
        role: 'duty',
        password: '123456',
      }),
    )
  }, 180000)

  it('编辑用户时打开弹窗并回填当前角色', async () => {
    render(<Users />)
    await screen.findByText('admin')
    const adminRow = screen.getByText('admin').closest('tr')
    fireEvent.click(within(adminRow).getByRole('button', { name: /编辑/ }))
    const dialog = await screen.findByRole('dialog')
    expect(await within(dialog).findByText('主管')).toBeInTheDocument()
  })

  it('启用状态切换调用 updateUser', async () => {
    const user = userEvent.setup()
    render(<Users />)
    await screen.findByText('admin')
    await user.click(screen.getAllByRole('switch')[0])
    await waitFor(() =>
      expect(mocks.updateUser).toHaveBeenCalledWith(1, { is_active: false }),
    )
    expect(message.success).toHaveBeenCalledWith('用户状态已更新')
  })

  it('重置密码调用 resetUserPassword', async () => {
    const user = userEvent.setup()
    render(<Users />)
    await screen.findByText('admin')
    await user.click(screen.getAllByRole('button', { name: /重置密码/ })[0])
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByPlaceholderText('至少 6 位'), 'newpass1')
    await user.click(dialog.querySelector('.ant-modal-footer .ant-btn-primary'))
    await waitFor(() =>
      expect(mocks.resetUserPassword).toHaveBeenCalledWith(1, { password: 'newpass1' }),
    )
  })
})