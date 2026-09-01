import { test, expect } from './fixture'

test('验证组件治理后首页、收录面板、存储浮层与阅读器交互无误', async ({ gotoRoute, page }) => {
  // 1. 访问首页 https://localhost:5173/
  await gotoRoute('/')
  await expect(page.locator('.site-header')).toBeVisible()

  // 2. 验证 ImportPanel 组件模块化
  const jmTab = page.locator('.panel-tab').first()
  await expect(jmTab).toHaveText('禁漫车号')
  const localTab = page.locator('.panel-tab').nth(1)
  await expect(localTab).toHaveText('本地自建 / 拆帧')

  // 切换到本地 Tab 并验证工坊入口
  await localTab.click()
  await expect(page.locator('.field-prefix')).toHaveText('PATH')
  await expect(page.locator('.workshop-btn')).toBeVisible()

  // 切换回 JM Tab 并验证下载并发步进器
  await jmTab.click()
  await expect(page.locator('.field-prefix')).toHaveText('JM')
  await expect(page.locator('.stepper')).toBeVisible()

  // 3. 验证 StoragePopover 模块化
  const storageBtn = page.locator('.storage-badge-btn')
  await expect(storageBtn).toBeVisible()
  await storageBtn.click()

  // 验证弹出的 StoragePanel 各子组件
  await expect(page.locator('.panel-title')).toHaveText('阅览室设备与离线')
  await expect(page.locator('.storage-gauge')).toBeVisible()
  await expect(page.locator('.storage-breakdown')).toBeVisible()
  await expect(page.locator('.reset-btn')).toHaveText('重置全部离线环境')

  // 点击关闭 StoragePopover
  await page.keyboard.press('Escape')

  // 4. 验证详情页与阅读器流转
  const firstCard = page.locator('.comic-card .card-link').first()
  if (await firstCard.isVisible()) {
    await firstCard.click()
    await page.waitForURL(/\/comic\//)

    const readBtn = page.locator('.btn-read')
    await expect(readBtn).toBeVisible()

    // 进入阅读器验证 useReaderNavigation 和 useReaderKeyboard
    await readBtn.click()
    await page.waitForURL(/\/read\//)

    const readerView = page.locator('.reader-view')
    await expect(readerView).toBeVisible()

    // 验证键盘按键与退出
    await page.keyboard.press('ArrowDown')
    await page.keyboard.press('Escape')
    await page.waitForURL(/\/comic\//)
  }
})
