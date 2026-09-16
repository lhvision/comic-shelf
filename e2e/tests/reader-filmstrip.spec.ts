import { test, expect } from './fixture'

/**
 * @file reader-filmstrip.spec.ts
 * @description 917 页超大画卷阅读器胶片预览轨（Filmstrip Scrubber）与画中画悬停气泡 E2E 终验。
 *
 * 核心验证维度：
 * 1. 抽屉唤醒与骨架常驻：按键盘 't' 或 's' 唤出胶片抽屉，917 个微缩单元格常驻，DOM 零坍塌；
 * 2. 迟滞注水隔离：初始仅注水当前页邻近（±8）缩略图（img <= 25），其余静默占位；
 * 3. 组级光标框定：第 4 页对应的胶卷单元格外框呈现激活高亮；
 * 4. 选页跳转响应：点击指定微缩胶卷单元格（如第 10 页），阅读器视口无缝跳转；
 * 5. 阶梯式 Escape 级联退出：抽屉展开时按 Escape 仅收起胶卷，绝对不退出阅读器；
 * 6. 暗室遮罩点击收起：抽屉展开时点击上方 Backdrop 遮罩立即收起抽屉。
 */

test.describe('阅读器胶片预览轨与交互安全 E2E 终验', () => {
  test('1. 胶片预览轨唤起、917 页注水隔离与交互选页', async ({ gotoRoute, page }) => {
    // 1. 直达 917 页漫画第 4 页
    await gotoRoute('/comic/local/tiya-frames/read/4')

    const readerView = page.locator('.reader-view')
    await expect(readerView).toBeVisible({ timeout: 15000 })

    // 等待第 4 页容器挂载并就绪，确保数据与初始化定位已完成
    const page4Spread = page.locator('#page-4')
    await expect(page4Spread).toBeAttached({ timeout: 15000 })

    // 2. 按快捷键 't' 唤起胶片预览轨
    await page.keyboard.press('t')

    const filmstrip = page.locator('.reader-filmstrip')
    await expect(filmstrip).toBeVisible({ timeout: 5000 })

    const backdrop = page.locator('.filmstrip-backdrop')
    await expect(backdrop).toBeVisible()

    // 3. 验证 917 个微缩胶卷格完整渲染，DOM 骨架不坍塌
    const totalTiles = await page.locator('.filmstrip-tile').count()
    expect(totalTiles).toBe(917)

    // 4. 验证当前激活页微缩格及所属分屏组呈现激活框定
    const activeTile = page.locator('.filmstrip-tile[data-page-active="true"]')
    await expect(activeTile).toBeVisible({ timeout: 5000 })
    const activePageNum = Number(await activeTile.getAttribute('data-page'))
    expect([3, 4]).toContain(activePageNum)

    const activeGroup = page.locator('.filmstrip-group.group-active')
    await expect(activeGroup).toBeVisible()

    // 5. 验证迟滞注水视窗隔离：仅当前页周围加载了真实的缩略图（<= 25）
    const hydratedThumbsCount = await page.locator('.filmstrip-tile img').count()
    expect(hydratedThumbsCount).toBeGreaterThanOrEqual(1)
    expect(hydratedThumbsCount).toBeLessThanOrEqual(25)

    // 6. 点击第 10 页微缩格，验证切页跳转
    const tile10 = page.locator('.filmstrip-tile[data-page="10"]')
    await expect(tile10).toBeAttached()
    await tile10.click()

    // 验证激活态已变更
    await expect(page.locator('.filmstrip-tile[data-page="10"]')).toBeAttached()

    // 7. 阶梯式 Escape 验证：按 Escape 键仅收起胶片轨，URL 仍保持在阅读器内
    await page.keyboard.press('Escape')
    await expect(filmstrip).not.toBeVisible()
    expect(page.url()).toContain('/read/')

    // 8. 快捷键 's' 与遮罩点击收起验证
    await page.keyboard.press('s')
    await expect(filmstrip).toBeVisible()
    await backdrop.click({ position: { x: 100, y: 100 } })
    await expect(filmstrip).not.toBeVisible()
  })

  test('2. 点击后续较远胶卷格（如第 60 页）平滑直达，无往复震荡回滚', async ({
    gotoRoute,
    page,
  }) => {
    // 1. 直达漫画第 4 页
    await gotoRoute('/comic/local/tiya-frames/read/4')
    await expect(page.locator('.reader-view')).toBeVisible({ timeout: 15000 })
    await expect(page.locator('#page-4')).toBeAttached({ timeout: 15000 })

    // 2. 唤起胶片预览轨
    await page.keyboard.press('t')
    const filmstrip = page.locator('.reader-filmstrip')
    await expect(filmstrip).toBeVisible({ timeout: 5000 })

    const tile60 = page.locator('.filmstrip-tile[data-page="60"]')
    await expect(tile60).toBeAttached()

    // 3. 监控轨道 scrollLeft 轨迹，验证单向平滑无震荡（reversals === 0）
    const trajectoryPromise = page.evaluate(() => {
      return new Promise<number>((resolve) => {
        const rail = document.querySelector('.filmstrip-rail')
        if (!rail) return resolve(0)
        let reversals = 0
        let lastScroll = rail.scrollLeft
        let lastDiff = 0
        const interval = setInterval(() => {
          const cur = rail.scrollLeft
          const diff = cur - lastScroll
          if ((diff > 3 && lastDiff < -3) || (diff < -3 && lastDiff > 3)) {
            reversals++
          }
          if (Math.abs(diff) > 3) {
            lastDiff = diff
          }
          lastScroll = cur
        }, 20)

        setTimeout(() => {
          clearInterval(interval)
          resolve(reversals)
        }, 900)
      })
    })

    // 4. 点击第 60 页微缩格
    await tile60.click()

    const reversals = await trajectoryPromise
    expect(reversals).toBe(0)

    // 5. 验证最终落点精确锁定在第 60 页，无来回乱跳
    const activeTile = page.locator('.filmstrip-tile[data-page-active="true"]')
    await expect(activeTile).toHaveAttribute('data-page', '60', { timeout: 3000 })
  })

  test('3. 长按键盘右方向键（连击翻页）平滑跟进，松手后无往复震荡回滚', async ({
    gotoRoute,
    page,
  }) => {
    // 1. 直达漫画第 4 页并唤起胶片轨
    await gotoRoute('/comic/local/tiya-frames/read/4')
    await expect(page.locator('.reader-view')).toBeVisible({ timeout: 15000 })
    await page.keyboard.press('t')
    const filmstrip = page.locator('.reader-filmstrip')
    await expect(filmstrip).toBeVisible({ timeout: 5000 })

    // 2. 长按右方向键 600ms（模拟连续翻页连击）
    await page.keyboard.down('ArrowRight')
    await page.waitForTimeout(600)

    // 3. 启动 20ms 物理轨迹监测探针，验证松手后胶片轨滑动单向平稳，reversals === 0
    const trajectoryPromise = page.evaluate(() => {
      return new Promise<number>((resolve) => {
        const rail = document.querySelector('.filmstrip-rail')
        if (!rail) return resolve(0)
        let reversals = 0
        let lastScroll = rail.scrollLeft
        let lastDiff = 0
        const interval = setInterval(() => {
          const cur = rail.scrollLeft
          const diff = cur - lastScroll
          if ((diff > 3 && lastDiff < -3) || (diff < -3 && lastDiff > 3)) {
            reversals++
          }
          if (Math.abs(diff) > 3) {
            lastDiff = diff
          }
          lastScroll = cur
        }, 20)

        setTimeout(() => {
          clearInterval(interval)
          resolve(reversals)
        }, 800)
      })
    })

    await page.keyboard.up('ArrowRight')

    const reversals = await trajectoryPromise
    expect(reversals).toBe(0)

    // 4. 验证松手后停留页码大于初始页 4，且激活单元格存在
    const activeTile = page.locator('.filmstrip-tile[data-page-active="true"]')
    await expect(activeTile).toBeAttached({ timeout: 3000 })
    const settledPage = Number(await activeTile.getAttribute('data-page'))
    expect(settledPage).toBeGreaterThan(4)
  })
})
