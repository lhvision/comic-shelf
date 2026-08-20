import {
  createAiFixture,
  expect,
  type PlayWrightAiFixtureType,
  type ExtendedAiFixtureType,
} from '@lhvison/ai-e2e-base'

// 创建支持 CDP 零内核直连、长效登录态持久化、深层路由直达与 Midscene AI 视觉能力的测试 Fixture
export const test = createAiFixture({
  cacheId: 'default-suite',
})

export { expect }
export type { PlayWrightAiFixtureType, ExtendedAiFixtureType }
