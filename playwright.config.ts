import { defineConfig, devices } from '@playwright/test'
import dotenv from 'dotenv'

// 把 .env 里的 Qwen-VL / DashScope 配置读进来
dotenv.config()

export default defineConfig({
  testDir: './e2e',
  timeout: 90 * 1000,
  fullyParallel: false,
  workers: 1,
  // Midscene 的报告器：跑完在 midscene_run/report/ 生成可回放的 HTML 报告
  reporter: [['list'], ['@midscene/web/playwright-reporter', { type: 'merged' }]],
  use: {
    baseURL: 'https://localhost:5173',
    viewport: { width: 1280, height: 900 },
    trace: 'off',
    ignoreHTTPSErrors: true,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'pnpm dev',
    url: 'https://localhost:5173',
    reuseExistingServer: true,
    timeout: 30 * 1000,
    ignoreHTTPSErrors: true,
  },
})
