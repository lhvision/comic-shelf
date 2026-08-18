import { PlaywrightAiFixture, type PlayWrightAiFixtureType } from '@midscene/web/playwright'
import { test as base } from '@playwright/test'

// 把 Midscene 的 AI 能力挂到 Playwright 的 test 上。
// 这样每个测试里就能直接解构出 ai / aiAssert / aiInput / aiTap / agentForPage 等方法。
// cache 打开后，AI 的规划与元素定位会被缓存，重复跑接近原生速度；
// 但 aiAssert / aiQuery 的判断结果永远不缓存，每次都真判。
export const test = base.extend<PlayWrightAiFixtureType>(
  PlaywrightAiFixture({
    cache: { id: 'user-admin' },
  }),
)

export { expect } from '@playwright/test'
