import { test, expect } from './fixture'

// 2B 同页多气泡一次描全：浮层标「N 处命中」，点进阅读器必须把命中的格子一并描出来，
// 不再只画代表句那一格。坐标取自已索引的 jm/1206348 第 20 页（搜「喜欢」命中 3 个气泡）。
const SOURCE = 'jm'
const SOURCE_ID = '1206348'
const PAGE = 20
const REP_BOX = '0.3616,0.3615,0.4635,0.4302'
const SIBLING_BOXES = '0.0347,0.7823,0.1491,0.8760;0.2236,0.1177,0.4827,0.2250'

test.describe('阅读器同页多气泡描边（Sibling Bubble Outlining）', () => {
  test('带 bubble_boxes 时，代表格外还描出同页其余命中气泡', async ({ gotoRoute, page }) => {
    await gotoRoute(
      `/comic/${SOURCE}/${SOURCE_ID}/read/${PAGE}?page=${PAGE}&bubble_box=${REP_BOX}&bubble_boxes=${SIBLING_BOXES}&bubble_text=喜欢`,
    )

    const overlay = page.locator('.reader-bubble-overlay')
    await expect(overlay).toHaveCount(1, { timeout: 15000 })

    // 代表格仍只有一个，callout 也只挂在代表格上
    await expect(page.locator('.reader-bubble-box')).toHaveCount(1)
    await expect(page.locator('.bubble-callout')).toHaveCount(1)
    // 其余 2 格以静态描边叠加
    await expect(page.locator('.reader-bubble-ghost')).toHaveCount(2)

    // 读屏只报实描格数，不冒用后端命中总数
    await expect(overlay).toHaveAttribute('aria-label', /同页一并描出 2 处气泡/)
  })

  test('缺省 bubble_boxes 时不渲染兄弟层，既有单气泡跳转不受影响', async ({ gotoRoute, page }) => {
    await gotoRoute(
      `/comic/${SOURCE}/${SOURCE_ID}/read/${PAGE}?page=${PAGE}&bubble_box=${REP_BOX}&bubble_text=喜欢`,
    )

    await expect(page.locator('.reader-bubble-box')).toHaveCount(1, { timeout: 15000 })
    await expect(page.locator('.reader-bubble-others')).toHaveCount(0)
  })

  test('超长 bubble_boxes（手改 URL 灌 20 段）被前端封顶到 5 格', async ({ gotoRoute, page }) => {
    const flooded = Array.from({ length: 20 }, () => REP_BOX).join(';')
    await gotoRoute(
      `/comic/${SOURCE}/${SOURCE_ID}/read/${PAGE}?page=${PAGE}&bubble_box=${REP_BOX}&bubble_boxes=${flooded}`,
    )

    await expect(page.locator('.reader-bubble-ghost')).toHaveCount(5, { timeout: 15000 })
  })
})
