import { test, expect } from './fixture'

test.describe('书架流式分页、阅读状态分段胶囊与视口平稳性 E2E 验证', () => {
  test('1. 阅读状态分段胶囊切换与视口保持（不暴力滚顶，无 TransitionGroup 警告）', async ({
    gotoRoute,
    page,
  }) => {
    const warnings: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'warning' && msg.text().includes('TransitionGroup')) {
        warnings.push(msg.text())
      }
    })

    // 1. 直达书架首页
    await gotoRoute('/')
    await expect(page.locator('.comic-grid-wrap')).toBeVisible({ timeout: 15000 })

    // 2. 模拟向下滚动一段距离（停在书架头部/网格区域）
    await page.evaluate(() => window.scrollTo(0, 350))
    await page.waitForTimeout(300)
    const scrollBefore = await page.evaluate(() => window.scrollY)
    expect(scrollBefore).toBeGreaterThan(100)

    // 3. 点击「在读」分段胶囊
    const readingTab = page.locator('.segmented-tab', { hasText: '在读' })
    await expect(readingTab).toBeVisible()
    await readingTab.click()

    // 验证 URL query 更新为 ?status=reading
    await expect(page).toHaveURL(/\?.*status=reading/)

    // 验证视口未被暴力滚回 0（保留浏览心流）
    await page.waitForTimeout(400)
    const scrollAfter = await page.evaluate(() => window.scrollY)
    expect(scrollAfter).toBeGreaterThan(0)

    // 4. 点击「全部」分段胶囊切回
    const allTab = page.locator('.segmented-tab', { hasText: '全部' })
    await allTab.click()
    await expect(page).not.toHaveURL(/status=reading/)

    // 5. 断言全程 0 TransitionGroup 警告
    expect(warnings).toHaveLength(0)
  })

  test('2. 展开与流式追加卡片正确呈现入 DOM', async ({ gotoRoute, page }) => {
    await gotoRoute('/')
    await expect(page.locator('.comic-grid-wrap')).toBeVisible({ timeout: 15000 })

    const cards = page.locator('.comic-card')
    const initialCount = await cards.count()
    expect(initialCount).toBeGreaterThanOrEqual(1)

    const foldCard = page.locator('.shelf-fold-card').first()
    if (await foldCard.isVisible()) {
      const continueBtn = foldCard.locator('button.btn-primary')
      await continueBtn.click()

      // 验证展现卡片数量成功扩充，新批次顺畅挂载
      await expect(async () => {
        const count = await cards.count()
        expect(count).toBeGreaterThan(initialCount)
      }).toPass({ timeout: 5000 })
    }
  })
})
