import { useCallback, useEffect, useState } from 'react'
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Select,
  Modal,
  Form,
  Input,
  Switch,
  message,
} from 'antd'
import {
  PlusOutlined,
  EditOutlined,
  KeyOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import {
  fetchUsers,
  createUser,
  updateUser,
  resetUserPassword,
} from '../api'
import { ROLE_TEXT } from '../utils/constants'

const roleOptions = Object.keys(ROLE_TEXT).map((r) => ({ value: r, label: ROLE_TEXT[r] }))

export default function Users() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createForm] = Form.useForm()
  const [editTarget, setEditTarget] = useState(null)
  const [editForm] = Form.useForm()
  const [editing, setEditing] = useState(false)
  const [pwTarget, setPwTarget] = useState(null)
  const [pwForm] = Form.useForm()
  const [pwSaving, setPwSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetchUsers()
      setList(Array.isArray(res) ? res : res?.items || [])
    } catch (e) {
      message.error(e.response?.data?.detail || '加载用户失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const openCreate = () => {
    createForm.resetFields()
    setCreateOpen(true)
  }

  const onCreate = async () => {
    let v
    try {
      v = await createForm.validateFields()
    } catch {
      return
    }
    setCreating(true)
    try {
      await createUser({
        username: v.username,
        real_name: v.real_name ?? '',
        role: v.role,
        password: v.password,
      })
      message.success('用户已创建')
      setCreateOpen(false)
      load()
    } catch (e) {
      message.error(e.response?.data?.detail || '创建失败')
    } finally {
      setCreating(false)
    }
  }

  const openEdit = (record) => {
    setEditTarget(record)
    editForm.setFieldsValue({ role: record.role, is_active: record.is_active !== false })
    setEditing(true)
  }

  const onEdit = async () => {
    let v
    try {
      v = await editForm.validateFields()
    } catch {
      return
    }
    setEditing(false)
    try {
      await updateUser(editTarget.id, { role: v.role, is_active: v.is_active })
      message.success('用户已更新')
      setEditTarget(null)
      load()
    } catch (e) {
      message.error(e.response?.data?.detail || '更新失败')
    }
  }

  const openPw = (record) => {
    setPwTarget(record)
    pwForm.resetFields()
  }

  const onPw = async () => {
    let v
    try {
      v = await pwForm.validateFields()
    } catch {
      return
    }
    setPwSaving(true)
    try {
      await resetUserPassword(pwTarget.id, { password: v.password })
      message.success('密码已重置')
      setPwTarget(null)
    } catch (e) {
      message.error(e.response?.data?.detail || '重置失败')
    } finally {
      setPwSaving(false)
    }
  }

  const toggleActive = async (record, checked) => {
    try {
      await updateUser(record.id, { is_active: checked })
      message.success('用户状态已更新')
      load()
    } catch (e) {
      message.error(e.response?.data?.detail || '更新失败')
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '用户名', dataIndex: 'username', width: 140 },
    { title: '姓名', dataIndex: 'real_name', width: 120, render: (v) => v || '-' },
    {
      title: '角色',
      dataIndex: 'role',
      width: 110,
      render: (v) => <Tag color="blue">{ROLE_TEXT[v] || v}</Tag>,
    },
    {
      title: '启用状态',
      dataIndex: 'is_active',
      width: 100,
      render: (v, record) => (
        <Switch
          checked={v !== false}
          checkedChildren="启用"
          unCheckedChildren="停用"
          onChange={(checked) => toggleActive(record, checked)}
        />
      ),
    },
    {
      title: '操作',
      width: 200,
      render: (_, record) => (
        <Space size="small">
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Button size="small" icon={<KeyOutlined />} onClick={() => openPw(record)}>
            重置密码
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <div className="page-container">
      <Card style={{ background: '#fff' }}>
        <div className="toolbar">
          <Button icon={<ReloadOutlined />} onClick={load} style={{ marginRight: 8 }}>
            刷新
          </Button>
          <div style={{ flex: 1 }} />
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新增用户
          </Button>
        </div>
        <Table rowKey="id" loading={loading} columns={columns} dataSource={list} pagination={false} />
      </Card>

      <Modal
        title="新增用户"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={onCreate}
        confirmLoading={creating}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input placeholder="登录账号" />
          </Form.Item>
          <Form.Item name="real_name" label="姓名">
            <Input placeholder="真实姓名（可选）" />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true, message: '请选择角色' }]}>
            <Select options={roleOptions} placeholder="选择角色" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少 6 位' },
            ]}
          >
            <Input.Password placeholder="至少 6 位" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`编辑用户 · ${editTarget?.username || ''}`}
        open={!!editTarget}
        onCancel={() => setEditTarget(null)}
        onOk={onEdit}
        confirmLoading={editing}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="role" label="角色" rules={[{ required: true, message: '请选择角色' }]}>
            <Select options={roleOptions} />
          </Form.Item>
          <Form.Item name="is_active" label="启用" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`重置密码 · ${pwTarget?.username || ''}`}
        open={!!pwTarget}
        onCancel={() => setPwTarget(null)}
        onOk={onPw}
        confirmLoading={pwSaving}
      >
        <Form form={pwForm} layout="vertical">
          <Form.Item
            name="password"
            label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 6, message: '密码至少 6 位' },
            ]}
          >
            <Input.Password placeholder="至少 6 位" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}