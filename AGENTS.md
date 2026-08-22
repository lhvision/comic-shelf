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

> 项目位置：`/home/miku/dsh/comic-shelf`
> 品牌：纸间 Paper Room。定位：本地优先的个人漫画收藏夹，不是泛化爬虫，也不是公开站点。
> 本文件只放每次必读的硬规则和路径索引；详细规则已拆分到 `docs/agents/`，按任务按需读取。

## 🎯 任务交付验收清单（Review Checklist）

- [ ] 运行 `vp check` 确保格式、Lint 与类型检查 100% 通过（0 error）。
- [ ] 涉及 UI/交互改动，在**最终交付阶段**执行对应单条 E2E 验证（`pnpm ai-e2e:test e2e/tests/<file>.spec.ts -g "用例名"`），无用例需在 `e2e/tests/` 补齐。
- [ ] 单元测试只跑与本次改动相关的测试文件（如 `vp test src/__tests__/App.spec.ts`），不全量跑测。

## 规则文件索引

| 文件                              | 何时读取                                                                         |
| --------------------------------- | -------------------------------------------------------------------------------- |
| `docs/agents/ui.md`               | 涉及新 UI 组件、页面重构或视觉方案设计时必读（调度 Impeccable skill 的执行协议） |
| `docs/agents/architecture.md`     | 改后端、Provider、存储、API 或需要架构/文件地图时                                |
| `docs/agents/frontend.md`         | 改书架、详情页、阅读器、页面索引、多来源导航、多章节时                           |
| `docs/agents/html-canvas.md`      | 改 HTML-in-Canvas 实验相关代码时                                                 |
| `docs/agents/tooling-workflow.md` | 处理 Vite+ / Docker / 部署 / 排错时                                              |
| `DESIGN_NOTES.md`                 | 任何 UI/视觉改动前必读（项目长期设计系统与决策现状地图）                         |
| `DEPLOYMENT.md`                   | 容器化、端口、环境变量、持久化相关                                               |
| `README.md`                       | 运行方式、数据布局、已实现功能总览                                               |

## 任何改动前必须遵守

1. **本地优先**：`POST /api/library/import` 先查 `album.json`，命中则 `from_cache=true`，不得请求远端；图片按需懒下载，只有显式缓存才批量下载。
2. **JM 图片必须解密**：禁止直接保存下载字节；必须走 `JmImageTool.get_num_by_url()` + `decode_and_save()`。
3. **decode_version 迁移**：`1` 表示旧 raw 缓存，读取时本地解密迁移，不重新下载；不要随意提升版本。
4. **视觉**：不用 SCSS；颜色/间距/动效走 `src/styles/tokens.css`；禁止紫色渐变、玻璃拟态堆叠、第三方轮播。
5. **性能**：详情页 tile 用 thumbnail，默认 48 个增量渲染，使用 `content-visibility: auto`；原图不得用于缩略图。
6. **阅读器定位**：`loading=false → await nextTick() → scrollTo`；`data-mode` 必须同时加在 `.reader-view` 和 `.reader-scroll`。
7. **多章节保持全局页码**：多章节作品页面按「全局页码拍平」；详情页只在页面索引上按章节切片，
   不要为章节拆新的 page/thumbnail/cover 端点。单章节不写 `chapters`、页面 `chapter` 置空，
   继续用扁平 `pages/`，旧缓存零迁移。

## 关键路径速查

- 后端路由：`backend/app/main.py`
- 存储/缓存：`backend/app/storage.py`
- Provider：`backend/app/providers/base.py`、`jm.py`、`registry.py`
- 数据目录：`backend/data/library/<source>/<source_id>/`
- 前端入口：`src/main.ts`、`src/App.vue`、`src/router/index.ts`
- 页面：`src/views/LibraryView.vue`、`ComicDetailView.vue`、`ReaderView.vue`
- 详情子组件：`src/components/detail/`（`DetailActionBar` / `ChapterSwitcher` / `PageIndexGrid` / `PageTile`）
- 设计 token：`src/styles/tokens.css`
- Composable：`src/composables/`（`useLastRead` / `useReaderSettings` / `useChapterNavigation` 等）
- Pinia：`src/stores/library.ts`、`src/stores/experiments.ts`

## 常用命令

