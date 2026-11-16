export const STATUS_COLOR = {
  normal: '#52c41a',
  alarm: '#f5222d',
  fault: '#fa8c16',
  masked: '#bfbfbf',
}

export const STATUS_TEXT = {
  normal: '正常',
  alarm: '报警',
  fault: '故障',
  masked: '屏蔽',
}

export const DEVICE_TYPES = [
  'smoke',
  'temp',
  'manual',
  'hydrant',
  'sprinkler',
  'smoke_exhaust',
  'fire_door',
  'emergency_light',
]

export const DEVICE_TYPE_TEXT = {
  smoke: '烟感探测器',
  temp: '温感探测器',
  manual: '手动报警按钮',
  hydrant: '消火栓',
  sprinkler: '喷淋头',
  smoke_exhaust: '排烟风机',
  fire_door: '防火门',
  emergency_light: '应急照明',
}

export const DEVICE_TYPE_ABBR = {
  smoke: '烟',
  temp: '温',
  manual: '手',
  hydrant: '栓',
  sprinkler: '喷',
  smoke_exhaust: '排',
  fire_door: '门',
  emergency_light: '照',
}

export const ACTION_TYPES = [
  'smoke_exhaust',
  'fire_door',
  'emergency_light',
  'broadcast',
]

export const ACTION_TEXT = {
  smoke_exhaust: '启动排烟',
  fire_door: '关闭防火门',
  emergency_light: '启动应急照明',
  broadcast: '疏散广播',
}

export const FIRE_TYPES = ['electrical', 'ordinary', 'oil', 'other']

export const FIRE_TYPE_TEXT = {
  electrical: '电气火灾',
  ordinary: '普通火灾',
  oil: '油类火灾',
  other: '其他',
}

export const ALARM_STATUS_TEXT = {
  pending: '待确认',
  confirmed_real: '确认真实',
  confirmed_false: '误报',
}

export const ALARM_STATUS_COLOR = {
  pending: '#faad14',
  confirmed_real: '#52c41a',
  confirmed_false: '#bfbfbf',
}

export const ROLE_TEXT = {
  duty: '值班员',
  maintenance: '维保员',
  supervisor: '主管',
}

export const PAGE_SIZE = 10