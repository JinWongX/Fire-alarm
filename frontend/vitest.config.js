import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import os from 'node:os'

// coverage 模式下每个 worker 都会叠加 V8 覆盖率收集的内存/CPU 开销。
// 在 16 核机器上默认并发满核跑会触发系统性资源争抢，令 jsdom 中依赖
// waitFor / .ant-spin-blur / Drawer-Modal 的重型用例偶发撞上测试超时。
// 因此 coverage 时：

const isCoverage = process.argv.includes('--coverage')

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    // 普通模式维持既有行为（18 文件全绿、速度不受影响）
    testTimeout: 90000,
    hookTimeout: 90000,
    // coverage 模式：降低并行度以消除资源争抢，并放宽单用例超时作为兜底。
    // 不改动任何断言，仅消除与覆盖率收集叠加带来的时序/超时抖动。
    ...(isCoverage
      ? {
          maxWorkers: Math.max(2, Math.floor(os.cpus().length / 4)),
          testTimeout: 120000,
          hookTimeout: 120000,
        }
      : {}),
    coverage: {
      provider: 'v8',
      include: ['src/**'],
      exclude: ['src/test/**', 'src/main.jsx', 'src/index.css'],
      reporter: ['text', 'json', 'html'],
      all: true,
    },
  },
})