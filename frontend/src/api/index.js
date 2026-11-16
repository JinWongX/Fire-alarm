import client from './client'

// Auth
export const login = (username, password) =>
  client.post('/auth/login', { username, password }).then((r) => r.data)

// Areas
export const fetchAreas = () => client.get('/areas').then((r) => r.data)

// Devices
export const fetchDevices = (params) =>
  client.get('/devices', { params }).then((r) => r.data)
export const createDevice = (data) =>
  client.post('/devices', data).then((r) => r.data)
export const updateDevice = (id, data) =>
  client.put(`/devices/${id}`, data).then((r) => r.data)
export const updateDeviceStatus = (id, status) =>
  client.put(`/devices/${id}/status`, { status }).then((r) => r.data)
export const deleteDevice = (id) =>
  client.delete(`/devices/${id}`).then((r) => r.data)

// Alarms
export const simulateAlarm = (data) =>
  client.post('/alarms/simulate', data).then((r) => r.data)
export const fetchAlarms = (params) =>
  client.get('/alarms', { params }).then((r) => r.data)
export const confirmAlarm = (id, data) =>
  client.post(`/alarms/${id}/confirm`, data).then((r) => r.data)

// Plans
export const fetchPlanActions = () => client.get('/plans/actions').then((r) => r.data)
export const fetchPlans = () => client.get('/plans').then((r) => r.data)
export const createPlan = (data) => client.post('/plans', data).then((r) => r.data)
export const updatePlan = (id, data) =>
  client.put(`/plans/${id}`, data).then((r) => r.data)
export const deletePlan = (id) => client.delete(`/plans/${id}`).then((r) => r.data)
export const executePlan = (id) => client.post(`/plans/${id}/execute`).then((r) => r.data)

// Linkage
export const fetchRuns = (params) =>
  client.get('/linkage/runs', { params }).then((r) => r.data)
export const fetchRunDetail = (id) =>
  client.get(`/linkage/runs/${id}`).then((r) => r.data)

// Emergencies
export const fetchEmergencies = () => client.get('/emergencies').then((r) => r.data)
export const fetchEmergency = (id) => client.get(`/emergencies/${id}`).then((r) => r.data)
export const createEmergency = (data) =>
  client.post('/emergencies', data).then((r) => r.data)
export const addEmergencyRecord = (id, data) =>
  client.post(`/emergencies/${id}/records`, data).then((r) => r.data)
export const closeEmergency = (id, data) =>
  client.post(`/emergencies/${id}/close`, data).then((r) => r.data)

// Patrols
export const fetchPatrols = () => client.get('/patrols').then((r) => r.data)
export const fetchPatrolSummary = () =>
  client.get('/patrols/summary').then((r) => r.data)
export const createPatrol = (data) => client.post('/patrols', data).then((r) => r.data)
export const submitPatrolResult = (id, data) =>
  client.post(`/patrols/${id}/result`, data).then((r) => r.data)

// Repairs
export const fetchRepairs = () => client.get('/repairs').then((r) => r.data)
export const createRepair = (data) => client.post('/repairs', data).then((r) => r.data)
export const startRepair = (id) => client.post(`/repairs/${id}/start`).then((r) => r.data)
export const finishRepair = (id, data) =>
  client.post(`/repairs/${id}/finish`, data).then((r) => r.data)

// Drills
export const fetchDrills = () => client.get('/drills').then((r) => r.data)
export const createDrill = (data) => client.post('/drills', data).then((r) => r.data)
export const updateDrill = (id, data) =>
  client.put(`/drills/${id}`, data).then((r) => r.data)
export const deleteDrill = (id) => client.delete(`/drills/${id}`).then((r) => r.data)
export const finishDrill = (id, data) =>
  client.post(`/drills/${id}/finish`, data).then((r) => r.data)

// Stats（from/to 为可选时间筛选）
export const fetchDashboard = (params) =>
  client.get('/stats/dashboard', { params }).then((r) => r.data)
export const fetchAlarmDetails = (params) =>
  client.get('/stats/alarms', { params }).then((r) => r.data)
export const exportData = (type, dataType, params) =>
  client.get('/stats/export', { params: { type, data: dataType, ...params }, responseType: 'blob' })

// Users（仅 supervisor）
export const fetchUsers = () => client.get('/users').then((r) => r.data)
export const createUser = (data) => client.post('/users', data).then((r) => r.data)
export const updateUser = (id, data) =>
  client.put(`/users/${id}`, data).then((r) => r.data)
export const resetUserPassword = (id, data) =>
  client.post(`/users/${id}/reset_password`, data).then((r) => r.data)