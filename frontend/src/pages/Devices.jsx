import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Select,
  Input,
  Drawer,
  Form,
  InputNumber,
  DatePicker,
  message,
  Popconfirm,
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useAuth } from '../context/AuthContext'
import {
  fetchDevices,
  fetchAreas,
  createDevice,
  updateDevice,
  updateDeviceStatus,
  deleteDevice,
} from '../api'
import {
  DEVICE_TYPES,
  DEVICE_TYPE_TEXT,
  STATUS_COLOR,
  STATUS_TEXT,
  PAGE_SIZE,
} from '../utils/constants'

export default function Devices() {
  const { user } = useAuth()
  const isSupervisor = user?.role === 'supervisor'
  const [data, setData] = useState({ total: 0, items: [] })
  const [areas, setAreas] = useState([])
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState({ device_type: undefined, status: undefined, keyword: '', page: 1 })
  const [keywordInput, setKeywordInput] = useState('')
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()
  const debounceRef = useRef(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = {
        page: filters.page,
        page_size: PAGE_SIZE,
      }
      if (filters.device_type) params.device_type = filters.device_type
      if (filters.status) params.status = filters.status
      if (filters.keyword) params.keyword = filters.keyword
      const res = await fetchDevices(params)
      setData(res)
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    load()
    fetchAreas().then(setAreas).catch(() => {})
  }, [load])

  useEffect(() => () => clearTimeout(debounceRef.current), [])

  const onKeywordChange = (e) => {
    const val = e.target.value
    setKeywordInput(val)
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setFilters((f) => ({ ...f, keyword: val.trim(), page: 1 }))
    }, 300)
  }

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setOpen(true)
  }

  const openEdit = (record) => {
    setEditing(record)
    form.setFieldsValue({
      device_no: record.device_no,
      name: record.name,
      device_type: record.device_type,
      area_id: record.area_id,
      x: record.x,
      y: record.y,
      install_date: record.install_date ? dayjs(record.install_date) : null,
      status: record.status,
      remark: record.remark,
    })
    setOpen(true)
  }

  const onSave = async () => {
    let values
    try {
      values = await form.validateFields()
    } catch {
      return
    }
    const payload = {
      ...values,
      install_date: values.install_date ? values.install_date.format('YYYY-MM-DD') : null,
      area_id: values.area_id ?? null,
      x: values.x ?? null,
      y: values.y ?? null,
    }
    setSaving(true)
    try {
      if (editing) {
        await updateDevice(editing.id, payload)
        message.success('设备已更新')
      } else {
        await createDevice(payload)
        message.success('设备已创建')
      }
      setOpen(false)
      load()
    } catch (e) {
      message.error(e.response?.data?.detail || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const onChangeStatus = async (record, status) => {
    try {
      await updateDeviceStatus(record.id, status)
      message.success('状态已更新')
      load()
    } catch (e) {
      message.error(e.response?.data?.detail || '更新失败')
    }
  }

  const onDelete = async (record) => {
    try {
      await deleteDevice(record.id)
      message.success('已删除')
      load()
    } catch (e) {
      message.error(e.response?.data?.detail || '删除失败')
    }
  }

  const columns = [
    { title: '编号', dataIndex: 'device_no', width: 90 },
    { title: '名称', dataIndex: 'name' },
    {
      title: '类型',
      dataIndex: 'device_type',
      width: 120,
      render: (t) => DEVICE_TYPE_TEXT[t] || t,
    },
    { title: '区域', dataIndex: ['area', 'name'], render: (v) => v || '-', width: 110 },
    { title: '坐标', width: 90, render: (_, r) => `${r.x ?? '-'}, ${r.y ?? '-'}` },
    { title: '安装日期', dataIndex: 'install_date', width: 110, render: (v) => v || '-' },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (s) => <Tag color={STATUS_COLOR[s] || 'default'}>{STATUS_TEXT[s] || s}</Tag>,
    },
    {
      title: '操作',
      width: 200,
      render: (_, record) => (
        <Space size="small">
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Select
            size="small"
            style={{ width: 84 }}
            value={record.status}
            onChange={(s) => onChangeStatus(record, s)}
            options={['normal', 'alarm', 'fault', 'masked'].map((s) => ({
              value: s,
              label: STATUS_TEXT[s],
            }))}
          />
          {isSupervisor && (
            <Popconfirm title="确认删除该设备？" onConfirm={() => onDelete(record)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
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
            placeholder="按类型过滤"
            style={{ width: 140 }}
            value={filters.device_type}
            onChange={(v) => setFilters((f) => ({ ...f, device_type: v, page: 1 }))}
            options={DEVICE_TYPES.map((t) => ({ value: t, label: DEVICE_TYPE_TEXT[t] }))}
          />
          <Select
            allowClear
            placeholder="按状态过滤"
            style={{ width: 120 }}
            value={filters.status}
            onChange={(v) => setFilters((f) => ({ ...f, status: v, page: 1 }))}
            options={['normal', 'alarm', 'fault', 'masked'].map((s) => ({
              value: s,
              label: STATUS_TEXT[s],
            }))}
          />
          <Input.Search
            placeholder="搜索名称/编号/区域"
            allowClear
            value={keywordInput}
            onChange={onKeywordChange}
            style={{ width: 220 }}
          />
          <div style={{ flex: 1 }} />
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新增设备
          </Button>
        </div>
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={data.items}
          pagination={{
            current: filters.page,
            pageSize: PAGE_SIZE,
            total: data.total,
            showSizeChanger: false,
            onChange: (p) => setFilters((f) => ({ ...f, page: p })),
          }}
        />
      </Card>

      <Drawer
        title={editing ? '编辑设备' : '新增设备'}
        width={420}
        open={open}
        onClose={() => setOpen(false)}
        extra={
          <Space>
            <Button onClick={() => setOpen(false)}>取消</Button>
            <Button type="primary" loading={saving} onClick={onSave}>
              保存
            </Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item name="device_no" label="设备编号" rules={[{ required: true, message: '请输入设备编号' }]}>
            <Input disabled={!!editing} placeholder="如 D-001" />
          </Form.Item>
          <Form.Item name="name" label="设备名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="device_type" label="设备类型" rules={[{ required: true }]}>
            <Select options={DEVICE_TYPES.map((t) => ({ value: t, label: DEVICE_TYPE_TEXT[t] }))} />
          </Form.Item>
          <Form.Item name="area_id" label="所属区域">
            <Select allowClear placeholder="选择区域" options={areas.map((a) => ({ value: a.id, label: a.name }))} />
          </Form.Item>
          <Space size="large">
            <Form.Item
              name="x"
              label="X 坐标"
              extra="0~100，地图中的百分比位置，超出范围会被自动修正"
            >
              <InputNumber min={0} max={100} style={{ width: 130 }} />
            </Form.Item>
            <Form.Item
              name="y"
              label="Y 坐标"
              extra="0~100，地图中的百分比位置，超出范围会被自动修正"
            >
              <InputNumber min={0} max={100} style={{ width: 130 }} />
            </Form.Item>
          </Space>
          <Form.Item name="install_date" label="安装日期">
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="status" label="状态" initialValue="normal">
            <Select
              options={['normal', 'alarm', 'fault', 'masked'].map((s) => ({
                value: s,
                label: STATUS_TEXT[s],
              }))}
            />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Drawer>
    </div>
  )
}