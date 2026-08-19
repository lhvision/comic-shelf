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

## 规则文件索引

| 文件                              | 何时读取                                                          |
| --------------------------------- | ----------------------------------------------------------------- |
| `docs/agents/ui.md`               | 设计到新的 ui 改动可以看这个，主要是 Impeccable skill 结合 234 步 |
| `docs/agents/architecture.md`     | 改后端、Provider、存储、API 或需要架构/文件地图时                 |
| `docs/agents/frontend.md`         | 改书架、详情页、阅读器、页面索引、多来源导航、多章节时            |
| `docs/agents/html-canvas.md`      | 改 HTML-in-Canvas 实验相关代码时                                  |
| `docs/agents/tooling-workflow.md` | 处理 Vite+ / Docker / 部署 / 排错时                               |
| `DESIGN_NOTES.md`                 | 任何 UI/视觉改动前                                                |
| `DEPLOYMENT.md`                   | 容器化、端口、环境变量、持久化相关                                |
| `README.md`                       | 运行方式、数据布局、已实现功能总览                                |

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
./scripts/dev.sh                         # 同时起 API + Web
../.venv/bin/python backend/server.py    # 只起 API
vp dev                                   # 只起 Web
vp check                                 # fmt + lint + type-check
vp test                                  # Vitest
vp build                                 # 生产构建
```

## Agent 执行约定

- 不能删除后端的 `backend/data/` 数据，一定要记住
- 先根据任务读取“规则文件索引”中的对应文件，再开始改代码；不要只依赖本索引的摘要。
- 新增功能时先分析职责边界再动手：拆成职责单一的小组件，不要把逻辑堆进单个页面视图；优先用 VueUse（见 `vueuse-functions` skill）实现，别手写浏览器样板；组件按可复用性设计，公共件沉淀到 `src/components/` 根目录，通用化优先于贴死当前需求。
- 任何 UI 改动先读 `DESIGN_NOTES.md`；阅读器问题先读 `docs/agents/frontend.md`。
- 完成后至少运行 `vp check`。
- 测试只跑与本次改动相关的测试文件，例如 `vp test src/__tests__/App.spec.ts`，不要全量 `vp test`；如果本次没有新增或修改测试文件，就不要再跑测试。
