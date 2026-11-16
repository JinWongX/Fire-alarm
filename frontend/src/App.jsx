import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import RequireAuth from './components/RequireAuth'
import MainLayout from './components/MainLayout'
import { ROLE_BY_PATH } from './utils/permissions'
import Login from './pages/Login'
import Monitor from './pages/Monitor'
import Devices from './pages/Devices'
import Alarms from './pages/Alarms'
import Plans from './pages/Plans'
import Linkage from './pages/Linkage'
import Emergencies from './pages/Emergencies'
import Patrols from './pages/Patrols'
import Repairs from './pages/Repairs'
import Drills from './pages/Drills'
import Stats from './pages/Stats'
import Users from './pages/Users'

function HomeRedirect() {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  return <Navigate to="/monitor" replace />
}

const guarded = (roles, element) => <RequireAuth roles={roles}>{element}</RequireAuth>

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <MainLayout />
          </RequireAuth>
        }
      >
        <Route index element={<HomeRedirect />} />
        <Route path="monitor" element={guarded(ROLE_BY_PATH['/monitor'], <Monitor />)} />
        <Route path="devices" element={guarded(ROLE_BY_PATH['/devices'], <Devices />)} />
        <Route path="alarms" element={guarded(ROLE_BY_PATH['/alarms'], <Alarms />)} />
        <Route path="plans" element={guarded(ROLE_BY_PATH['/plans'], <Plans />)} />
        <Route path="linkage" element={guarded(ROLE_BY_PATH['/linkage'], <Linkage />)} />
        <Route path="emergencies" element={guarded(ROLE_BY_PATH['/emergencies'], <Emergencies />)} />
        <Route path="patrols" element={guarded(ROLE_BY_PATH['/patrols'], <Patrols />)} />
        <Route path="repairs" element={guarded(ROLE_BY_PATH['/repairs'], <Repairs />)} />
        <Route path="drills" element={guarded(ROLE_BY_PATH['/drills'], <Drills />)} />
        <Route path="stats" element={guarded(ROLE_BY_PATH['/stats'], <Stats />)} />
        <Route path="users" element={guarded(ROLE_BY_PATH['/users'], <Users />)} />
      </Route>
      <Route path="*" element={<Navigate to="/monitor" replace />} />
    </Routes>
  )
}