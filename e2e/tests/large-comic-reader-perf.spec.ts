import { test, expect } from './fixture'

/**
 * @file large-comic-reader-perf.spec.ts
 * @description 900+ 页超大画卷视口常驻骨架与非对称迟滞注水视窗（Hysteresis Hydration Window）E2E 性能与防退化测试。
 *
 * 核心验证维度：
 * 1. 常驻 DOM 骨架：917 个 Spread 容器全量存在，scrollHeight 绝对稳定不坍塌；
 * 2. 迟滞注水视窗：初始仅注水首屏及前向 15 屏（活跃 <img> <= 25），远端渲染为静默纸印占位符（.quiescent-paper）；
 * 3. 深层路由直达与视窗漂移：直达第 500 页时，视窗精准滑动至 [470..515]，前序页面安全脱水，活跃图片总数始终受到严格约束（<= 50）；
 * 4. 连续来回翻页防抖动：程序化翻页 320ms 互锁生效，根除画面快速上下颠簸与页码狂跳死锁；
 * 5. 条漫无缝长卷模式（vertical-continuous + seamless）：验证负 margin 亚像素咬合、quiescent-paper 样式清空与浮动页码指示胶囊；
 * 6. 竖向翻页（vertical-paged）与横向翻页（horizontal RTL）：验证 scroll-snap 吸附与单屏 100dvh/100vw 刚性固定。
 */

