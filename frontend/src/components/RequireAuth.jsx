import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { DEFAULT_HOME } from '../utils/permissions'

export default function RequireAuth({ children, roles }) {
  const { user } = useAuth()
  const location = useLocation()
  // 校验登录令牌：未登录跳转登录页
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  // 校验角色：无权限访问高权限页面时重定向（不显示内容）
  if (roles && !roles.includes(user.role)) {
    return <Navigate to={DEFAULT_HOME} replace />
  }
  return children
}