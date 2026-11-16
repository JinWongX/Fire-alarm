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
  message,
  Typography,
  Alert,
} from 'antd'
import { useNavigate } from 'react-router-dom'
import { fetchAlarms, confirmAlarm } from '../api'
import {
  ALARM_STATUS_TEXT,
  FIRE_TYPE_TEXT,
  PAGE_SIZE,
} from '../utils/constants'
import { fmtServerTime } from '../utils/time'

const statusOptions = [
  { value: 'pending', label: '待确认' },
  { value: 'confirmed_real', label: '确认真实' },
  { value: 'confirmed_false', label: '误报' },
]

export default function Alarms() {
  const navigate = useNavigate()
  const [data, setData] = useState({ total: 0, items: [] })
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState(undefined)
  const [page, setPage] = useState(1)
  const [confirmType, setConfirmType] = useState(null) // 'true' | 'false'
  const [current, setCurrent] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [trueForm] = Form.useForm()
  const [falseForm] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, page_size: PAGE_SIZE }
      if (status) params.status = status
      const res = await fetchAlarms(params)
      setData(res)
    } finally {
      setLoading(false)
    }
  }, [page, status])

  useEffect(() => {
    load()
  }, [load])

  const openConfirm = (record, type) => {
    setCurrent(record)
    setConfirmType(type)
    if (type === 'false') falseForm.resetFields()
    else trueForm.resetFields()
  }

  const onConfirm = async () => {
    let payload
    try {
      if (confirmType === 'false') {
        const v = await falseForm.validateFields()
        payload = { result: 'false', false_reason: v.false_reason }
      } else {
        const v = await trueForm.validateFields()
        payload = { result: 'true', scene: v.scene }
      }
    } catch {
      // 校验失败：antd 已在表单中展示对应字段错误，无需提交
      return
    }
    setSubmitting(true)
    try {
      const res = await confirmAlarm(current.id, payload)
      message.success(confirmType === 'false' ? '已确认误报' : '已确认为真实报警')
      setConfirmType(null)
      load()
      if (confirmType === 'true' && res.emergency) {
        Modal.confirm({
          title: '处置单已自动创建',
          content: `系统已为该报警创建处置单：#${res.emergency.id}「${res.emergency.title}」。是否前往应急处置？`,
          okText: '前往处置',
          cancelText: '稍后',
          onOk: () => navigate('/emergencies'),
        })
      }
    } catch (e) {
      message.error(e.response?.data?.detail || '确认失败')
    } finally {
      setSubmitting(false)
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    {
      title: '设备',
      width: 200,
      render: (_, r) => r.device?.name || `设备#${r.device_id}`,
    },
    {
      title: '区域',
      width: 120,
      render: (_, r) => r.device?.area?.name || '-',
    },
    {
      title: '火灾类型',
      dataIndex: 'fire_type',
      width: 110,
      render: (v) => FIRE_TYPE_TEXT[v] || v || '-',
    },
    {
      title: '触发时间',
      dataIndex: 'trigger_at',
      width: 170,
      render: (v) => (v ? fmtServerTime(v) : '-'),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (s) => <Tag color={statusTagColor(s)}>{ALARM_STATUS_TEXT[s] || s}</Tag>,
    },
    {
      title: '现场描述',
      dataIndex: 'scene',
      ellipsis: true,
      render: (v) => v || '-',
    },
    {
      title: '误报原因',
      dataIndex: 'false_reason',
      ellipsis: true,
      render: (v) => v || '-',
    },
    {
      title: '操作',
      width: 180,
      render: (_, record) =>
        record.status === 'pending' ? (
          <Space size="small">
            <Button type="primary" size="small" onClick={() => openConfirm(record, 'true')}>
              确认真实
            </Button>
            <Button size="small" danger onClick={() => openConfirm(record, 'false')}>
              误报
            </Button>
          </Space>
        ) : (
          <Typography.Text type="secondary">{confirmText(record)}</Typography.Text>
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
            style={{ width: 160 }}
            value={status}
            onChange={(v) => {
              setStatus(v)
              setPage(1)
            }}
            options={statusOptions}
          />
        </div>
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={data.items}
          pagination={{
            current: page,
            pageSize: PAGE_SIZE,
            total: data.total,
            showSizeChanger: false,
            onChange: setPage,
          }}
        />
      </Card>

      <Modal
        title={`确认报警 #${current?.id} 为真实火灾`}
        open={confirmType === 'true'}
        onCancel={() => setConfirmType(null)}
        onOk={onConfirm}
        confirmLoading={submitting}
        okText="确认真实"
      >
        <Form form={trueForm} layout="vertical">
          {current?.scene && (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
              message={`已记录现场描述：${current.scene}`}
            />
          )}
          <Form.Item name="scene" label="现场描述 / 救火信息" rules={[{ required: true, message: '请填写现场描述' }]}>
            <Input.TextArea rows={4} placeholder="描述现场情况、火势及对应扑救措施" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`确认报警 #${current?.id} 为误报`}
        open={confirmType === 'false'}
        onCancel={() => setConfirmType(null)}
        onOk={onConfirm}
        confirmLoading={submitting}
        okText="确认为误报"
      >
        <Form form={falseForm} layout="vertical">
          <Form.Item name="false_reason" label="误报原因" rules={[{ required: true, message: '请填写误报原因' }]}>
            <Input.TextArea rows={3} placeholder="如：烹饪油烟、设备误触发等" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

function statusTagColor(s) {
  if (s === 'pending') return 'gold'
  if (s === 'confirmed_real') return 'red'
  if (s === 'confirmed_false') return 'default'
  return 'default'
}

function confirmText(r) {
  if (r.status === 'confirmed_real') return `已确认（${r.confirm_by || '-'}）`
  return '已误报'
}