import { Layout, Menu, Dropdown, Space, Tag } from 'antd'
import {
  DashboardOutlined,
  ExperimentOutlined,
  ThunderboltOutlined,
  AlertOutlined,
  ApartmentOutlined,
  SettingOutlined,
  SafetyCertificateOutlined,
  ToolOutlined,
  FileDoneOutlined,
  BarChartOutlined,
  LogoutOutlined,
  UserOutlined,
  TeamOutlined,
  FireOutlined,
} from '@ant-design/icons'
import { useMemo } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ROLE_TEXT } from '../utils/constants'
import { ROLE_BY_PATH } from '../utils/permissions'

const { Sider, Header, Content } = Layout

export const menuConfig = [
  { key: '/monitor', icon: <DashboardOutlined />, label: '实时监控', roles: ROLE_BY_PATH['/monitor'] },
  { key: '/devices', icon: <ApartmentOutlined />, label: '设备档案', roles: ROLE_BY_PATH['/devices'] },
  { key: '/alarms', icon: <AlertOutlined />, label: '报警管理', roles: ROLE_BY_PATH['/alarms'] },
  { key: '/plans', icon: <SafetyCertificateOutlined />, label: '联动预案', roles: ROLE_BY_PATH['/plans'] },
  { key: '/linkage', icon: <ThunderboltOutlined />, label: '联动执行记录', roles: ROLE_BY_PATH['/linkage'] },
  { key: '/emergencies', icon: <ExperimentOutlined />, label: '应急处置', roles: ROLE_BY_PATH['/emergencies'] },
  { key: '/patrols', icon: <SettingOutlined />, label: '设备巡检', roles: ROLE_BY_PATH['/patrols'] },
  { key: '/repairs', icon: <ToolOutlined />, label: '维修管理', roles: ROLE_BY_PATH['/repairs'] },
  { key: '/drills', icon: <FileDoneOutlined />, label: '消防演练', roles: ROLE_BY_PATH['/drills'] },
  { key: '/stats', icon: <BarChartOutlined />, label: '统计报表', roles: ROLE_BY_PATH['/stats'] },
  { key: '/users', icon: <TeamOutlined />, label: '用户管理', roles: ROLE_BY_PATH['/users'] },
]

export default function MainLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuth()

  const items = useMemo(() => {
    if (!user) return []
    return menuConfig
      .filter((m) => m.roles.includes(user.role))
      .map((m) => ({ key: m.key, icon: m.icon, label: m.label }))
  }, [user])

  const selectedKey = items.find((i) => location.pathname.startsWith(i.key))
    ? location.pathname
    : '/monitor'

  const userMenu = {
    items: [
      {
        key: 'logout',
        icon: <LogoutOutlined />,
        label: '退出登录',
        onClick: () => {
          logout()
          navigate('/login')
        },
      },
    ],
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider theme="dark" width={220}>
        <div
          style={{
            height: 56,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontWeight: 700,
            fontSize: 16,
            gap: 8,
            background: '#001529',
          }}
        >
          <FireOutlined style={{ color: '#ff4d4f' }} />
          <span>消防联动控制</span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={items}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            boxShadow: '0 1px 4px rgba(0,21,41,.08)',
            height: 56,
            lineHeight: '56px',
          }}
        >
          <div style={{ fontWeight: 600, color: '#001529' }}>消防报警联动控制系统</div>
          {user && (
            <Dropdown menu={userMenu} placement="bottomRight">
              <Space style={{ cursor: 'pointer' }}>
                <UserOutlined />
                <span>{user.real_name || user.username}</span>
                <Tag color="blue" style={{ marginInlineEnd: 0 }}>
                  {ROLE_TEXT[user.role] || user.role}
                </Tag>
              </Space>
            </Dropdown>
          )}
        </Header>
        <Content style={{ margin: 16, overflow: 'auto', background: '#f0f2f5' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}