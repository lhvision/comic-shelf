# 纸间 Paper Room — Agent 索引

本地优先的个人漫画收藏夹；禁止作为泛化爬虫或公开图床。工具链为 Vite+（命令用 `vp help` 查）。

## 按需读取

- 术语：`CONTEXT.md`；架构决策：`docs/adr/`
- 后端 / 存储 / Provider / 安全 / 后端测试：`docs/agents/architecture.md`
- 前端 / 阅读器 / 路由 / VueUse / 契约注释：`docs/agents/frontend.md`
- 新 UI 组件或视觉重构：`docs/agents/ui.md` + `DESIGN_NOTES.md`
- 踩坑记录：`docs/PITFALLS.md`（按编号或关键词查，不必通读）
- 引入新 CSS / JS 特性前：`docs/CSS_RADAR.md` / `docs/JS_RADAR.md`
- 部署与环境变量：`DEPLOYMENT.md`；E2E：`e2e/README.md`

## 不变量

1. 本地优先：import 先查 `album.json`（命中即 `from_cache=true`，不请求远端）；图片懒下载；不得删除 `backend/data/`。
2. JM 图片必须经 `JmImageTool.get_num_by_url()` + `decode_and_save()`，不直接存下载字节。
3. 多章节页码按全书拍平为 1..`page_count`，每页带 `chapter`；阅读器、封面、API 都用全局页号。
4. `views/*.vue` 只做布局（脚本 ≤150 行），状态下沉到 `src/composables/`；Composable 返回的 Ref 在 `<script setup>` 顶层解构，只解构实际用到的项；新增模块必须编写完整 JSDoc。
5. 样式：颜色、间距、动效走 `src/styles/tokens.css`；禁止紫色渐变、玻璃拟态堆叠、第三方轮播。
6. 图标只用 `src/components/icons/`（`IconXxx` / `<AppIcon>`），新增图标基于 `BaseIcon.vue`，不写 Unicode 伪图标或内联 `<svg>`。
7. View Transitions 只用于跨页面跳转，阅读器内翻页、切话不用；`ready` / `finished` / `updateCallbackDone` 必须 catch；弹窗用 `<Transition>`。
8. 仓库内不写宿主机绝对路径（跨文件引用走相对路径，落盘剥离 `file://` 协议）。
9. 优先用 VueUse 和现有依赖，不造轮子。

## 交付门禁

- `vp check` 0 错误；改了 `.vue` 再跑 `pnpm type-check`。
- 只跑相关单测：`vp test src/__tests__/<Target>.spec.ts`，日常不跑全量。
- 改了 Python：`pnpm test:py`。
- 结构性 UI 变更：按 `docs/agents/ui.md` 请独立子代理评审，并用 `pnpm critique write` 落盘快照。
- E2E 只在新增路由、跨页流程重构或用户要求时，最后跑单条：`pnpm ai-e2e:test e2e/tests/<file>.spec.ts -g "<用例>"`。

## 常用命令

`pnpm dev:all`（API + Web）· `pnpm api` · `vp dev` · `vp build` · `pnpm imsearch <action>` · `pnpm detect:slop <target>` · `pnpm detect:perf`
