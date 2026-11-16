import { useEffect, useState } from 'react'
import { Card, Table, Button, Space, Tag, Modal, Form, Input, Select, message } from 'antd'
import {
  fetchRepairs,
  startRepair,
  finishRepair,
  fetchDevices,
} from '../api'
import { fmtServerTime } from '../utils/time'

const statusColor = {
  pending: 'gold',
  in_progress: 'blue',
  done: 'green',
}

const statusText = {
  pending: '待维修',
  in_progress: '维修中',
  done: '已完成',
}

export default function Repairs() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState(undefined)
  const [devices, setDevices] = useState([])
  const [finishTarget, setFinishTarget] = useState(null)
  const [finishForm] = Form.useForm()
  const [finishing, setFinishing] = useState(false)
  const [starting, setStarting] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await fetchRepairs()
      setList(res)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    fetchDevices({ page: 1, page_size: 500 })
      .then((r) => setDevices(r.items || []))
      .catch(() => {})
  }, [])

  const filtered = list.filter((r) => (status ? r.status === status : true))

  const onStart = async (record) => {
    setStarting(true)
    try {
      await startRepair(record.id)
      message.success('维修已开始')
      load()
    } catch (e) {
      message.error(e.response?.data?.detail || '操作失败')
    } finally {
      setStarting(false)
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
      await finishRepair(finishTarget.id, { result: v.result })
      message.success('维修已完成，设备状态已恢复')
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
    {
      title: '设备',
      width: 180,
      render: (_, r) => {
        const dev = devices.find((d) => d.id === r.device_id)
        return dev ? dev.name : r.device_id ? `设备#${r.device_id}` : '-'
      },
    },
    { title: '标题', dataIndex: 'title', render: (v) => v || '-' },
    { title: '描述', dataIndex: 'description', ellipsis: true, render: (v) => v || '-' },
    { title: '创建人', dataIndex: 'creator', width: 90, render: (v) => v || '-' },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (s) => <Tag color={statusColor[s] || 'default'}>{statusText[s] || s}</Tag>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 170,
      render: (v) => (v ? fmtServerTime(v) : '-'),
    },
    { title: '结果', dataIndex: 'result', ellipsis: true, render: (v) => v || '-' },
    {
      title: '操作',
      width: 160,
      render: (_, record) => (
        <Space size="small">
          {record.status === 'pending' && (
            <Button size="small" type="primary" loading={starting} onClick={() => onStart(record)}>
              开始维修
            </Button>
          )}
          {record.status === 'in_progress' && (
            <Button size="small" type="primary" onClick={() => openFinish(record)}>
              完成维修
            </Button>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div className="page-container">
      <Card style={{ background: '#fff' }}>
        <div className="toolbar">
          <Select
            allowClear
            placeholder="按状态过滤"
            style={{ width: 140 }}
            value={status}
            onChange={setStatus}
            options={['pending', 'in_progress', 'done'].map((s) => ({
              value: s,
              label: statusText[s],
            }))}
          />
        </div>
        <Table rowKey="id" loading={loading} columns={columns} dataSource={filtered} pagination={false} />
      </Card>

      <Modal
        title={`完成维修 · #${finishTarget?.id || ''}`}
        open={!!finishTarget}
        onCancel={() => setFinishTarget(null)}
        onOk={onFinish}
        confirmLoading={finishing}
        okText="确认完成"
      >
        <Form form={finishForm} layout="vertical">
          <Form.Item name="result" label="维修结果" rules={[{ required: true, message: '请输入维修结果' }]}>
            <Input.TextArea rows={4} placeholder="填写维修结果" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}