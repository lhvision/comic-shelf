# AI E2E 自动化测试与自我修复约定

> 目标：指导 AI Agent 在交付带 UI 的新功能或修复 Bug 后，必须为核心交互补齐视觉回归用例，并通过【单条跑测 -> 查阅 Midscene 报告 -> 自我修复】实现闭环交付。

## 🤖 核心闭环与执行约定

1. **交付带 UI 新功能必须补测**：新增或修改核心交互时，必须在 `e2e/tests/` 补齐对应 Midscene 用例，保证测试 100% 全部通过；
2. **严禁全量跑测（Focused Execution Only）**：仅执行本次改动的单条用例（使用 `-g "用例名"` 精确匹配）；
3. **路由秒级直达（Deep-Link First）**：开发深层路由（如 `/detail/123`）时，使用 `gotoRoute('/detail/123')` 直接直达，严禁从首页漫游点击；
4. **视觉断言优先**：优先使用 `aiAssert` 自然语言断言关键视觉呈现与业务状态，避免维护脆弱的 CSS 选择器；
5. **失败自愈闭环**：UI 回归测试若有失败，报告在 `midscene_run/report/` 下，逐个定位修复，修完重新跑 E2E 测试，直到全绿为止；
6. **长效登录态复用**：保持 `BROWSER_MODE=auto` 直连 Chrome 9222 端口，人工扫码一次后长期复用，免去冗长的模拟登录脚本。

## 📝 用例编写范式

```ts
import { test, expect } from './fixture'

test('功能验证与路由直达', async ({ gotoRoute, aiAssert, aiTap, aiInput, aiWaitFor }) => {
  // ⚡ 直接直达被测深层路由（带登录态）
  await gotoRoute('/comic/123')
  await aiAssert('页面顶部展示导航栏，主要区域展示内容卡片且有操作按钮')
})
```

## ⚡ 常用命令速查

- **跑单条用例**：`pnpm exec playwright test e2e/tests/example.spec.ts -g "用例名"`
- **跑 Midscene YAML 脚本**：`pnpm ai-e2e:yaml e2e/yaml/example.yaml`
- **启动 Chrome 调试实例（扫码登录一次）**：`pnpm ai-e2e:chrome`
- **启动 Web 回归看板**：`pnpm ai-e2e:platform`
- **环境健康自检**：`pnpm ai-e2e:doctor`
