import { test, expect } from './fixture'

test.describe('全站 AppButton 统一按钮体系与多态治理 E2E 全面验证', () => {
  test('1. 首页全局浮层、离线存储面板及回到顶部 FAB 交互验证', async ({ gotoRoute, page }) => {
    // 1. 直达书架首页
    await gotoRoute('/')
    await expect(page.locator('.site-header')).toBeVisible({ timeout: 15000 })

    // 2. 验证书架相机识图按钮为正圆 AppButton 且具备无障碍语义
    const cameraBtn = page.locator('.camera-btn')
    await expect(cameraBtn).toBeVisible()
    await expect(cameraBtn).toHaveClass(/btn-shape-circle/)
    await expect(cameraBtn).toHaveAttribute('aria-label', '上传图片以图搜图')

    // 3. 验证设备与离线存储管理浮层 (StoragePopover)
    const storageBtn = page.locator('.storage-badge-btn')
    await expect(storageBtn).toBeVisible()
    await storageBtn.click()

    // 验证弹出的 StoragePanel 内部按钮均规范收敛为 AppButton
    const resetBtn = page.locator('.reset-btn')
    await expect(resetBtn).toBeVisible()
    await expect(resetBtn).toHaveClass(/btn-ghost/)

    // 点击进入二次确认状态，验证 AppButton 变体
    await resetBtn.click()
    const confirmBox = page.locator('.confirm-box')
    await expect(confirmBox).toBeVisible()

    const confirmDangerBtn = page.locator('.confirm-btn.danger')
    await expect(confirmDangerBtn).toBeVisible()
    await expect(confirmDangerBtn).toHaveClass(/btn-danger/)

    const cancelBtn = page.locator('.confirm-btn.cancel')
    await expect(cancelBtn).toBeVisible()
    await expect(cancelBtn).toHaveClass(/btn-ghost/)

    // 点击取消并按 Escape 退出浮层
    await cancelBtn.click()
    await expect(confirmBox).not.toBeVisible()
    await page.keyboard.press('Escape')

    // 4. 模拟页面深滚动验证 BackToTop 悬浮正圆 FAB 按钮
    await page.evaluate(() => window.scrollTo(0, 800))
    await page.waitForTimeout(300)

    const backToTopBtn = page.locator('.back-to-top-btn')
    await expect(backToTopBtn).toBeVisible()
    await expect(backToTopBtn).toHaveClass(/btn-shape-circle/)
    await expect(backToTopBtn).toHaveAttribute('aria-label', '回到顶部')

    // 点击回到顶部
    await backToTopBtn.click()
    await page.waitForTimeout(400)
    const currentY = await page.evaluate(() => window.scrollY)
    expect(currentY).toBeLessThan(150)
  })

  test('2. 漫画详情页与章节列表内的核心操作栏与独立图标按钮流转', async ({ gotoRoute, page }) => {
    await gotoRoute('/')
    await expect(page.locator('.comic-grid-wrap')).toBeVisible({ timeout: 15000 })

    const firstCard = page.locator('.comic-card .card-link').first()
    if (await firstCard.isVisible()) {
      await firstCard.click()
      await page.waitForURL(/\/comic\//)

      // 1. 验证详情页顶部返回按钮（正圆 Ghost 图标按钮）
      const backBtn = page.locator('.detail-back')
      await expect(backBtn).toBeVisible()
      await expect(backBtn).toHaveClass(/btn-shape-circle/)
      await expect(backBtn).toHaveAttribute('aria-label', '返回书库')

      // 2. 验证操作栏按钮（阅读、离线缓存、更多操作等）
      const readBtn = page.locator('.detail-actions .btn-read')
      await expect(readBtn).toBeVisible()
      await expect(readBtn).toHaveClass(/btn-primary/)

      const cacheAllBtn = page.locator('.detail-actions .btn-cache')
      if (await cacheAllBtn.isVisible()) {
        await expect(cacheAllBtn).toHaveClass(/btn-ghost/)
      }

      // 3. 验证更多操作下拉菜单中的 AppButton
      const moreTrigger = page.locator('.more-trigger')
      if (await moreTrigger.isVisible()) {
        await expect(moreTrigger).toHaveClass(/btn-ghost/)
      }

      // 4. 验证章节卡片列表与章节级独立缓存按钮
      const chapterCards = page.locator('.chapter-card')
      if ((await chapterCards.count()) > 0) {
        const firstChapterCard = chapterCards.first()
        const chapterCacheBtn = firstChapterCard.locator('.chapter-cache-btn')
        if (await chapterCacheBtn.isVisible()) {
          await expect(chapterCacheBtn).toHaveClass(/btn-shape-circle/)
          await expect(chapterCacheBtn).toHaveClass(/btn-ghost/)
        }

        // 点击章节卡片进入章节子路由
        await firstChapterCard.click()
        await page.waitForURL(/\/chapter\//)

        // 验证章节页（ChapterView）核心操作与返回按钮
        const chapterBackBtn = page.locator('.chapter-top-bar .btn.btn-shape-circle')
        await expect(chapterBackBtn).toBeVisible()
        await expect(chapterBackBtn).toHaveAttribute('aria-label', '返回漫画目录')

        // 验证章节底栏翻页动作条
        const chapterActions = page.locator('.chapter-actions')
        await expect(chapterActions).toBeVisible()
        const actionButtons = chapterActions.locator('.btn')
        expect(await actionButtons.count()).toBeGreaterThanOrEqual(1)
      }
    }
  })

  test('3. 自建工坊（CreateComicView）中的章节编排与多态按钮治理验证', async ({
    gotoRoute,
    page,
  }) => {
    // 1. 直达自建工坊页面
    await gotoRoute('/create')
    await expect(page.locator('.create-view')).toBeVisible({ timeout: 15000 })

    // 2. 验证顶部返回正圆图标按钮
    const backBtn = page.locator('.create-head .back-btn')
    await expect(backBtn).toBeVisible()
    await expect(backBtn).toHaveClass(/btn-shape-circle/)
    await expect(backBtn).toHaveAttribute('aria-label', '返回书库')

    // 3. 开启「多章节（分话合集）」模式
    const multiCheckbox = page.locator('.multi-toggle input[type="checkbox"]')
    await multiCheckbox.check()

    // 4. 验证「新增话」按钮（采用 icon="plus" 矢量单源，无伪字符 ＋）
    const chapterBar = page.locator('.chapter-tabs-bar')
    await expect(chapterBar).toBeVisible()

    const addChapterBtn = chapterBar.locator('.btn', { hasText: '新增话' })
    await expect(addChapterBtn).toBeVisible()
    await expect(addChapterBtn).toHaveClass(/btn-ghost/)
    await expect(addChapterBtn.locator('.app-icon--plus')).toBeVisible()

    // 点击新增一话，验证出现多话标签
    await addChapterBtn.click()
    const chapterTabs = page.locator('.chapter-tab')
    expect(await chapterTabs.count()).toBe(2)

    // 验证出现删除话的正圆图标按钮（chap-del-btn）
    const delChapterBtn = chapterTabs.last().locator('.chap-del-btn')
    await expect(delChapterBtn).toBeVisible()
    await expect(delChapterBtn).toHaveClass(/btn-shape-circle/)
    await expect(delChapterBtn).toHaveAttribute('aria-label', '删除本话')

    // 点击删除第二话
    await delChapterBtn.click()
    expect(await page.locator('.chapter-tab').count()).toBe(1)
  })

  test('4. 访客簿弹窗（GuestModal）与凭证印发/卡片操作流中的 AppButton 治理验证', async ({
    gotoRoute,
    page,
  }) => {
    // 拦截馆长通行证列表请求，返回标准 Mock 数据保证用例确定性
    await page.route('**/api/curator/passes', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            {
              id: 101,
              username: '墨客同行',
              token: 'testtoken1234567890abcdef',
              max_devices: 2,
              bound_devices_count: 1,
              created_at: 1710000000,
              expires_at: 1750000000,
              status: 'active',
              has_pin: true,
              activation_status: 'active',
              devices: [
                {
                  device_fingerprint: 'fp_abc123',
                  device_name: 'Chrome on Mac',
                  bound_at: 1710000100,
                  last_seen_at: 1710000200,
                  last_ip: '192.168.1.10',
                },
              ],
            },
          ]),
        })
      } else {
        await route.continue()
      }
    })

    // 1. 直达书架首页并打开访客簿弹窗
    await gotoRoute('/')
    const rosterBtn = page.locator('.guest-roster-btn')
    await expect(rosterBtn).toBeVisible({ timeout: 15000 })
    await rosterBtn.click()

    const modal = page.locator('dialog.modal-dialog')
    await expect(modal).toBeVisible()

    // 2. 验证访客簿标题栏信息说明图标按钮（收敛为 AppButton 方块形态）
    const titleInfoBtn = modal.locator('.title-info-btn')
    await expect(titleInfoBtn).toBeVisible()
    await expect(titleInfoBtn).toHaveClass(/btn-shape-square/)
    await expect(titleInfoBtn).toHaveClass(/btn-ghost/)
    await expect(titleInfoBtn).toHaveAttribute('aria-label', '查看权限隔离说明')

    // 3. 验证现存名册卡片内的 AppButton 核心动作
    const guestCard = modal.locator('.pass-card')
    await expect(guestCard).toBeVisible()

    // 复制直达链接大按钮（AppButton variant="soft"）
    const copyLinkBtn = guestCard.locator('.hero-btn.primary')
    await expect(copyLinkBtn).toBeVisible()
    await expect(copyLinkBtn).toHaveClass(/btn-soft/)

    // 复制口令大按钮（AppButton variant="ghost"）
    const copyTokenBtn = guestCard.locator('.hero-btn.secondary')
    await expect(copyTokenBtn).toBeVisible()
    await expect(copyTokenBtn).toHaveClass(/btn-ghost/)

    // 4. 验证次级工具栏动作按钮（+30天、清空PIN、注销等）
    const toolButtons = guestCard.locator('.sub-tool-btn')
    expect(await toolButtons.count()).toBeGreaterThanOrEqual(3)
    await expect(toolButtons.first()).toHaveClass(/btn-ghost/)
    await expect(toolButtons.first()).toHaveClass(/btn-xs/)

    // 5. 验证清空 PIN 的内联防误触确认弹层 AppButton
    const clearPinBtn = guestCard.locator('.sub-tool-btn', { hasText: '清空PIN' })
    if (await clearPinBtn.isVisible()) {
      await clearPinBtn.click()
      const confirmPop = guestCard.locator('.confirm-pop')
      await expect(confirmPop).toBeVisible()

      const confirmYesBtn = confirmPop.locator('.btn-danger')
      await expect(confirmYesBtn).toBeVisible()
      await expect(confirmYesBtn).toHaveClass(/btn-xs/)

      const confirmNoBtn = confirmPop.locator('.btn-ghost')
      await expect(confirmNoBtn).toBeVisible()
      await confirmNoBtn.click()
      await expect(confirmPop).not.toBeVisible()
    }

    // 6. 切换至「登记印发」Tab，验证登记表单主动作按钮
    const tabs = modal.locator('.tabs-nav-bar .segmented-tab')
    await tabs.nth(1).click()

    const issueSubmitBtn = modal.locator('.issue-submit-btn')
    await expect(issueSubmitBtn).toBeVisible()
    await expect(issueSubmitBtn).toHaveClass(/btn-primary/)
    await expect(issueSubmitBtn).toHaveClass(/btn-md/)
    await expect(issueSubmitBtn).toBeDisabled() // 用户名为空时保持禁用

    // 7. 关闭模态弹窗，验证无障碍恢复
    await page.keyboard.press('Escape')
    await expect(modal).not.toBeVisible()
  })
})
