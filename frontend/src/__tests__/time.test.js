import { describe, it, expect } from 'vitest'
import { parseServerTime, fmtServerTime } from '../utils/time'

describe('utils/time', () => {
  describe('parseServerTime', () => {
    it('naive UTC 时间（无时区）视为 UTC 解析', () => {
      const d = parseServerTime('2026-09-01T10:00:00')
      expect(d.toISOString()).toBe('2026-09-01T10:00:00.000Z')
    })

    it('纯日期补为 UTC 零点', () => {
      const d = parseServerTime('2026-09-01')
      expect(d.toISOString()).toBe('2026-09-01T00:00:00.000Z')
    })

    it('已带时区标记的字符串直接解析', () => {
      const d = parseServerTime('2024-01-01T00:00:00Z')
      expect(d.toISOString()).toBe('2024-01-01T00:00:00.000Z')
    })

    it('空值/非法值返回 null', () => {
      expect(parseServerTime(null)).toBeNull()
      expect(parseServerTime('')).toBeNull()
      expect(parseServerTime(undefined)).toBeNull()
      expect(parseServerTime('not-a-date')).toBeNull()
    })
  })

  describe('fmtServerTime', () => {
    it('将午夜 UTC 时间转为本地（UTC+8）并格式化为 08:00', () => {
      expect(fmtServerTime('2026-09-01')).toContain('08:00:00')
    })

    it('空值渲染为 -', () => {
      expect(fmtServerTime(null)).toBe('-')
      expect(fmtServerTime('')).toBe('-')
    })
  })
})