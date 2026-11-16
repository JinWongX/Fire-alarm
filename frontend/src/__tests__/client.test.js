import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import client from '../api/client'
import MockAdapter from 'axios-mock-adapter'

let mock

beforeEach(() => {
  mock = new MockAdapter(client, { onNoMatch: 'throwException' })
})

afterEach(() => {
  mock.restore()
  localStorage.clear()
})

describe('api/client', () => {
  it('存在 token 时请求携带 Authorization: Bearer 头', async () => {
    localStorage.setItem('token', 'abc123')
    mock.onGet('/api/devices').reply((config) => {
      expect(config.headers.Authorization).toBe('Bearer abc123')
      return [200, { items: [] }]
    })
    const res = await client.get('/devices')
    expect(res.data).toEqual({ items: [] })
  })

  it('无 token 时不携带 Authorization 头', async () => {
    mock.onGet('/api/areas').reply((config) => {
      expect(config.headers.Authorization).toBeUndefined()
      return [200, []]
    })
    await client.get('/areas')
  })

  it('401 时清理 token/user 并跳转 /login', async () => {
    const fakeLocation = { pathname: '/monitor', href: '/monitor' }
    const origDescriptor = Object.getOwnPropertyDescriptor(window, 'location')
    try {
      Object.defineProperty(window, 'location', {
        value: fakeLocation,
        configurable: true,
        writable: true,
      })
      localStorage.setItem('token', 'expired')
      localStorage.setItem('user', JSON.stringify({ username: 'a' }))
      mock.onGet('/api/x').reply(401, { detail: 'unauthorized' })

      await expect(client.get('/x')).rejects.toBeTruthy()

      expect(localStorage.getItem('token')).toBeNull()
      expect(localStorage.getItem('user')).toBeNull()
      expect(fakeLocation.href).toBe('/login')
    } finally {
      if (origDescriptor) {
        Object.defineProperty(window, 'location', origDescriptor)
      } else {
        delete window.location
      }
    }
  })

  it('已在 /login 页面时不重复跳转（无导航副作用）', async () => {
    window.history.replaceState({}, '', '/login')
    localStorage.setItem('token', 't')
    mock.onGet('/api/x').reply(401, { detail: 'unauthorized' })
    await expect(client.get('/x')).rejects.toBeTruthy()
    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()
  })
})