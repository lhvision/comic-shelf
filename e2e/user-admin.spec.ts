import { test, expect } from './fixture'

test.beforeEach(async ({ page }) => {
  await page.goto('/')
  await page.waitForLoadState('networkidle')
})

test('漫画列表能正常加载', async ({ page, aiAssert }) => {
  const firstCard = page.locator('.comic-card, .canvas-card').first()

  await expect(firstCard).toBeVisible({ timeout: 15_000 })
  await firstCard.scrollIntoViewIfNeeded()
  await page.waitForTimeout(400)

  await aiAssert('当前视口中可以看到漫画卡片，并且卡片上有标题、封面和缓存进度')
})