```bash
cd /home/miku/dsh/comic-shelf
./scripts/dev.sh                         # 同时起 API + Web（带热重载）
pnpm api                                 # 只起 API（自动探测 Python 并热重载）
vp dev                                   # 只起 Web
vp check                                 # fmt + lint + type-check
vp test                                  # Vitest
vp build                                 # 生产构建
pnpm ai-e2e:doctor                       # AI E2E 环境诊断
pnpm ai-e2e:platform                     # 启动 Web 回归测试看板
pnpm ai-e2e:chrome                       # 启动 Chrome 调试实例（扫码登录一次持久化）
pnpm ai-e2e:yaml e2e/yaml/<file>.yaml    # 执行 Midscene YAML 脚本
pnpm ai-e2e:test e2e/tests/<file>.spec.ts -g "用例名"   # 默认无头静默跑单条用例
pnpm ai-e2e:test e2e/tests/<file>.spec.ts -g "用例名" --headed # 临时以有头窗口运行排查
```

## Agent 执行约定

### 1. 业务与架构底线（开发阶段专注编码）

- **专注编码，严禁频繁跑测**：在编写组件、函数与状态逻辑期间，**严禁边改代码边频繁触发慢速 E2E 测试**，防止流程打断、Token 浪费与网络等待。
- **禁止删数据**：绝对不能删除后端的 `backend/data/` 数据。
- **改前必读索引**：先根据任务读取“规则文件索引”中的对应文件，再开始改代码；不要只依赖本索引的摘要。
- **视图轻量化（View Thinness）**：`src/views/*.vue` 仅负责页面布局编排、子组件插槽与路由直达，单文件脚本原则上不超过 150 行。
- **状态与副作用下沉（Composable First）**：状态机、定时器、复杂计算与筛选算法必须收敛到 `src/composables/use*.ts`，优先复用 VueUse。
- **Composable 顶层解构铁律（DESIGN_NOTES §13）**：凡由 Composable 返回的 Ref/Computed，必须在 `<script setup>` 顶层解构后再绑定模板或传给子组件，严禁传包装对象导致模板解包失效。
- **组件职责与目录边界**：通用基础组件沉淀至 `src/components/` 根目录；业务域专属组件沉淀至对应子目录（如 `detail/`、`library/`、`reader/`）。
- **视觉准则**：新 UI 组件/重构必读 `docs/agents/ui.md` 并调用 `impeccable` skill；日常与微调遵从 `DESIGN_NOTES.md` 与设计 tokens；阅读器问题先读 `docs/agents/frontend.md`。

### 2. 最终交付验收门禁（Definition of Done）

> 🎯 核心原则：**小步快跑用原生 Playwright，阶段交付/复杂视觉才用 Midscene AI**。避免每次微调代码都跑慢速 AI 断言，防止过度消耗 Token 与卡顿。

- **静态检查**：代码编写完成后，必须运行 `vp check` 确保 0 lint error / 0 type error。
- **单元测试**：如有单测，仅跑与本次改动相关的测试文件（如 `vp test src/__tests__/App.spec.ts`）。
- **🌟 UI / 交互 E2E 终态验证（必做门禁）**：
  - **执行时机**：**仅在功能代码全部编写完成后的最后一步执行**，作为交付验收门禁；
  - **必跑单条用例（静默无头）**：凡涉及页面结构、交互按钮、数据渲染或深层路由，必须运行单条对应 E2E 用例（默认后台无头静默运行，不抢占窗口焦点）：
    `pnpm ai-e2e:test e2e/tests/<file>.spec.ts -g "用例名"`
  - **补齐用例规范**：若该功能尚无用例，必须在 `e2e/tests/` 补齐对应 spec（日常断言优先原生 Playwright，关键视觉使用 `aiAssert`）；
  - **路由秒级直达**：用例使用 `gotoRoute('/comic/123')` 直接跳转，禁止从首页慢速点击；
  - **长效登录态复用**：保持 `BROWSER_MODE=auto` 直连 Chrome 9222 端口或复用 Profile，避免重复模拟登录；首次人工扫码通过 `pnpm ai-e2e:chrome` 初始化；
  - **视觉自愈**：阶段性回归若有失败，查阅 `midscene_run/report/` 视觉报告定位修复，直至单条测试全绿。
