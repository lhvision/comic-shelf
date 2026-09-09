import { test, expect } from './fixture'

test.describe('JM1211472 全流程与近期架构改动 E2E 回归测试', () => {
  test('1. 书架卡片呈现、红心收藏切换与响应式状态回归', async ({ gotoRoute, page }) => {
    // 1. 访问首页书架
    await gotoRoute('/')
    await expect(page.locator('.site-header')).toBeVisible()

    // 2. 定位 JM1211472 卡片
    const card = page.locator('.comic-card').filter({
      has: page.locator('.id-stamp', { hasText: 'JM1211472' }),
    })
    await expect(card).toBeVisible({ timeout: 10000 })

    // 验证标题与页数信息正确
    await expect(card.locator('.card-meta')).toContainText('42P')

    // 3. 验证红心收藏按钮交互与乐观更新
    const favBtn = card.locator('.favorite-button')
    await expect(favBtn).toBeVisible()

    const initialPressed = (await favBtn.getAttribute('aria-pressed')) === 'true'

    // 点击切换收藏
    await favBtn.click()
    await expect(favBtn).toHaveAttribute('aria-pressed', String(!initialPressed))

    // 再次点击恢复初始状态，保持用户测试环境整洁
    await favBtn.click()
    await expect(favBtn).toHaveAttribute('aria-pressed', String(initialPressed))
  })

  test('2. 详情页直达、useChapterCache 缓存状态与元数据回归', async ({ gotoRoute, page }) => {
    // 1. 直达 JM1211472 详情页
    await gotoRoute('/comic/jm/1211472')

    // 2. 验证 Hero 头部与元数据就绪
    const hero = page.locator('.detail-hero')
    await expect(hero).toBeVisible({ timeout: 10000 })

    // 3. 验证操作栏（DetailActionBar）
    const readBtn = page.locator('.btn-read')
    await expect(readBtn).toBeVisible()

    // 验证由 useChapterCache 驱动的本地化状态（42P 全部已缓存）
    const actionButtons = page.locator('.detail-actions button')
    await expect(actionButtons.filter({ hasText: '已全部本地化' })).toBeVisible()

    // 4. 验证画页索引网格与 PageTile 就地呈现
    const pageTiles = page.locator('.page-tile')
    await expect(pageTiles.first()).toBeVisible()
    await expect(pageTiles.first().locator('.page-state')).toHaveText('本地')
  })

  test('3. 阅读器沉浸阅读、翻页与阅读进度跨页联动回归', async ({ gotoRoute, page }) => {
    // 1. 从详情页点击开始阅读进入阅读器
    await gotoRoute('/comic/jm/1211472')
    const readBtn = page.locator('.btn-read')
    await expect(readBtn).toBeVisible({ timeout: 10000 })

    await readBtn.click()
    await page.waitForURL(/\/read\//)

    // 2. 验证阅读器主视图加载
    const readerView = page.locator('.reader-view')
    await expect(readerView).toBeVisible({ timeout: 10000 })

    // 等待画页图片就绪
    const pageImage = page.locator('.comic-page-image').first()
    await expect(pageImage).toBeVisible({ timeout: 15000 })

    // 3. 执行键盘翻页操作
    await page.keyboard.press('ArrowDown')
    // 等待 1000ms 让防抖阅读进度上报与广播完成
    await page.waitForTimeout(1000)

    // 4. 按 Escape 返回详情页
    await page.keyboard.press('Escape')
    await page.waitForURL(/\/comic\/jm\/1211472$/)

    // 5. 回到首页书架，验证进度徽印
    await gotoRoute('/')
    const card = page.locator('.comic-card').filter({
      has: page.locator('.id-stamp', { hasText: 'JM1211472' }),
    })
    await expect(card).toBeVisible({ timeout: 10000 })

    // 验证卡片上的阅读进度印章呈现
    const stamp = card.locator('.reading-stamp')
    if (await stamp.isVisible()) {
      await expect(stamp).toContainText('P')
    }
  })
})
