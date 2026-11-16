import { useEffect, useState } from 'react'
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Modal,
  Form,
  Input,
  Select,
  Switch,
  message,
  Popconfirm,
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, PlayCircleOutlined } from '@ant-design/icons'
import {
  fetchPlans,
  createPlan,
  updatePlan,
  deletePlan,
  executePlan,
  fetchAreas,
} from '../api'
import {
  ACTION_TYPES,
  ACTION_TEXT,
  FIRE_TYPES,
  FIRE_TYPE_TEXT,
} from '../utils/constants'
import { fmtServerTime } from '../utils/time'

export default function Plans() {
  const [plans, setPlans] = useState([])
  const [areas, setAreas] = useState([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [actions, setActions] = useState([])
  const [saving, setSaving] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [execResult, setExecResult] = useState(null)
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const [p, a] = await Promise.all([fetchPlans(), fetchAreas()])
      setPlans(p)
      setAreas(a)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setActions([])
    setOpen(true)
  }

  const openEdit = (record) => {
    setEditing(record)
    form.setFieldsValue({
      name: record.name,
      area_id: record.area_id,
      fire_type: record.fire_type || 'ordinary',
      enabled: record.enabled !== false,
    })
    setActions(record.actions || [])
    setOpen(true)
  }

  const addAction = () => {
    setActions((prev) => [...prev, { action_type: undefined }])
  }

  const removeAction = (idx) => {
    setActions((prev) => prev.filter((_, i) => i !== idx))
  }

  const changeActionType = (idx, value) => {
    setActions((prev) =>
      prev.map((a, i) => {
        if (i !== idx) return a
        // 重新选择时重置 action_name 为对应动作文案
        return { action_type: value, action_name: ACTION_TEXT[value] }
      }),
    )
  }

  const onSave = async () => {
    let values
    try {
      values = await form.validateFields()
    } catch {
      return
    }
    const validActions = actions
      .filter((a) => a.action_type)
      .map((a) => ({ action_type: a.action_type, action_name: ACTION_TEXT[a.action_type] || a.action_type }))
    if (validActions.length === 0) {
      message.warning('至少需要一条联动动作')
      return
    }
    const payload = {
      name: values.name,
      area_id: values.area_id ?? null,
      fire_type: values.fire_type,
      enabled: values.enabled ?? true,
      actions: validActions,
    }
    setSaving(true)
    try {
      if (editing) {
        await updatePlan(editing.id, payload)
        message.success('预案已更新')
      } else {
        await createPlan(payload)
        message.success('预案已创建')
      }
      setOpen(false)
      load()
    } catch (e) {
      message.error(e.response?.data?.detail || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const onDelete = async (record) => {
    try {
      await deletePlan(record.id)
      message.success('已删除')
      load()
    } catch (e) {
      message.error(e.response?.data?.detail || '删除失败')
    }
  }

  const onExecute = async (record) => {
    setExecuting(true)
    try {
      const res = await executePlan(record.id)
      message.success('预案手动执行成功')
      setExecResult(res.run)
    } catch (e) {
      message.error(e.response?.data?.detail || '执行失败')
    } finally {
      setExecuting(false)
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '名称', dataIndex: 'name' },
    { title: '区域', dataIndex: ['area', 'name'], render: (v) => v || '-', width: 130 },
    {
      title: '火灾类型',
      dataIndex: 'fire_type',
      width: 110,
      render: (v) => (v ? FIRE_TYPE_TEXT[v] || v : '普通'),
    },
    {
      title: '联动动作',
      render: (_, r) => (
        <Space size={4} wrap>
          {(r.actions || []).map((a, i) => (
            <Tag key={i} color="blue">
              {a.action_name || ACTION_TEXT[a.action_type] || a.action_type}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '启用',
      dataIndex: 'enabled',
      width: 80,
      render: (v) => (v ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>),
    },
    {
      title: '操作',
      width: 220,
      render: (_, record) => (
        <Space size="small">
          <Button size="small" icon={<PlayCircleOutlined />} loading={executing} onClick={() => onExecute(record)}>
            手动执行
          </Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm title="确认删除该预案？" onConfirm={() => onDelete(record)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div className="page-container">
      <Card style={{ background: '#fff' }}>
        <div className="toolbar">
          <div style={{ flex: 1 }} />
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新增预案
          </Button>
        </div>
        <Table rowKey="id" loading={loading} columns={columns} dataSource={plans} pagination={false} />
      </Card>

      <Modal
        title={editing ? '编辑预案' : '新增预案'}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={onSave}
        confirmLoading={saving}
        width={560}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="预案名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input />
          </Form.Item>
          <Space size="large">
            <Form.Item name="area_id" label="适用区域">
              <Select allowClear style={{ width: 190 }} placeholder="选择区域" options={areas.map((a) => ({ value: a.id, label: a.name }))} />
            </Form.Item>
            <Form.Item name="fire_type" label="火灾类型" initialValue="ordinary">
              <Select style={{ width: 160 }} options={FIRE_TYPES.map((t) => ({ value: t, label: FIRE_TYPE_TEXT[t] }))} />
            </Form.Item>
          </Space>
          <Form.Item label="联动动作">
            <Space direction="vertical" style={{ width: '100%' }}>
              {actions.map((a, idx) => (
                <Space key={idx} style={{ width: '100%' }}>
                  <Select
                    style={{ width: 260 }}
                    placeholder="选择联动动作"
                    value={a.action_type}
                    onChange={(v) => changeActionType(idx, v)}
                    options={ACTION_TYPES.map((t) => ({ value: t, label: ACTION_TEXT[t] }))}
                  />
                  <Button danger type="text" onClick={() => removeAction(idx)}>
                    移除
                  </Button>
                </Space>
              ))}
              <Button type="dashed" block onClick={addAction}>
                + 添加联动动作
              </Button>
            </Space>
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="预案执行结果"
        open={!!execResult}
        footer={null}
        onCancel={() => setExecResult(null)}
      >
        {execResult && (
          <div>
            <p>
              联动执行 ID：<b>{execResult.id}</b>
            </p>
            <p>
              状态：
              <Tag color={execResult.status === 'success' ? 'green' : 'orange'}>{execResult.status}</Tag>
            </p>
            <p>触发方式：{execResult.trigger_type === 'manual' ? '手动执行' : '自动触发'}</p>
            <p>
              触发时间：
              {execResult.trigger_at ? fmtServerTime(execResult.trigger_at) : '-'}
            </p>
            <p style={{ color: '#666' }}>
              联动执行明细可前往“联动执行记录”页面查看每个动作的结果。
            </p>
          </div>
        )}
      </Modal>
    </div>
  )
}