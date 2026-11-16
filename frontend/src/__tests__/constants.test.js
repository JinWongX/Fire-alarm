import { describe, it, expect } from 'vitest'
import {
  STATUS_COLOR,
  STATUS_TEXT,
  DEVICE_TYPE_TEXT,
  DEVICE_TYPE_ABBR,
  ACTION_TEXT,
  FIRE_TYPE_TEXT,
  ALARM_STATUS_TEXT,
  ALARM_STATUS_COLOR,
  ROLE_TEXT,
} from '../utils/constants'

describe('utils/constants', () => {
  describe('STATUS_COLOR', () => {
    it('提供四种状态对应的颜色值', () => {
      expect(STATUS_COLOR.normal).toBe('#52c41a')
      expect(STATUS_COLOR.alarm).toBe('#f5222d')
      expect(STATUS_COLOR.fault).toBe('#fa8c16')
      expect(STATUS_COLOR.masked).toBe('#bfbfbf')
    })
  })

  describe('STATUS_TEXT', () => {
    it('提供中文状态文本', () => {
      expect(STATUS_TEXT.normal).toBe('正常')
      expect(STATUS_TEXT.alarm).toBe('报警')
      expect(STATUS_TEXT.fault).toBe('故障')
      expect(STATUS_TEXT.masked).toBe('屏蔽')
    })
  })

  describe('DEVICE_TYPE_TEXT / DEVICE_TYPE_ABBR', () => {
    it('正确映射设备类型的完整中文名', () => {
      expect(DEVICE_TYPE_TEXT.smoke).toBe('烟感探测器')
      expect(DEVICE_TYPE_TEXT.temp).toBe('温感探测器')
      expect(DEVICE_TYPE_TEXT.manual).toBe('手动报警按钮')
      expect(DEVICE_TYPE_TEXT.hydrant).toBe('消火栓')
      expect(DEVICE_TYPE_TEXT.sprinkler).toBe('喷淋头')
      expect(DEVICE_TYPE_TEXT.smoke_exhaust).toBe('排烟风机')
      expect(DEVICE_TYPE_TEXT.fire_door).toBe('防火门')
      expect(DEVICE_TYPE_TEXT.emergency_light).toBe('应急照明')
    })

    it('正确映射设备类型缩写', () => {
      expect(DEVICE_TYPE_ABBR.smoke).toBe('烟')
      expect(DEVICE_TYPE_ABBR.temp).toBe('温')
      expect(DEVICE_TYPE_ABBR.fire_door).toBe('门')
      expect(DEVICE_TYPE_ABBR.emergency_light).toBe('照')
    })
  })

  describe('ACTION_TEXT', () => {
    it('正确映射联动动作中文名', () => {
      expect(ACTION_TEXT.smoke_exhaust).toBe('启动排烟')
      expect(ACTION_TEXT.fire_door).toBe('关闭防火门')
      expect(ACTION_TEXT.emergency_light).toBe('启动应急照明')
      expect(ACTION_TEXT.broadcast).toBe('疏散广播')
    })
  })

  describe('FIRE_TYPE_TEXT', () => {
    it('正确映射火灾类型中文名', () => {
      expect(FIRE_TYPE_TEXT.electrical).toBe('电气火灾')
      expect(FIRE_TYPE_TEXT.ordinary).toBe('普通火灾')
      expect(FIRE_TYPE_TEXT.oil).toBe('油类火灾')
    })
  })

  describe('ALARM_STATUS_TEXT / ROLE_TEXT', () => {
    it('正确映射报警状态与角色文本', () => {
      expect(ALARM_STATUS_TEXT.pending).toBe('待确认')
      expect(ALARM_STATUS_TEXT.confirmed_real).toBe('确认真实')
      expect(ALARM_STATUS_TEXT.confirmed_false).toBe('误报')
      expect(ROLE_TEXT.supervisor).toBe('主管')
      expect(ROLE_TEXT.duty).toBe('值班员')
      expect(ROLE_TEXT.maintenance).toBe('维保员')
    })
  })

  describe('ALARM_STATUS_COLOR', () => {
    it('为报警状态提供对应的颜色', () => {
      expect(ALARM_STATUS_COLOR.pending).toBe('#faad14')
      expect(ALARM_STATUS_COLOR.confirmed_real).toBe('#52c41a')
      expect(ALARM_STATUS_COLOR.confirmed_false).toBe('#bfbfbf')
    })
  })
})