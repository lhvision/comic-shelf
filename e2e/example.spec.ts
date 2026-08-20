import { test, expect } from './fixture'

test('首页能够正常加载并呈现主要内容', async ({ gotoRoute, aiAssert, page }) => {
  // 1. 使用 gotoRoute 路由直达
  await gotoRoute('/')

  // 2. 基础页面可达性断言
  await expect(page).toHaveURL(/\//)

  // 3. Midscene 智能视觉断言
  await aiAssert('页面顶部能清晰看到“纸间”标题栏与分类导航项')
})
