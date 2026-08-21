import { createAiFixture } from '@lhvision/ai-e2e-base'

// 创建支持 CDP 零内核直连、长效登录态持久化、深层路由直达与 Midscene AI 视觉能力的测试 Fixture
export const test = createAiFixture({
  cacheId: 'default-suite',
})

// 重新导出所有 Playwright 原生能力 (Page, Locator, expect, devices, defineConfig 等) 与 Midscene 方法/类型
export * from '@lhvision/ai-e2e-base'
