import { useCallback, useEffect, useState } from 'react'
import { Card, Table, Button, Space, Tag, Modal, Descriptions, List, message } from 'antd'
import { fetchRuns, fetchRunDetail } from '../api'
import { FIRE_TYPE_TEXT, ACTION_TEXT } from '../utils/constants'
import { fmtServerTime } from '../utils/time'

const runStatusColor = {
  success: 'green',
  partial: 'orange',
  failed: 'red',
}

export default function Linkage() {
  const [data, setData] = useState({ total: 0, items: [] })
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetchRuns({ page, page_size: 10 })
      setData(res)
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => {
    load()
  }, [load])

  const openDetail = async (record) => {
    setDetail(null)
    setDetailLoading(true)
    try {
      const res = await fetchRunDetail(record.id)
      setDetail(res)
    } catch (e) {
      message.error(e.response?.data?.detail || '加载详情失败')
    } finally {
      setDetailLoading(false)
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    {
      title: '触发方式',
      dataIndex: 'trigger_type',
      width: 100,
      render: (v) =>
        v === 'auto' ? <Tag color="blue">自动</Tag> : <Tag color="purple">手动</Tag>,
    },
    {
      title: '预案名称',
      dataIndex: 'plan_name',
      render: (v) => v || '-',
    },
    {
      title: '关联报警',
      render: (_, r) =>
        r.alarm ? (
          <span>
            报警 #{r.alarm.id}
            {r.alarm.fire_type ? `（${FIRE_TYPE_TEXT[r.alarm.fire_type] || r.alarm.fire_type}）` : ''}
          </span>
        ) : (
          '-'
        ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (v) => <Tag color={runStatusColor[v] || 'default'}>{v}</Tag>,
    },
    {
      title: '触发时间',
      dataIndex: 'trigger_at',
      width: 170,
      render: (v) => (v ? fmtServerTime(v) : '-'),
    },
    {
      title: '操作',
      width: 90,
      render: (_, record) => (
        <Button size="small" onClick={() => openDetail(record)}>
          详情
        </Button>
      ),
    },
  ]

  return (
    <div className="page-container">
      <Card style={{ background: '#fff' }}>
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={data.items}
          pagination={{
            current: page,
            pageSize: 10,
            total: data.total,
            showSizeChanger: false,
            onChange: setPage,
          }}
        />
      </Card>

      <Modal
        title={`联动执行详情 #${detail?.id || ''}`}
        open={!!detail}
        footer={null}
        onCancel={() => setDetail(null)}
        width={640}
        loading={detailLoading}
      >
        {detail && (
          <div>
            <Descriptions size="small" bordered column={2}>
              <Descriptions.Item label="触发方式">
                {detail.trigger_type === 'auto' ? '自动触发' : '手动执行'}
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={runStatusColor[detail.status] || 'default'}>{detail.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="预案名称" span={2}>
                {detail.plan_name || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="触发时间" span={2}>
                {detail.trigger_at ? fmtServerTime(detail.trigger_at) : '-'}
              </Descriptions.Item>
            </Descriptions>
            <h4 style={{ marginTop: 16 }}>联动动作（{detail.results?.length || 0}）</h4>
            <List
              size="small"
              dataSource={detail.results || []}
              renderItem={(r) => (
                <List.Item>
                  <Space>
                    <Tag color="blue">{r.action_name || ACTION_TEXT[r.action_type] || r.action_type}</Tag>
                    <Tag color={r.status === 'success' ? 'green' : 'orange'}>{r.status}</Tag>
                    <span style={{ color: '#666' }}>{r.detail}</span>
                  </Space>
                </List.Item>
              )}
            />
          </div>
        )}
      </Modal>
    </div>
  )
}