// 后端返回的时间为 naive-UTC（无时区标记），浏览器按本地时区解析会偏移。
// 统一在展示层补 'Z' 视为 UTC 后转本地时间显示。

const DATE_ONLY_RE = /^\d{4}-\d{2}-\d{2}$/
const HAS_TZ_RE = /(Z|[+-]\d{2}:?\d{2})$/i

export function parseServerTime(value) {
  if (value === null || value === undefined || value === '') return null
  if (DATE_ONLY_RE.test(String(value))) {
    return new Date(`${value}T00:00:00Z`)
  }
  const raw = String(value)
  const iso = HAS_TZ_RE.test(raw) ? raw : `${raw}Z`
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  return d
}

export function fmtServerTime(value) {
  const d = parseServerTime(value)
  if (!d) return '-'
  return d.toLocaleString('zh-CN', { hour12: false })
}