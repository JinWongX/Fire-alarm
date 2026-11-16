import '@testing-library/jest-dom'
import { vi } from 'vitest'

// 明确声明处于 React act 测试环境（React 18），配合 RTL 统一行为、减少 act 噪声
globalThis.IS_REACT_ACT_ENVIRONMENT = true

// 禁用 antd Modal / Drawer / Select 等组件的过渡动画（getTransitionName -> undefined），
// 避免动画结束触发的异步 setState 在测试中产生大量 not wrapped in act 警告。
// 不改动生产逻辑，仅测试环境生效。
vi.mock('antd/es/_util/motion', async (importOriginal) => {
  const mod = await importOriginal()
  return { ...mod, getTransitionName: () => undefined }
})

// 稳定动画帧，避免动画回调在测试收尾后仍触发
if (typeof globalThis.requestAnimationFrame === 'function') {
  globalThis.requestAnimationFrame = (cb) => setTimeout(cb, 0)
  globalThis.cancelAnimationFrame = (id) => clearTimeout(id)
}

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver =
    globalThis.ResizeObserver || ResizeObserverStub
}

if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })
}

if (!window.scrollTo) {
  window.scrollTo = () => {}
}

const _origGetComputedStyle = window.getComputedStyle.bind(window)
window.getComputedStyle = (elt) => _origGetComputedStyle(elt)