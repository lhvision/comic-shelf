import { test, expect } from './fixture'

test('验证组件治理后首页、收录面板、存储浮层与阅读器交互无误', async ({ gotoRoute, page }) => {
  // 1. 访问单源工作台：禁漫收录 https://localhost:5173/?source=jm
  await gotoRoute('/?source=jm')
  await expect(page.locator('.site-header')).toBeVisible()

  // 验证 JM 专属工作台：展示 JM 前缀与并发步进器
  await expect(page.locator('.import-panel.is-source-locked')).toBeVisible()
  await expect(page.locator('.field-prefix')).toHaveText('JM')
  await expect(page.locator('.stepper')).toBeVisible()

  // 2. 访问单源工作台：本地自建与拆帧工坊 https://localhost:5173/?source=local
  await gotoRoute('/?source=local')
  await expect(page.locator('.field-prefix')).toHaveText('PATH')
  const workshopBtn = page.locator('.workshop-btn')
  await expect(workshopBtn).toBeVisible()

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
  await gotoRoute('/')
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

  // 5. 验证自建工坊与 FileStagingDropZone 公共暂存组件交互
  await gotoRoute('/create')
  await expect(page.locator('.create-head h1')).toHaveText('收录自建图集与本地拆帧')

  // 验证 FileStagingDropZone 默认渲染网页多图拖拽区
  const dropZone = page.locator('.file-staging-drop-zone .drop-zone')
  await expect(dropZone).toBeVisible()
  await expect(dropZone.locator('.drop-prompt')).toContainText('点击或批量拖入图片至此')

  // 切换到服务器目录导入 Tab 并验证输入框
  const pathModeTab = page.getByRole('tab', { name: '服务器目录导入' })
  await expect(pathModeTab).toBeVisible()
  await pathModeTab.click()

  const pathInput = page.locator('#staging-server-path')
  await expect(pathInput).toBeVisible()
  await expect(page.locator('.path-guide')).toBeVisible()

  // 点击返回按钮验证分级导航
  const backBtn = page.locator('.create-head .back-btn')
  await expect(backBtn).toBeVisible()
  await backBtn.click()
  await page.waitForURL('/')
})
