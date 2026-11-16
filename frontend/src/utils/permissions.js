// 单源角色权限：路径 -> 允许访问的角色列表
// 与后端角色体系对齐（supervisor 主管 / duty 值班员 / maintenance 维保员）
// 统计看板与导出仅 supervisor；预案/演练/用户管理仅 supervisor
export const ROLE_BY_PATH = {
  '/monitor': ['duty', 'maintenance', 'supervisor'],
  '/devices': ['duty', 'maintenance', 'supervisor'],
  '/alarms': ['duty', 'supervisor'],
  '/plans': ['supervisor'],
  '/linkage': ['duty', 'supervisor'],
  '/emergencies': ['duty', 'supervisor'],
  '/patrols': ['maintenance', 'supervisor'],
  '/repairs': ['maintenance', 'supervisor'],
  '/drills': ['supervisor'],
  '/stats': ['supervisor'],
  '/users': ['supervisor'],
}

// 首页默认跳转：无权限访问时的回退路径
export const DEFAULT_HOME = '/monitor'