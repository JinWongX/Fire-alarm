import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Card,
  Row,
  Col,
  Statistic,
  List,
  Tag,
  Select,
  Form,
  Button,
  message,
  Modal,
  Alert,
  Space,
  Empty,
  Descriptions,
} from 'antd'
import {
  fetchDevices,
  fetchAreas,
  fetchAlarms,
  simulateAlarm,
} from '../api'
import {
  STATUS_COLOR,
  STATUS_TEXT,
  DEVICE_TYPES,
  DEVICE_TYPE_ABBR,
  DEVICE_TYPE_TEXT,
  ACTION_TEXT,
  FIRE_TYPES,
  FIRE_TYPE_TEXT,
  ALARM_STATUS_TEXT,
  ALARM_STATUS_COLOR,
} from '../utils/constants'
import { fmtServerTime } from '../utils/time'
import { WarningOutlined, SafetyOutlined, ToolOutlined, EyeInvisibleOutlined } from '@ant-design/icons'

const W = 900
const H = 480

const statusIcon = {
  normal: <SafetyOutlined />,
  alarm: <WarningOutlined />,
  fault: <ToolOutlined />,
  masked: <EyeInvisibleOutlined />,
}

export default function Monitor() {
  const [devices, setDevices] = useState({ total: 0, items: [] })
  const [areas, setAreas] = useState([])
  const [alarms, setAlarms] = useState({ total: 0, items: [] })
  const [simForm] = Form.useForm()
  const [simLoading, setSimLoading] = useState(false)
  const [simResult, setSimResult] = useState(null)
  const [areaFilter, setAreaFilter] = useState(undefined)
  const [typeFilter, setTypeFilter] = useState(undefined)
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState(false)
  const timerRef = useRef(null)

  const load = async () => {
    try {
      const [d, a, al] = await Promise.all([
        fetchDevices({ page: 1, page_size: 500 }),
        fetchAreas(),
        fetchAlarms({ page: 1, page_size: 10 }),
      ])
      setDevices(d)
      setAreas(a)
      setAlarms(al)
      setError(false)
    } catch (e) {
      setError(true)
      /* 401 handled by interceptor */
    }
  }

  useEffect(() => {
    load()
    const onVisibilityChange = () => {
      if (document.hidden) {
        clearInterval(timerRef.current)
      } else {
        clearInterval(timerRef.current)
        timerRef.current = setInterval(load, 3000)
        load()
      }
    }
    timerRef.current = setInterval(load, 3000)
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => {
      clearInterval(timerRef.current)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [])

  const count = useMemo(() => {
    const c = { normal: 0, alarm: 0, fault: 0, masked: 0 }
    devices.items.forEach((d) => {
      if (c[d.status] !== undefined) c[d.status] += 1
      else c.normal += 1
    })
    return c
  }, [devices])

  const areaDevices = useMemo(() => {
    const shownAreas = areaFilter ? areas.filter((a) => a.id === areaFilter) : areas
    return shownAreas.map((area) => ({
      area,
      devices: devices.items.filter(
        (d) =>
          d.area_id === area.id &&
          (!typeFilter || d.device_type === typeFilter),
      ),
    }))
  }, [areas, devices, areaFilter, typeFilter])

  const simulate = async (values) => {
    setSimLoading(true)
    try {
      const res = await simulateAlarm({ ...values, scene: values.scene || '' })
      message.success('模拟报警触发成功')
      setSimResult(res)
    } catch (e) {
      message.error(e.response?.data?.detail || '模拟报警失败')
    } finally {
      setSimLoading(false)
    }
  }

  // 网格化均衡排布：以设备序号为主分配行列，x/y 仅作轻微抖动，
  // 保证同区域内设备均匀散开、互不重叠（与底层坐标分布无关）。
  const layoutDevices = (ds, x0, y0, w, h) => {
    const n = ds.length
    if (!n) return []
    const cols = Math.max(1, Math.ceil(Math.sqrt((n * w) / h)))
    const rows = Math.ceil(n / cols)
    const cw = w / cols
    const ch = h / rows
    return ds.map((d, i) => {
      const col = i % cols
      const row = Math.floor(i / cols)
      const jx = ((((d.x ?? 20) * 31) % 100) / 100) - 0.5
      const jy = ((((d.y ?? 20) * 17) % 100) / 100) - 0.5
      return {
        d,
        px: Math.round(x0 + col * cw + cw / 2 + jx * cw * 0.4),
        py: Math.round(y0 + row * ch + ch / 2 + jy * ch * 0.4),
      }
    })
  }

  const renderMap = () => {
    if (areaDevices.length === 0) {
      return <Empty style={{ marginTop: 160 }} description="暂无区域数据" />
    }
    const zones = areaDevices.length
    const cols = zones > 4 ? Math.ceil(zones / 2) : zones
    const rows = Math.ceil(zones / cols)
    const cw = W / cols
    const ch = H / rows
    const m = 14
    const headerH = 28
    return (
      <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }} role="img" aria-label="电子地图">
        <defs>
          <linearGradient id="floorFill" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#fbfdfe" />
            <stop offset="100%" stopColor="#e8f0f6" />
          </linearGradient>
        </defs>
        {/* 建筑外墙 */}
        <rect x="3" y="3" width={W - 6} height={H - 6} rx="12" fill="#e9eff4" stroke="#27394c" strokeWidth="3" />
        <rect x="12" y="12" width={W - 24} height={H - 24} rx="6" fill="none" stroke="#8fa9bd" strokeWidth="1" strokeDasharray="5 4" />

        {areaDevices.map(({ area, devices: ds }, idx) => {
          const col = idx % cols
          const row = Math.floor(idx / cols)
          const x = col * cw
          const y = row * ch
          const zoneW = cw - 2 * m
          const zoneH = ch - 2 * m
          const zx = x + m
          const zy = y + m
          const innerX = zx + 12
          const innerY = zy + headerH + 12
          const innerW = zoneW - 24
          const innerH = zoneH - headerH - 12 - 16
          const placed = layoutDevices(ds, innerX, innerY, innerW, innerH)

          return (
            <g key={area.id}>
              {/* 房间外墙 */}
              <rect x={zx} y={zy} width={zoneW} height={zoneH} rx="9" fill="url(#floorFill)" stroke="#5b7287" strokeWidth="2" />
              {/* 房间名标牌 */}
              <rect x={zx} y={zy} width={zoneW} height={headerH} rx="9" fill="#2f5d86" />
              <rect x={zx} y={zy + headerH - 6} width={zoneW} height="6" fill="#2f5d86" />
              <text x={zx + 14} y={zy + 19} fontSize="14" fontWeight="700" fill="#fff">
                {area.name} · 设备 {ds.length} 台
              </text>
              {/* 隔间/走廊分隔虚线 */}
              <line x1={innerX} y1={innerY - 4} x2={zx + zoneW - 12} y2={innerY - 4} stroke="#b9c8d4" strokeWidth="1" strokeDasharray="2 3" />
              <line x1={innerX} y1={zy + zoneH - 14} x2={zx + zoneW - 12} y2={zy + zoneH - 14} stroke="#b9c8d4" strokeWidth="1" strokeDasharray="2 3" />
              {/* 门洞 */}
              <path d={`M${zx + 8} ${zy + headerH + 8} h18`} stroke="#94a7b5" strokeWidth="2" fill="none" />
              {/* 设备点位 */}
              {placed.map(({ d, px, py }) => {
                const color = STATUS_COLOR[d.status] || STATUS_COLOR.normal
                return (
                  <g
                    key={d.id}
                    onClick={() => setSelected(d)}
                    style={{ cursor: 'pointer' }}
                    className="device-node"
                  >
                    <circle cx={px} cy={py} r="12" fill="transparent" />
                    <circle cx={px} cy={py} r="9" fill={color} opacity="0.9" stroke="#fff" strokeWidth="1.5" />
                    <text x={px} y={py + 3.5} textAnchor="middle" fontSize="10" fill="#fff" fontWeight="600">
                      {DEVICE_TYPE_ABBR[d.device_type] || '•'}
                    </text>
                    <title>{`${d.name}（${DEVICE_TYPE_TEXT[d.device_type] || d.device_type}） ${STATUS_TEXT[d.status]}`}</title>
                  </g>
                )
              })}
            </g>
          )
        })}
      </svg>
    )
  }

  return (
    <div className="monitor-layout">
      {error && (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="监控数据加载失败"
          description="请检查网络或后端服务后刷新页面重试。"
        />
      )}
      <div>
        <Card size="small" title="设备状态" className="stat-card" style={{ marginBottom: 16 }}>
          <Row gutter={[8, 8]}>
            {['normal', 'alarm', 'fault', 'masked'].map((s) => (
              <Col span={12} key={s}>
                <Card size="small" style={{ textAlign: 'center', borderLeft: `4px solid ${STATUS_COLOR[s]}` }}>
                  <Statistic
                    title={STATUS_TEXT[s]}
                    value={count[s] || 0}
                    valueStyle={{ color: STATUS_COLOR[s], fontSize: 22 }}
                    prefix={statusIcon[s]}
                  />
                </Card>
              </Col>
            ))}
          </Row>
        </Card>

        <Card size="small" title="模拟报警" className="stat-card">
          <Form form={simForm} layout="vertical" onFinish={simulate} initialValues={{ fire_type: 'ordinary' }}>
            <Form.Item label="设备" name="device_id" rules={[{ required: true, message: '请选择设备' }]}>
              <Select
                showSearch
                optionFilterProp="label"
                placeholder="选择要触发报警的设备"
                options={devices.items.map((d) => ({
                  value: d.id,
                  label: `${d.name}（${DEVICE_TYPE_TEXT[d.device_type] || d.device_type}）`,
                }))}
              />
            </Form.Item>
            <Form.Item label="火灾类型" name="fire_type" rules={[{ required: true, message: '请选择火灾类型' }]}>
              <Select
                placeholder="选择火灾类型"
                options={FIRE_TYPES.map((t) => ({ value: t, label: FIRE_TYPE_TEXT[t] }))}
              />
            </Form.Item>
            <Form.Item label="现场描述" name="scene">
              <Select
                allowClear
                placeholder="选择现场场景"
                options={[
                  { value: '走廊烟雾弥漫', label: '走廊烟雾弥漫' },
                  { value: '配电箱冒烟', label: '配电箱冒烟' },
                  { value: '厨房起火', label: '厨房起火' },
                ]}
              />
            </Form.Item>
            <Button type="primary" htmlType="submit" loading={simLoading} block danger>
              触发模拟报警
            </Button>
          </Form>
        </Card>
      </div>

      <Card
        size="small"
        title="电子地图 · 重点区域监控"
        extra={
          <span>
            {['normal', 'alarm', 'fault', 'masked'].map((s) => (
              <span key={s} style={{ marginRight: 12, fontSize: 12 }}>
                <span
                  style={{
                    display: 'inline-block',
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    background: STATUS_COLOR[s],
                    marginRight: 4,
                  }}
                />
                {STATUS_TEXT[s]}
              </span>
            ))}
          </span>
        }
      >
        <div className="toolbar" style={{ marginBottom: 12 }}>
          <Select
            allowClear
            placeholder="按区域查看"
            style={{ width: 180 }}
            value={areaFilter}
            onChange={setAreaFilter}
            options={areas.map((a) => ({ value: a.id, label: a.name }))}
          />
          <Select
            allowClear
            placeholder="按设备类型筛选"
            style={{ width: 200 }}
            value={typeFilter}
            onChange={setTypeFilter}
            options={DEVICE_TYPES.map((t) => ({ value: t, label: DEVICE_TYPE_TEXT[t] }))}
          />
        </div>
        <div className="map-container">{renderMap()}</div>
      </Card>

      <Card size="small" title="最新报警（最近10条）" className="stat-card">
        {alarms.items.length === 0 ? (
          <Empty description="暂无报警" />
        ) : (
          <List
            size="small"
            dataSource={alarms.items}
            renderItem={(a) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <Space small>
                      <span>{a.device?.name || `设备#${a.device_id}`}</span>
                      <Tag color={ALARM_STATUS_COLOR[a.status] || undefined}>
                        {ALARM_STATUS_TEXT[a.status] || a.status}
                      </Tag>
                    </Space>
                  }
                  description={
                    <div style={{ fontSize: 12 }}>
                      <div>{a.device?.area?.name || '未知区域'}</div>
                      <div>
                        {FIRE_TYPE_TEXT[a.fire_type] || a.fire_type} ·{' '}
                        {a.trigger_at ? fmtServerTime(a.trigger_at) : '-'}
                      </div>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>

      <Modal
        title="联动执行结果"
        open={!!simResult}
        footer={null}
        onCancel={() => setSimResult(null)}
        width={620}
      >
        {simResult && (
          <div>
            <Alert
              type="success"
              showIcon
              message="模拟报警已触发"
              description={
                <div>
                  <p>
                    报警单：{simResult.alarm?.device?.name} ·{' '}
                    {FIRE_TYPE_TEXT[simResult.alarm?.fire_type] || simResult.alarm?.fire_type}
                  </p>
                  {simResult.linkage_run ? (
                    <p>
                      联动执行 ID：{simResult.linkage_run.id} · 状态：
                      <Tag color={simResult.linkage_run.status === 'success' ? 'green' : 'orange'}>
                        {simResult.linkage_run.status}
                      </Tag>
                      {simResult.linkage_run.trigger_type === 'auto' ? '（自动触发）' : '（手动触发）'}
                    </p>
                  ) : (
                    <p>未匹配到启用预案，未触发联动。</p>
                  )}
                </div>
              }
            />
            <p style={{ marginTop: 16, color: '#666' }}>
              联动执行明细可前往“联动执行记录”页面查看每个动作的结果。
            </p>
          </div>
        )}
      </Modal>

      <Modal
        title={`设备详情 · ${selected?.name || ''}`}
        open={!!selected}
        footer={null}
        onCancel={() => setSelected(null)}
      >
        {selected && (
          <Descriptions bordered size="small" column={1}>
            <Descriptions.Item label="设备名称">{selected.name}</Descriptions.Item>
            <Descriptions.Item label="设备类型">
              {DEVICE_TYPE_TEXT[selected.device_type] || selected.device_type || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={STATUS_COLOR[selected.status] || undefined}>
                {STATUS_TEXT[selected.status] || selected.status}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="坐标">
              {selected.x ?? '-'}, {selected.y ?? '-'}
            </Descriptions.Item>
            <Descriptions.Item label="所属区域">
              {areas.find((a) => a.id === selected.area_id)?.name || '-'}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  )
}