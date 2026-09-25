# E2E 测试

用例在 `e2e/tests/`，基于 `@lhvision/ai-e2e-base`（Playwright + Midscene AI，fixture 见 `e2e/tests/fixture.ts`）。

## 什么时候跑

- 不跑：纯样式或 CSS 微调、TS 类型修复、单组件逻辑修复、纯后端逻辑与文档改动。
- 跑单条：新增页面路由、核心跨页流程重构、新增全流程交互，或用户明确要求时，在功能全部写完后的最后阶段跑对应的一条：
  `pnpm ai-e2e:test e2e/tests/<file>.spec.ts -g "用例名"`
- 编码过程中不要边改边跑：E2E 慢，AI 断言还要消耗 token。

## 写用例

- 功能还没有用例时，在 `e2e/tests/` 补对应的 spec。
- 断言优先用原生 Playwright（`expect(locator)…`，毫秒级、不耗 token）；复杂排版、Canvas 或图片内容、阶段成果才用 `aiAssert`。
- 用 `gotoRoute('/path')` 直达目标页，不要从首页一路点过去。
- 失败时看 `midscene_run/report/` 里可回放的报告定位问题，修到这一条全绿才算交付。

## 常用命令

- `pnpm ai-e2e:test e2e/tests/<file>.spec.ts -g "用例名"`：跑单条用例
- `pnpm ai-e2e:chrome`：启动调试浏览器，扫码登录一次，登录态会保留
- `pnpm ai-e2e:platform`：Web 可视化看板
- `pnpm ai-e2e:doctor`：环境自检
