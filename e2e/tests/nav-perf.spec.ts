import { test, expect } from './fixture'

test('验证首页->详情页->阅读页首次与二次点击流转时延及卡顿', async ({ gotoRoute, page }) => {
  // 1. 访问首页
  await gotoRoute('/')
  const firstCard = page.locator('.comic-card .card-link').first()
  await expect(firstCard).toBeVisible()

  console.log('\n--- 首次导航测试（含悬停意图预热 150ms）---')
  await firstCard.hover()
  await page.waitForTimeout(150)

  const t0 = Date.now()
  await firstCard.click()

  // 等待路由变更
  await page.waitForURL(/\/comic\//)
  const tRoute1 = Date.now()

  // 等待详情页内容就绪 (Hero 真实封面与阅读按钮呈现)
  const readBtn = page.locator('.btn-read')
  await expect(readBtn).toBeVisible()
  const tDetailLoaded = Date.now()

  // 详情页停留 200ms 决策时间
  await page.waitForTimeout(200)

  const tReadClick = Date.now()
  await readBtn.click()

  await page.waitForURL(/\/read\//)
  const tReadRoute = Date.now()

  const firstPageImg = page.locator('.comic-page-image[data-state="ready"]').first()
  await expect(firstPageImg).toBeVisible({ timeout: 15000 })
  const tReaderReady = Date.now()

  console.log(
    `[首次] 点击卡片 -> URL 变更耗时: ${tRoute1 - t0}ms, 详情页呈现耗时: ${tDetailLoaded - t0}ms`,
  )
  console.log(
    `[首次] 点击阅读 -> URL 变更耗时: ${tReadRoute - tReadClick}ms, 阅读器呈现耗时: ${tReaderReady - tReadClick}ms`,
  )

  // 2. 返回首页，测试二次导航
  console.log('\n--- 二次导航测试 (已有缓存与热模块) ---')
  await gotoRoute('/')
  await expect(firstCard).toBeVisible()

  await firstCard.hover()
  await page.waitForTimeout(100)

  const t0_2 = Date.now()
  await firstCard.click()

  await page.waitForURL(/\/comic\//)
  const tRoute2 = Date.now()

  await expect(readBtn).toBeVisible()
  const tDetailLoaded2 = Date.now()

  await page.waitForTimeout(100)
  const tReadClick2 = Date.now()
  await readBtn.click()

  await page.waitForURL(/\/read\//)
  const tReadRoute2 = Date.now()

  await expect(firstPageImg).toBeVisible({ timeout: 15000 })
  const tReaderReady2 = Date.now()

  console.log(
    `[二次] 点击卡片 -> URL 变更耗时: ${tRoute2 - t0_2}ms, 详情页呈现耗时: ${tDetailLoaded2 - t0_2}ms`,
  )
  console.log(
    `[二次] 点击阅读 -> URL 变更耗时: ${tReadRoute2 - tReadClick2}ms, 阅读器呈现耗时: ${tReaderReady2 - tReadClick2}ms`,
  )
})
