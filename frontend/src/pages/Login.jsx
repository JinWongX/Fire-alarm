import { Button, Card, Form, Input, message, Typography, Space } from 'antd'
import { UserOutlined, LockOutlined, FireOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { ROLE_TEXT } from '../utils/constants'

const demoAccounts = [
  { username: 'admin', role: 'supervisor', pass: '123456' },
  { username: 'duty', role: 'duty', pass: '123456' },
  { username: 'maintain', role: 'maintenance', pass: '123456' },
]

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [form] = Form.useForm()

  const onFinish = async (values) => {
    setLoading(true)
    try {
      await login(values.username, values.password)
      message.success('登录成功')
      navigate('/monitor', { replace: true })
    } catch (e) {
      message.error(e.response?.data?.detail || '登录失败，请检查账号密码')
    } finally {
      setLoading(false)
    }
  }

  const fill = (username, password) => {
    form.setFieldsValue({ username, password })
  }

  return (
    <div
      style={{
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg,#001529 0%,#003a70 60%,#04539e 100%)',
      }}
    >
      <Card style={{ width: 380, borderRadius: 12, boxShadow: '0 12px 32px rgba(0,0,0,.2)' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <FireOutlined style={{ fontSize: 40, color: '#f5222d' }} />
          <Typography.Title level={3} style={{ marginTop: 12, marginBottom: 4 }}>
            消防报警联动控制系统
          </Typography.Title>
          <Typography.Text type="secondary">Fire Alarm Linkage Control System</Typography.Text>
        </div>
        {/* eslint-disable-next-line react/no-unstable-nested-components */}
        <Form form={form} name="login" onFinish={onFinish} size="large">
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入账号' }]}
          >
            <Input prefix={<UserOutlined />} placeholder="账号" autoComplete="username" />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
              autoComplete="current-password"
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={loading}>
              登 录
            </Button>
          </Form.Item>
        </Form>
        <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: 12 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            演示账号（点击填充）：
          </Typography.Text>
          <Space wrap style={{ marginTop: 8 }}>
            {demoAccounts.map((acc) => (
              <Button
                key={acc.username}
                size="small"
                onClick={() => {
                  fill(acc.username, acc.pass)
                }}
              >
                {ROLE_TEXT[acc.role]}({acc.username})
              </Button>
            ))}
          </Space>
        </div>
      </Card>
    </div>
  )
}