import { useCallback, useEffect, useState } from 'react'
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Modal,
  Form,
  Select,
  Input,
  DatePicker,
  Row,
  Col,
  Statistic,
  message,
  Radio,
} from 'antd'
import { PlusOutlined, EditOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import {
  fetchPatrols,
  fetchPatrolSummary,
  createPatrol,
  submitPatrolResult,
  fetchDevices,
  fetchAreas,
} from '../api'
import { STATUS_COLOR } from '../utils/constants'
import { fmtServerTime } from '../utils/time'

const statusColor = {
  pending: 'gold',
  normal: 'green',
  abnormal: 'red',
}

const statusText = {
  pending: '待巡检',
  normal: '正常',
  abnormal: '异常',
}

export default function Patrols() {
  const [list, setList] = useState([])
  const [summary, setSummary] = useState({ total: 0, done: 0, abnormal: 0, done_rate: 0 })
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState(undefined)
  const [devices, setDevices] = useState([])
  const [areas, setAreas] = useState([])
  const [createOpen, setCreateOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createForm] = Form.useForm()
  const [resultTarget, setResultTarget] = useState(null)
  const [resultForm] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [p, s] = await Promise.all([fetchPatrols(), fetchPatrolSummary()])
      setList(p)
      setSummary(s)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    fetchDevices({ page: 1, page_size: 500 })
      .then((r) => setDevices(r.items || []))
      .catch(() => {})
    fetchAreas().then(setAreas).catch(() => {})
  }, [load])

  const filtered = list.filter((p) => (status ? p.status === status : true))

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
      await createPatrol({
        device_id: v.device_id ?? null,
        area_id: v.area_id ?? null,
        scheduled_date: v.scheduled_date ? v.scheduled_date.format('YYYY-MM-DD') : null,
      })
      message.success('巡检任务已创建')
      setCreateOpen(false)
      load()
    } catch (e) {
      message.error(e.response?.data?.detail || '创建失败')
    } finally {
      setCreating(false)
    }
  }

  const openResult = (record) => {
    setResultTarget(record)
    resultForm.resetFields()
    setSubmitting(false)
  }

  const onResult = async () => {
    let v
    try {
      v = await resultForm.validateFields()
    } catch {
      return
    }
    setSubmitting(true)
    try {
      await submitPatrolResult(resultTarget.id, {
        status: v.status,
        result: v.result,
        suggest: v.suggest,
      })
      message.success(v.status === 'abnormal' ? '已记录异常，系统已自动生成维修单' : '巡检结果已提交')
      setResultTarget(null)
      load()
    } catch (e) {
      message.error(e.response?.data?.detail || '提交失败')
    } finally {
      setSubmitting(false)
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
    {
      title: '区域',
      width: 120,
      render: (_, r) => {
        const area = areas.find((a) => a.id === r.area_id)
        return area ? area.name : '-'
      },
    },
    { title: '计划日期', dataIndex: 'scheduled_date', width: 110, render: (v) => v || '-' },
    {
      title: '状态',
      dataIndex: 'status',
      width: 130,
      render: (s, record) => (
        <Space size={4}>
          <Tag color={statusColor[s] || 'default'}>{statusText[s] || s}</Tag>
          {record.overdue && <Tag color="red">逾期</Tag>}
        </Space>
      ),
    },
    { title: '巡检人', dataIndex: 'patrol_by', width: 90, render: (v) => v || '-' },
    {
      title: '巡检时间',
      dataIndex: 'patrol_time',
      width: 160,
      render: (v) => (v ? fmtServerTime(v) : '-'),
    },
    { title: '结果', dataIndex: 'result', ellipsis: true, render: (v) => v || '-' },
    {
      title: '操作',
      width: 110,
      render: (_, record) =>
        record.status === 'pending' ? (
          <Button size="small" icon={<EditOutlined />} onClick={() => openResult(record)}>
            录入结果
          </Button>
        ) : (
          <Tag color={record.status === 'normal' ? 'green' : 'red'}>
            {record.status === 'normal' ? '已巡检' : '异常'}
          </Tag>
        ),
    },
  ]

  return (
    <div className="page-container">
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card style={{ background: '#fff' }}>
            <Statistic title="巡检任务总数" value={summary.total} />
          </Card>
        </Col>
        <Col span={6}>
          <Card style={{ background: '#fff' }}>
            <Statistic title="已完成" value={summary.done} valueStyle={{ color: STATUS_COLOR.normal }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card style={{ background: '#fff' }}>
            <Statistic title="异常" value={summary.abnormal} valueStyle={{ color: '#f5222d' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card style={{ background: '#fff' }}>
            <Statistic title="完成率" value={summary.done_rate} suffix="%" />
          </Card>
        </Col>
      </Row>

      <Card style={{ background: '#fff' }}>
        <div className="toolbar">
          <Select
            allowClear
            placeholder="按状态过滤"
            style={{ width: 140 }}
            value={status}
            onChange={setStatus}
            options={['pending', 'normal', 'abnormal'].map((s) => ({
              value: s,
              label: statusText[s],
            }))}
          />
          <div style={{ flex: 1 }} />
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新增巡检任务
          </Button>
        </div>
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={filtered}
          pagination={false}
        />
      </Card>

      <Modal
        title="新增巡检任务"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={onCreate}
        confirmLoading={creating}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item name="device_id" label="巡检设备">
            <Select
              allowClear
              placeholder="选择设备"
              options={devices.map((d) => ({ value: d.id, label: d.name }))}
            />
          </Form.Item>
          <Form.Item name="area_id" label="区域">
            <Select allowClear placeholder="选择区域" options={areas.map((a) => ({ value: a.id, label: a.name }))} />
          </Form.Item>
          <Form.Item name="scheduled_date" label="计划日期">
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`录入巡检结果 · #${resultTarget?.id || ''}`}
        open={!!resultTarget}
        onCancel={() => setResultTarget(null)}
        onOk={onResult}
        confirmLoading={submitting}
        okText="提交结果"
      >
        {resultTarget && (
          <Form form={resultForm} layout="vertical" initialValues={{ status: 'normal' }}>
            <Form.Item name="status" label="结果" rules={[{ required: true }]}>
              <Radio.Group
                options={[
                  { value: 'normal', label: '正常' },
                  { value: 'abnormal', label: '异常' },
                ]}
              />
            </Form.Item>
            <Form.Item
              name="result"
              label="巡检结果说明"
              dependencies={['status']}
              rules={[
                ({ getFieldValue }) => ({
                  required: getFieldValue('status') === 'abnormal',
                  message: '异常时请填写异常说明',
                }),
              ]}
            >
              <Input.TextArea rows={3} placeholder="说明巡检情况" />
            </Form.Item>
            <Form.Item
              name="suggest"
              label="整改建议"
              dependencies={['status']}
              rules={[
                ({ getFieldValue }) => ({
                  required: getFieldValue('status') === 'abnormal',
                  message: '异常时请填写整改建议',
                }),
              ]}
            >
              <Input.TextArea rows={2} placeholder="如有异常请填写整改建议" />
            </Form.Item>
          </Form>
        )}
      </Modal>
    </div>
  )
}