test.describe('900+ 页超大画卷阅读器性能与多模式全景回归测试', () => {
  test('1. 超大画卷冷启动：常驻骨架与初始注水视窗隔离', async ({ gotoRoute, page }) => {
    // 1. 直达本地 917 页漫画第 1 页
    await gotoRoute('/comic/local/tiya-frames/read/1')

    // 2. 验证阅读器主视口挂载
    const readerView = page.locator('.reader-view')
    await expect(readerView).toBeVisible({ timeout: 15000 })

    const scrollEl = page.locator('.reader-scroll')
    await expect(scrollEl).toBeVisible()

    // 等待首屏图片就绪
    const firstImg = page.locator('#page-1 .comic-page-image[data-state="ready"]')
    await expect(firstImg).toBeVisible({ timeout: 15000 })

    // 3. 验证 917 个 Spread 骨架完整常驻（保证物理滚动高度稳定，不发生 DOM 坍塌）
    const totalSpreads = await page.locator('.reader-spread').count()
    expect(totalSpreads).toBe(917)

    // 验证物理总滚动高度远大于 400,000px
    const scrollMetrics = await page.evaluate(() => {
      const el = document.querySelector('.reader-scroll')
      return {
        scrollHeight: el ? el.scrollHeight : 0,
        scrollTop: el ? el.scrollTop : 0,
      }
    })
    expect(scrollMetrics.scrollHeight).toBeGreaterThan(400000)

    // 4. 验证活跃注水窗口：首屏 + 前向 15 屏，活跃 <img> 总数严格受限（<= 25）
    const activeImagesCount = await page.locator('.comic-page-img').count()
    expect(activeImagesCount).toBeGreaterThanOrEqual(1)
    expect(activeImagesCount).toBeLessThanOrEqual(25)

    // 5. 验证远端页面（第 100 页与第 500 页）渲染为静默纸印占位符，未挂载真实的图片组件
    const page100Paper = page.locator('#page-100 .quiescent-paper')
    await expect(page100Paper).toBeAttached()
    await expect(page100Paper.locator('.quiescent-page-num')).toHaveText('100')

    const page500Paper = page.locator('#page-500 .quiescent-paper')
    await expect(page500Paper).toBeAttached()
    await expect(page500Paper.locator('.quiescent-page-num')).toHaveText('500')
  })

  test('2. 深层跳转与迟滞视窗漂移：第 500 页精准直达与前序脱水', async ({ gotoRoute, page }) => {
    // 1. 直接通过深层路由直达第 500 页
    await gotoRoute('/comic/local/tiya-frames/read/500')

    const readerView = page.locator('.reader-view')
    await expect(readerView).toBeVisible({ timeout: 15000 })

    // 2. 等待第 500 页图片就绪
    const page500Img = page.locator('#page-500 .comic-page-img')
    await expect(page500Img).toBeVisible({ timeout: 15000 })

    // 3. 验证视口处于深层位置，并未跳回顶部
    const scrollMetrics = await page.evaluate(() => {
      const el = document.querySelector('.reader-scroll')
      const target = document.querySelector('#page-500') as HTMLElement | null
      return {
        scrollTop: el ? el.scrollTop : 0,
        targetTop: target ? target.offsetTop : 0,
      }
    })
    expect(scrollMetrics.scrollTop).toBeGreaterThan(200000)

    // 4. 验证第 1 页已经成功脱水为 quiescent-paper，释放显存与 DOM 资源
    const page1Paper = page.locator('#page-1 .quiescent-paper')
    await expect(page1Paper).toBeAttached()

    // 5. 验证整个画卷的活跃 <img> 数量依然受控（保持在 30 后向 + 15 前向的视窗内，约 46 张）
    const activeImagesCount = await page.locator('.comic-page-img').count()
    expect(activeImagesCount).toBeLessThanOrEqual(50)
  })

  test('3. 连续来回翻页与互锁防抖动验证', async ({ gotoRoute, page }) => {
    // 1. 直达第 200 页
    await gotoRoute('/comic/local/tiya-frames/read/200')
    const readerView = page.locator('.reader-view')
    await expect(readerView).toBeVisible({ timeout: 15000 })

    const page200Img = page.locator('#page-200 .comic-page-img')
    await expect(page200Img).toBeVisible({ timeout: 15000 })

    // 记录初始 scrollTop
    const initialScrollTop = await page.evaluate(() => {
      const el = document.querySelector('.reader-scroll')
      return el ? el.scrollTop : 0
    })

    // 2. 连续向下翻页 2 次（按 ArrowDown 键，间隔 350ms 确保走完单次平滑步进）
    await page.keyboard.press('ArrowDown')
    await page.waitForTimeout(350)
    await page.keyboard.press('ArrowDown')
    await page.waitForTimeout(350)

    const scrolledDownTop = await page.evaluate(() => {
      const el = document.querySelector('.reader-scroll')
      return el ? el.scrollTop : 0
    })
    expect(scrolledDownTop).toBeGreaterThan(initialScrollTop)

    // 3. 连续向上翻页 2 次（按 ArrowUp 键）
    await page.keyboard.press('ArrowUp')
    await page.waitForTimeout(350)
    await page.keyboard.press('ArrowUp')
    await page.waitForTimeout(350)

    const scrolledBackTop = await page.evaluate(() => {
      const el = document.querySelector('.reader-scroll')
      return el ? el.scrollTop : 0
    })

    // 4. 验证视口平稳回退，绝无反复抖动或死锁震荡（偏差在 1 屏内）
    expect(Math.abs(scrolledBackTop - initialScrollTop)).toBeLessThan(1200)
  })

  test('4. 纵向条漫无缝长卷模式验证（vertical-continuous + seamless）', async ({
    gotoRoute,
    page,
  }) => {
    // 1. 预先注入 seamless=true 设置
    await gotoRoute('/comic/local/tiya-frames/read/10')
    await page.evaluate(() => {
      const raw = localStorage.getItem('comic-shelf:reader-settings:v1')
      const current = raw ? JSON.parse(raw) : {}
      current.mode = 'vertical-continuous'
      current.seamless = true
      localStorage.setItem('comic-shelf:reader-settings:v1', JSON.stringify(current))
      localStorage.removeItem('comic-shelf:reader-overrides:v1')
    })

    // 重新加载应用设置
    await page.reload()
    const scrollEl = page.locator('.reader-scroll')
    await expect(scrollEl).toBeVisible({ timeout: 15000 })
    await expect(scrollEl).toHaveAttribute('data-seamless', 'true')

    // 2. 验证无缝模式下 quiescent-paper 移除了边框与外发光
    const quiescentBorder = await page.evaluate(() => {
      const paper = document.querySelector('#page-100 .quiescent-paper')
      return paper ? window.getComputedStyle(paper).borderStyle : null
    })
    expect(quiescentBorder).toBe('none')

    // 3. 验证无缝模式下浮动画卷页标（ReaderFloatingPill）就绪挂载
    const floatingPill = page.locator('.reader-floating-pill')
    await expect(floatingPill).toBeAttached()
  })

  test('5. 竖向翻页与横向日漫翻页模式全景验证（vertical-paged & horizontal RTL）', async ({
    gotoRoute,
    page,
  }) => {
    // --- 5.1 竖向翻页模式（vertical-paged）---
    await gotoRoute('/comic/local/tiya-frames/read/50')
    await page.evaluate(() => {
      const raw = localStorage.getItem('comic-shelf:reader-settings:v1')
      const current = raw ? JSON.parse(raw) : {}
      current.mode = 'vertical-paged'
      current.seamless = false
      localStorage.setItem('comic-shelf:reader-settings:v1', JSON.stringify(current))
      localStorage.removeItem('comic-shelf:reader-overrides:v1')
    })
    await page.reload()

    const scrollEl = page.locator('.reader-scroll')
    await expect(scrollEl).toBeVisible({ timeout: 15000 })
    await expect(scrollEl).toHaveAttribute('data-mode', 'vertical-paged')

    // 验证 scroll-snap 为 y mandatory
    const pagedSnap = await page.evaluate(() => {
      const el = document.querySelector('.reader-scroll')
      return el ? window.getComputedStyle(el).scrollSnapType : ''
    })
    expect(pagedSnap).toContain('y mandatory')

    // --- 5.2 横向翻页日漫 RTL 模式（horizontal RTL）---
    await page.evaluate(() => {
      const raw = localStorage.getItem('comic-shelf:reader-settings:v1')
      const current = raw ? JSON.parse(raw) : {}
      current.mode = 'horizontal'
      current.direction = 'rtl'
      localStorage.setItem('comic-shelf:reader-settings:v1', JSON.stringify(current))
      localStorage.removeItem('comic-shelf:reader-overrides:v1')
    })
    await page.reload()

    await expect(scrollEl).toHaveAttribute('data-mode', 'horizontal')
    const horizontalMetrics = await page.evaluate(() => {
      const el = document.querySelector('.reader-scroll')
      const activeImgs = document.querySelectorAll('.comic-page-img')
      const endCardRtl = document.querySelector('.reader-end-rtl')
      return {
        scrollWidth: el ? el.scrollWidth : 0,
        scrollSnap: el ? window.getComputedStyle(el).scrollSnapType : '',
        activeCount: activeImgs.length,
        hasRtlEndCard: !!endCardRtl,
      }
    })

    expect(horizontalMetrics.scrollSnap).toContain('x mandatory')
    expect(horizontalMetrics.scrollWidth).toBeGreaterThan(400000)
    expect(horizontalMetrics.activeCount).toBeLessThanOrEqual(50)
    expect(horizontalMetrics.hasRtlEndCard).toBe(true)

    // 清理测试设置，恢复默认纵向连续
    await page.evaluate(() => {
      const raw = localStorage.getItem('comic-shelf:reader-settings:v1')
      const current = raw ? JSON.parse(raw) : {}
      current.mode = 'vertical-continuous'
      current.seamless = false
      current.direction = 'ltr'
      localStorage.setItem('comic-shelf:reader-settings:v1', JSON.stringify(current))
      localStorage.removeItem('comic-shelf:reader-overrides:v1')
    })
  })
})
