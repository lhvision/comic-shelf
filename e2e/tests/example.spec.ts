import { test, expect } from './fixture'

test('首页能够正常加载并呈现主要内容', async ({ gotoRoute, aiAssert }) => {
  // 1. 使用 gotoRoute 路由直达并智能等待网络就绪
  const page = await gotoRoute('/')

  // 2. 基础页面断言
  await expect(page).toHaveURL(/\//)

  // 3. Midscene 视觉大模型智能断言
  await aiAssert('页面顶部有清晰的标题栏或导航栏，视口中展示了主要的内容或欢迎界面')
})
