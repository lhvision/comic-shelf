<!--VITE PLUS START-->

# Using Vite+, the Unified Toolchain for the Web

This project is using Vite+, a unified toolchain built on top of Vite, Rolldown, Vitest, tsdown, Oxlint, Oxfmt, and Vite Task. Vite+ wraps runtime management, package management, and frontend tooling in a single global CLI called `vp`. Vite+ is distinct from Vite, and it invokes Vite through `vp dev` and `vp build`. Run `vp help` to print a list of commands and `vp <command> --help` for information about a specific command.

Docs are local at `node_modules/vite-plus/docs` or online at https://viteplus.dev/guide/.

## Built-in Commands vs Scripts

`vp <name>` runs a built-in command. `vp run <name>` runs a `package.json` script or a `vite.config.ts` task. Scripts cannot overwrite built-ins, so `vp dev` and `vp run dev` may do different things. Check `package.json` and `vite.config.ts` first, and run `vp run <name>` when the project defines a script or task with that name.

## Tool Versions

Run `vp toolchain` to show versions and relationships in the active Vite+
release. Add a tool name to select part of the graph. For example, run
`vp toolchain vite`. Use `--global` to ignore the local `vite-plus` package. Use
`vp why <package>` to show the package-manager dependency graph.

## Review Checklist

- [ ] Run `vp install` after pulling remote changes and before getting started.
- [ ] Run `vp check` and `vp test` to format, lint, type check and test changes.
- [ ] Check if there are `vite.config.ts` tasks or `package.json` scripts necessary for validation, run via `vp run <script>`.
- [ ] If setup, runtime, or package-manager behavior looks wrong, run `vp env doctor` and include its output when asking for help.

<!--VITE PLUS END-->

# AGENTS.md — 纸间 · Paper Room（索引）

> **品牌定位**：纸间 Paper Room。本地优先的个人漫画收藏夹，禁止作为泛化爬虫或公开图床。
> 本文件为**高信息密度索引中枢**；开发前根据任务按需读取 `docs/agents/` 对应细则。

## 🎯 任务交付验收门禁（Definition of Done）

- [ ] **静态检查**：代码编写完成后运行 `vp check` 确保 0 lint error / 0 type error。
- [ ] **精准单测验证（严禁无差别全量）**：改动涉及逻辑时，**只运行改动对应的单测文件**（如 `vp test src/__tests__/ReaderLoadingState.spec.ts`），严禁日常开发无差别全量执行 `vp test`（防止用例增多后全量卡死/阻塞）。
- [ ] **E2E 终验**：涉及 UI/交互改动，按下方 **E2E 测试准则** 在最终交付阶段执行单条用例验证。

## 📚 规则文件索引（按需读取）

| 规则文档                          | 适用任务场景                                                  |
| --------------------------------- | ------------------------------------------------------------- |
| `docs/agents/architecture.md`     | 后端模型、FastAPI 路由、存储布局、Provider 扩展、安全与防盗链 |
| `docs/agents/frontend.md`         | 书架/详情/阅读器、页面索引、多章节子路由、HTML-in-Canvas      |
| `docs/agents/ui.md`               | 新 UI 组件、页面重构、视觉设计（调度 `impeccable` skill）     |
| `docs/agents/tooling-workflow.md` | Vite+ 工具链、Docker 单容器部署、排错建议                     |
| `DESIGN_NOTES.md`                 | UI 视觉改动前必读（设计系统演进、物理质感决策与踩坑记录）     |
| `DEPLOYMENT.md`                   | 环境变量、TrueNAS / Docker 容器化与以图搜图 Sidecar           |
| `README.md`                       | 项目功能总览、运行方式与 API 清单                             |

## ⚡ 核心不变量与红线（改动必守）

1. **本地优先**：`import` 先查 `album.json`（命中则 `from_cache=true`，不请求远端）；图片按需懒下载；严禁删 `backend/data/`。
2. **JM 图片解密**：严禁直接存下载字节，必须走 `JmImageTool.get_num_by_url()` + `decode_and_save()`；`decode_version=1` 走本地迁移。
3. **多章节全局页码**：页面全书拍平（1..`page_count`），每页带 `chapter`；阅读器/封面/API 走全局页号；详情页走目录+子路由切片。
4. **视图轻量化（View Thinness）**：`views/*.vue` 只负责布局编排（脚本 ≤150 行）；状态与计算必须下沉到 `src/composables/`。
5. **Composable 顶层解构**：Composable 返回的 Ref 必须在 `<script setup>` 顶层解构后绑定，禁止传包装对象导致模板解包失效（DESIGN_NOTES §13）。
6. **视觉与样式约束**：不用 SCSS；颜色/间距/动效走 `src/styles/tokens.css`；禁止紫色渐变、玻璃拟态堆叠、第三方轮播。
7. **精准单测红线**：严禁在日常开发中无差别全量执行 `vp test`；必须只定位改动相关的单测文件（`vp test src/__tests__/<Target>.spec.ts`），防止全量阻塞卡死。
8. **View Transitions 边界与安全**：全屏路由过渡仅在跨页面跳转（书架 ⇄ 详情 ⇄ 章节 ⇄ 阅读器）触发，**严禁在阅读器内部翻页/切话触发**（防 AbortError 抢占崩溃）；所有 `startViewTransition` 必须对 `ready`/`finished`/`updateCallbackDone` 绑定 catch；弹窗与微交互走 Vue 原生 `<Transition>`，禁止对弹窗根容器滥用快照导致遮罩畸变与文字亚像素模糊。

## 🧪 E2E 测试准则与 AI 协作规范

> 🎯 **核心原则**：小步快跑用原生 Playwright，阶段交付/关键视觉才用 Midscene AI。**编码开发中严禁边改边频繁触发慢速 E2E 测试**，避免打断工作流与浪费 Token。

### 1. 最终交付验收门禁（Definition of Done）

- **单条用例终验**：凡涉及页面渲染、交互按钮、数据渲染或深层路由，必须在功能全部写完后的**最终交付阶段**执行单条对应 E2E 用例：
  `pnpm ai-e2e:test e2e/tests/<file>.spec.ts -g "用例名"`
- **补齐用例规范**：若该功能尚无用例，必须在 `e2e/tests/` 补齐对应 spec 文件；
- **断言分层范式**：日常断言优先使用原生 Playwright API（`expect(locator)...`，毫秒级 0 Token）；仅在复杂 UI 排版、Canvas/图片内容或阶段成果时使用 `aiAssert`；
- **路由秒级直达**：用例使用 `gotoRoute('/path')` 直达目标页，禁止从首页漫游点击；
- **自愈与报告排查**：若用例执行失败，查阅 `midscene_run/report/` 视觉报告定位修复，直至单条测试全绿才算交付完成。

### 2. 常用命令速查

- **跑单条用例（最终验收必跑）**：`pnpm ai-e2e:test e2e/tests/<file>.spec.ts -g "用例名"`
- **启动调试浏览器（扫码登录一次持久化）**：`pnpm ai-e2e:chrome`
- **Web 可视化看板**：`pnpm ai-e2e:platform`
- **环境自检**：`pnpm ai-e2e:doctor`

## 🛠️ 项目常用命令

```bash
pnpm dev:all                             # 同时启动 API + Web（热重载）
pnpm api                                 # 只起 API（自动探测 Python 虚拟环境）
vp dev                                   # 只起 Web（Vite+ dev server）
vp check                                 # fmt + lint + type-check
vp test src/__tests__/<Target>.spec.ts   # 运行目标文件单测（严禁日常全量）
vp build                                 # 生产构建
```
