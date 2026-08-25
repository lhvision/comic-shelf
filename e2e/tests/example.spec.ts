import { test, expect } from './fixture'

test('详情页深层路由直达验证', async ({ gotoRoute, page }) => {
  // 1. 使用 gotoRoute 传入相对路径，自动结合 playwright.config.ts 中的 baseURL 拼接
  await gotoRoute('/')

  await expect(page.locator('body')).toBeVisible()
})
