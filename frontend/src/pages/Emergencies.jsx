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
  message,
  Descriptions,
  List,
  Timeline,
} from 'antd'
import { PlusOutlined, EyeOutlined } from '@ant-design/icons'
import {
  fetchEmergencies,
  fetchEmergency,
  createEmergency,
  addEmergencyRecord,
  closeEmergency,
  fetchAlarms,
} from '../api'
import { FIRE_TYPE_TEXT } from '../utils/constants'
import { fmtServerTime } from '../utils/time'

export default function Emergencies() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState(undefined)
  const [pendingAlarms, setPendingAlarms] = useState([])
  const [createOpen, setCreateOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createForm] = Form.useForm()
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [recordOpen, setRecordOpen] = useState(false)
  const [recordForm] = Form.useForm()
  const [recordLoading, setRecordLoading] = useState(false)
  const [closeOpen, setCloseOpen] = useState(false)
  const [closeForm] = Form.useForm()
  const [closeLoading, setCloseLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetchEmergencies()
      setList(res)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    fetchAlarms({ status: 'pending', page: 1, page_size: 100 })
      .then((r) => setPendingAlarms(r.items || []))
      .catch(() => {})
  }, [load])

  const filtered = list.filter((e) => (status ? e.status === status : true))

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
      await createEmergency(v)
      message.success('处置单已创建')
      setCreateOpen(false)
      load()
    } catch (e) {
      message.error(e.response?.data?.detail || '创建失败')
    } finally {
      setCreating(false)
    }
  }

  const openDetail = async (record) => {
    setDetail(null)
    setDetailLoading(true)
    try {
      const res = await fetchEmergency(record.id)
      setDetail(res)
    } catch (e) {
      message.error(e.response?.data?.detail || '加载详情失败')
    } finally {
      setDetailLoading(false)
    }
  }

  const openAddRecord = () => {
    recordForm.resetFields()
    setRecordOpen(true)
  }

  const onAddRecord = async () => {
    let v
    try {
      v = await recordForm.validateFields()
    } catch {
      return
    }
    setRecordLoading(true)
    try {
      await addEmergencyRecord(detail.id, v)
      message.success('处置记录已添加')
      setRecordOpen(false)
      const res = await fetchEmergency(detail.id)
      setDetail(res)
    } catch (e) {
      message.error(e.response?.data?.detail || '添加失败')
    } finally {
      setRecordLoading(false)
    }
  }

  const openClose = () => {
    closeForm.resetFields()
    setCloseOpen(true)
  }

  const onClose = async () => {
    let v
    try {
      v = await closeForm.validateFields()
    } catch {
      return
    }
    setCloseLoading(true)
    try {
      await closeEmergency(detail.id, { result: v.result })
      message.success('已闭环')
      setCloseOpen(false)
      setDetail(null)
      load()
    } catch (e) {
      message.error(e.response?.data?.detail || '闭环失败')
    } finally {
      setCloseLoading(false)
    }
  }

  const showDetailRecords = () => {
    setRecordOpen(true)
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '标题', dataIndex: 'title' },
    {
      title: '关联报警',
      dataIndex: 'alarm_id',
      width: 100,
      render: (v) => (v ? `报警 #${v}` : '-'),
    },
    {
      title: '开始时间',
      dataIndex: 'start_at',
      width: 170,
      render: (v) => (v ? fmtServerTime(v) : '-'),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (s) =>
        s === 'active' ? <Tag color="red">处置中</Tag> : <Tag color="green">已闭环</Tag>,
    },
    { title: '处置结果', dataIndex: 'result', ellipsis: true, render: (v) => v || '-' },
    {
      title: '操作',
      width: 100,
      render: (_, r) => (
        <Button size="small" icon={<EyeOutlined />} onClick={() => openDetail(r)}>
          详情
        </Button>
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
            options={[
              { value: 'active', label: '处置中' },
              { value: 'closed', label: '已闭环' },
            ]}
          />
          <div style={{ flex: 1 }} />
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新增处置单
          </Button>
        </div>
        <Table rowKey="id" loading={loading} columns={columns} dataSource={filtered} pagination={false} />
      </Card>

      <Modal
        title="新增处置单"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={onCreate}
        confirmLoading={creating}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item name="alarm_id" label="关联报警（待确认）">
            <Select
              allowClear
              placeholder="选择待确认报警"
              options={pendingAlarms.map((a) => ({
                value: a.id,
                label: `#${a.id} ${a.device?.name || ''}（${FIRE_TYPE_TEXT[a.fire_type] || a.fire_type}）`,
              }))}
            />
          </Form.Item>
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}>
            <Input placeholder="如：A区一层消防处置" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`应急处置详情 #${detail?.id || ''}`}
        open={!!detail && !recordOpen}
        footer={
          detail?.status === 'active'
            ? [
                <Button key="record" onClick={showDetailRecords}>
                  添加处置记录
                </Button>,
                <Button key="close" type="primary" danger onClick={openClose}>
                  闭环（结束处置）
                </Button>,
              ]
            : null
        }
        onCancel={() => setDetail(null)}
        loading={detailLoading}
        width={680}
      >
        {detail && (
          <div>
            <Descriptions size="small" bordered column={2}>
              <Descriptions.Item label="标题" span={2}>
                {detail.title}
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                {detail.status === 'active' ? <Tag color="red">处置中</Tag> : <Tag color="green">已闭环</Tag>}
              </Descriptions.Item>
              <Descriptions.Item label="关联报警">
                {detail.alarm ? `#${detail.alarm.id} ${detail.alarm.device?.name || ''}` : '无'}
              </Descriptions.Item>
              <Descriptions.Item label="开始时间" span={2}>
                {detail.start_at ? fmtServerTime(detail.start_at) : '-'}
              </Descriptions.Item>
              {detail.closed_at && (
                <Descriptions.Item label="闭环时间" span={2}>
                  {fmtServerTime(detail.closed_at)}（{detail.closed_by}）
                </Descriptions.Item>
              )}
              {detail.result && (
                <Descriptions.Item label="处置结果" span={2}>
                  {detail.result}
                </Descriptions.Item>
              )}
            </Descriptions>
            <h4 style={{ marginTop: 16 }}>处置记录（{detail.records?.length || 0}）</h4>
            <Timeline
              items={(detail.records || []).map((r) => ({
                children: (
                  <div>
                    <div>
                      <b>@{r.time || '-'}</b> · {r.person || '-'}
                    </div>
                    <div>{r.content}</div>
                  </div>
                ),
              }))}
            />
          </div>
        )}
      </Modal>

      <Modal
        title={`添加处置记录 · #${detail?.id || ''}`}
        open={recordOpen}
        onCancel={() => setRecordOpen(false)}
        onOk={onAddRecord}
        confirmLoading={recordLoading}
      >
        <Form form={recordForm} layout="vertical">
          <Form.Item name="time" label="时间" rules={[{ required: true, message: '请输入时间' }]}>
            <Input placeholder="如：2025-09-25 10:30" />
          </Form.Item>
          <Form.Item name="content" label="内容" rules={[{ required: true, message: '请输入内容' }]}>
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="person" label="人员">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`闭环处置 #${detail?.id || ''}`}
        open={closeOpen}
        onCancel={() => setCloseOpen(false)}
        onOk={onClose}
        confirmLoading={closeLoading}
        okText="确认闭环"
        okButtonProps={{ danger: true }}
      >
        <Form form={closeForm} layout="vertical">
          <Form.Item name="result" label="处置结果" rules={[{ required: true, message: '请填写处置结果' }]}>
            <Input.TextArea rows={4} placeholder="填写本次处置的最终结果" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}