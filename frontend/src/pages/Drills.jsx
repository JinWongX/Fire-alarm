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
  DatePicker,
  InputNumber,
  message,
  Popconfirm,
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, CheckCircleOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import {
  fetchDrills,
  createDrill,
  updateDrill,
  deleteDrill,
  finishDrill,
  fetchAreas,
} from '../api'

const statusColor = {
  planned: 'blue',
  done: 'green',
}

const statusText = {
  planned: '待开展',
  done: '已完成',
}

export default function Drills() {
  const [list, setList] = useState([])
  const [areas, setAreas] = useState([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()
  const [finishTarget, setFinishTarget] = useState(null)
  const [finishForm] = Form.useForm()
  const [finishing, setFinishing] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [d, a] = await Promise.all([fetchDrills(), fetchAreas()])
      setList(d)
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
    setOpen(true)
  }

  const openEdit = (record) => {
    setEditing(record)
    form.setFieldsValue({
      title: record.title,
      drill_type: record.drill_type,
      area_id: record.area_id,
      plan_date: record.plan_date ? dayjs(record.plan_date) : null,
      duration: record.duration ?? null,
      organizer: record.organizer,
      participants: record.participants,
      process: record.process,
    })
    setOpen(true)
  }

  const onSave = async () => {
    let v
    try {
      v = await form.validateFields()
    } catch {
      return
    }
    const payload = {
      ...v,
      area_id: v.area_id ?? null,
      plan_date: v.plan_date ? v.plan_date.format('YYYY-MM-DD') : null,
      duration: v.duration ?? null,
    }
    setSaving(true)
    try {
      if (editing) {
        await updateDrill(editing.id, payload)
        message.success('演练已更新')
      } else {
        await createDrill(payload)
        message.success('演练已创建')
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
      await deleteDrill(record.id)
      message.success('已删除')
      load()
    } catch (e) {
      message.error(e.response?.data?.detail || '删除失败')
    }
  }

  const openFinish = (record) => {
    setFinishTarget(record)
    finishForm.resetFields()
  }

  const onFinish = async () => {
    let v
    try {
      v = await finishForm.validateFields()
    } catch {
      return
    }
    setFinishing(true)
    try {
      await finishDrill(finishTarget.id, {
        score: v.score ?? null,
        evaluate: v.evaluate,
        summary: v.summary,
      })
      message.success('演练已完成')
      setFinishTarget(null)
      load()
    } catch (e) {
      message.error(e.response?.data?.detail || '操作失败')
    } finally {
      setFinishing(false)
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '标题', dataIndex: 'title' },
    { title: '类型', dataIndex: 'drill_type', width: 100, render: (v) => v || '-' },
    { title: '区域', dataIndex: ['area', 'name'], width: 120, render: (v) => v || '-' },
    { title: '计划日期', dataIndex: 'plan_date', width: 110, render: (v) => v || '-' },
    { title: '时长(分)', dataIndex: 'duration', width: 90, render: (v) => v ?? '-' },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (s) => <Tag color={statusColor[s] || 'default'}>{statusText[s] || s}</Tag>,
    },
    { title: '评分', dataIndex: 'score', width: 80, render: (v) => v ?? '-' },
    { title: '评估', dataIndex: 'evaluate', ellipsis: true, render: (v) => v || '-' },
    {
      title: '操作',
      width: 180,
      render: (_, record) => (
        <Space size="small">
          <Button size="small" icon={<CheckCircleOutlined />} onClick={() => openFinish(record)} disabled={record.status === 'done'}>
            完成演练
          </Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm title="确认删除该演练？" onConfirm={() => onDelete(record)}>
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
            新增演练
          </Button>
        </div>
        <Table rowKey="id" loading={loading} columns={columns} dataSource={list} pagination={false} />
      </Card>

      <Modal
        title={editing ? '编辑演练' : '新增演练'}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={onSave}
        confirmLoading={saving}
        width={560}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}>
            <Input />
          </Form.Item>
          <Space size="large">
            <Form.Item name="drill_type" label="演练类型" initialValue="疏散演练">
              <Select
                style={{ width: 180 }}
                options={['疏散演练', '灭火演练', '联动测试'].map((t) => ({ value: t, label: t }))}
              />
            </Form.Item>
            <Form.Item name="area_id" label="区域">
              <Select allowClear style={{ width: 180 }} placeholder="选择区域" options={areas.map((a) => ({ value: a.id, label: a.name }))} />
            </Form.Item>
          </Space>
          <Form.Item name="plan_date" label="计划日期">
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            name="duration"
            label="时长（分钟）"
            rules={[{ type: 'number', min: 0, message: '时长不能为负数' }]}
          >
            <InputNumber min={0} style={{ width: '100%' }} placeholder="演练时长（分钟）" />
          </Form.Item>
          <Space size="large">
            <Form.Item name="organizer" label="组织者">
              <Input style={{ width: 190 }} />
            </Form.Item>
            <Form.Item name="participants" label="参与人员">
              <Input style={{ width: 190 }} />
            </Form.Item>
          </Space>
          <Form.Item name="process" label="演练流程">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`完成演练 · #${finishTarget?.id || ''}`}
        open={!!finishTarget}
        onCancel={() => setFinishTarget(null)}
        onOk={onFinish}
        confirmLoading={finishing}
        okText="确认完成"
      >
        <Form form={finishForm} layout="vertical">
          <Form.Item
            name="score"
            label="评分（0-100）"
            rules={[{ type: 'number', min: 0, max: 100, message: '评分需在 0-100 之间' }]}
          >
            <InputNumber min={0} max={100} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="evaluate" label="评估">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="summary" label="总结">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}