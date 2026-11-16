import { useEffect, useState } from 'react'
import {
  Card,
  Row,
  Col,
  Statistic,
  Table,
  Button,
  Space,
  message,
  Tag,
  DatePicker,
  Alert,
} from 'antd'
import {
  DownloadOutlined,
  FileExcelOutlined,
  FileTextOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import dayjs from 'dayjs'
import { fetchDashboard, fetchAlarmDetails, exportData } from '../api'
import { useAuth } from '../context/AuthContext'
import { STATUS_TEXT, FIRE_TYPE_TEXT } from '../utils/constants'
import { fmtServerTime } from '../utils/time'

const { RangePicker } = DatePicker

function rangeParams(range) {
  const params = {}
  if (range && range[0]) params.from = range[0].format('YYYY-MM-DD')
  if (range && range[1]) params.to = range[1].format('YYYY-MM-DD')
  return params
}

export default function Stats() {
  const { user } = useAuth()
  const isSupervisor = user?.role === 'supervisor'
  const [dash, setDash] = useState(null)
  const [alarms, setAlarms] = useState([])
  const [alarmsTotal, setAlarmsTotal] = useState(0)
  const [exporting, setExporting] = useState('')
  const [range, setRange] = useState(null)

  useEffect(() => {
    const params = rangeParams(range)
    fetchDashboard(params)
      .then(setDash)
      .catch(() => {})
    fetchAlarmDetails(params)
      .then((r) => {
        setAlarms(r?.items || [])
        setAlarmsTotal(r?.total || 0)
      })
      .catch(() => {})
  }, [range])

  const triggerDownload = (blob, filename) => {
    const url = URL.createObjectURL(new Blob([blob]))
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  const doExport = async (type, dataType, ext) => {
    setExporting(`${type}-${dataType}`)
    try {
      const res = await exportData(type, dataType, rangeParams(range))
      triggerDownload(res.data, `消防导出_${new Date().toISOString().slice(0, 10)}.${ext}`)
      message.success('导出成功')
    } catch (e) {
      message.error('导出失败')
    } finally {
      setExporting('')
    }
  }

  const stats = dash
    ? [
        { label: '报警总数', value: dash.alarm_total, color: '#f5222d' },
        { label: '确认真实', value: dash.alarm_true, color: '#fa541c' },
        { label: '误报', value: dash.alarm_false, color: '#faad14' },
        { label: '设备总数', value: dash.device_total, color: '#1677ff' },
        { label: '联动预案', value: dash.plan_total, color: '#722ed1' },
        { label: '消防演练', value: dash.drill_total, color: '#13c2c2' },
        { label: '应急处置', value: dash.emergency_total, color: '#eb2f96' },
      ]
    : []

  const pieOption = {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [
      {
        type: 'pie',
        radius: ['40%', '65%'],
        data: (dash?.device_status
          ? ['normal', 'alarm', 'fault', 'masked'].map((k) => ({
              name: STATUS_TEXT[k],
              value: dash.device_status[k] || 0,
              itemStyle: { color: { normal: '#52c41a', alarm: '#f5222d', fault: '#fa8c16', masked: '#bfbfbf' }[k] },
            }))
          : []
        ).filter((d) => d.value > 0),
        label: { formatter: '{b}: {c}' },
      },
    ],
  }

  const trendOption = {
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: (dash?.alarm_trend || []).map((t) => t.date.slice(5)) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        type: 'line',
        smooth: true,
        areaStyle: {},
        data: (dash?.alarm_trend || []).map((t) => t.count),
        itemStyle: { color: '#f5222d' },
      },
    ],
  }

  const ringOption = (label, value) => ({
    tooltip: { formatter: '{a}<br/>{b}: {c}%' },
    series: [
      {
        name: label,
        type: 'gauge',
        startAngle: 210,
        endAngle: -30,
        radius: '90%',
        progress: { show: true, width: 18 },
        axisLine: { lineStyle: { width: 18 } },
        axisTick: { show: false },
        axisLabel: { show: false },
        pointer: { show: false },
        anchor: { show: false },
        detail: { valueAnimation: true, formatter: '{value}%', fontSize: 22, offsetCenter: [0, '20%'] },
        data: [{ value: value || 0 }],
      },
    ],
  })

  const alarmColumns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '设备编号', dataIndex: 'device_no', width: 100, render: (v) => v || '-' },
    { title: '设备名称', dataIndex: 'device_name', render: (v) => v || '-' },
    {
      title: '火灾类型',
      dataIndex: 'fire_type',
      width: 100,
      render: (v) => (v ? FIRE_TYPE_TEXT[v] || v : '-'),
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
      width: 100,
      render: (s) => {
        const map = { pending: ['gold', '待确认'], confirmed_real: ['red', '真实'], confirmed_false: ['default', '误报'] }
        const [c, t] = map[s] || ['default', s]
        return <Tag color={c}>{t}</Tag>
      },
    },
    { title: '误报原因', dataIndex: 'false_reason', ellipsis: true, render: (v) => v || '-' },
  ]

  if (!dash) {
    return <div className="page-container"><Card loading /></div>
  }

  return (
    <div className="page-container">
      <Row gutter={[16, 16]}>
        {stats.map((s) => (
          <Col span={3} key={s.label}>
            <Card style={{ background: '#fff', textAlign: 'center' }}>
              <Statistic title={s.label} value={s.value} valueStyle={{ color: s.color, fontSize: 22 }} />
            </Card>
          </Col>
        ))}
        <Col span={3} />
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={8}>
          <Card title="设备状态分布" size="small">
            <ReactECharts option={pieOption} style={{ height: 260 }} />
          </Card>
        </Col>
        <Col xs={24} md={16}>
          <Card title="近30天报警趋势" size="small">
            <ReactECharts option={trendOption} style={{ height: 260 }} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={12}>
          <Card title={`误报率 ${dash.false_alarm_rate}%`} size="small">
            <ReactECharts option={ringOption('误报率', dash.false_alarm_rate)} style={{ height: 200 }} />
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title={`巡检完成率 ${dash.patrol_done_rate}%`} size="small">
            <ReactECharts option={ringOption('巡检完成率', dash.patrol_done_rate)} style={{ height: 200 }} />
          </Card>
        </Col>
      </Row>

      <Card title="报警明细" size="small" style={{ marginTop: 16, background: '#fff' }}>
        <div className="toolbar">
          <Space wrap>
            <RangePicker
              value={range}
              onChange={setRange}
              style={{ width: 260 }}
              placeholder={['开始日期', '结束日期']}
            />
          </Space>
        </div>
        {!isSupervisor && (
          <Alert
            style={{ marginBottom: 12 }}
            type="warning"
            showIcon
            message="导出功能仅主管可用"
          />
        )}
        {isSupervisor && (
          <div className="toolbar">
            <Space wrap>
              <Button
                icon={<FileExcelOutlined />}
                type="primary"
                onClick={() => doExport('excel', 'alarms', 'xlsx')}
                loading={exporting === 'excel-alarms'}
              >
                导出报警Excel
              </Button>
              <Button
                icon={<FileTextOutlined />}
                onClick={() => doExport('csv', 'alarms', 'csv')}
                loading={exporting === 'csv-alarms'}
              >
                导出报警CSV
              </Button>
              <Button
                icon={<DownloadOutlined />}
                onClick={() => doExport('excel', 'patrols', 'xlsx')}
                loading={exporting === 'excel-patrols'}
              >
                导出巡检Excel
              </Button>
              <Button
                icon={<DownloadOutlined />}
                onClick={() => doExport('excel', 'drills', 'xlsx')}
                loading={exporting === 'excel-drills'}
              >
                导出演练Excel
              </Button>
            </Space>
          </div>
        )}
        <Table rowKey="id" size="small" columns={alarmColumns} dataSource={alarms} pagination={{ pageSize: 10, total: alarmsTotal }} />
      </Card>
    </div>
  )
}