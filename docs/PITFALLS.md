# 错题本与避坑指南（Pitfalls Ledger & Anti-Regression Guide）

> **说明**：本文件为纸间项目开发过程中的**核心故障复盘与避坑红线速查表**。
> 每次进行全仓重构、代码审查或架构调整前，必须通读本清单，严禁踩踏已有红线。

---

## 📌 目录索引

1. [后端：依赖清理与中间件执行断层（NameError 500）](#1-后端依赖清理与中间件执行断层)
2. [后端：JM 漫画下架与 404 容错拦截（album_missing）](#2-后端jm-漫画下架与-404-容错拦截)
3. [后端：多章节全局页码单调连续性（Monotonic Indexing）](#3-后端多章节全局页码单调连续性)
4. [后端：服务端路径导入沙箱隔离（Path Sandboxing）](#4-后端服务端路径导入沙箱隔离)
5. [前端：Vue 3 响应式解包与 Composable 顶层解构（Ref Unwrap）](#5-前端vue-3-响应式解包与-composable-顶层解构)
6. [前端：View Transitions 边界与阅读器防抢占崩溃（AbortError）](#6-前端view-transitions-边界与阅读器防抢占崩溃)
7. [前端：硬件图层裁剪与增量呈现（contain: paint 陷阱）](#7-前端硬件图层裁剪与增量呈现)

---

### 1. 后端：依赖清理与中间件执行断层

- **🚨 故障现象**：重构或审查清理未使用 import 时，误将 `auth.py` 的 `is_admin` 移除，导致所有 `POST / PUT / PATCH / DELETE` 接口（如「收录到纸间」、自建图集、追加页面、喜欢等）全部报错 500 `NameError: name 'is_admin' is not defined`。
- **🔍 漏网根因**：
  1. `test_auth.py` 原本仅对 `auth.py` 工具函数做孤立单元测试，未对 FastAPI 顶层挂载的 `auth_and_security_middleware` 真实 HTTP 请求链路进行覆盖；
  2. 项目缺乏 Python 静态未定义变量与 AST 符号检查工具。
- **🛡️ 避坑军规与防线**：
  1. 权限术语统一收敛为 `is_curator`，不再使用别名 `is_admin`；
  2. 提交代码前必跑 `pnpm test:py`（集成 `backend/check_backend.py` 静态 AST 检查 + 中间件端到端鉴权测试）；
  3. `backend/app/main.py` 的路由与中间件改动，必须确保 `test_auth_and_security_middleware` 全绿。

---

### 2. 后端：JM 漫画下架与 404 容错拦截

- **🚨 故障现象**：输入不存在或已被原站下架的 JM 车号（如 `1188845`）时，原站 302 重定向至 `/error/album_missing`，`JmcomicText.analyse_jm_album_html` 试图从错误页提取 `album_id` 抛出 `RegularNotMatchException` 导致后端 500 崩溃。
- **🔍 漏网根因**：Provider 假设所有 HTTP 200/302 响应均为合法漫画 HTML，缺少对错误页面特征的主动探查。
- **🛡️ 避坑军规与防线**：
  1. `JMProvider.fetch` 必须前置探测 `album_missing`（URL 与 HTML 特征）；
  2. 显式抛出 `ValueError("禁漫车号 JM... 不存在或已被下架")`，由 `import_comic` 转换为标准 HTTP 404 响应，UI 友好 Toast 提示。

---

### 3. 后端：多章节全局页码单调连续性

- **🚨 故障现象**：向自建漫画的某一话增量追加多张图片时，后续章节的 `start` 起始页号与全书 `meta.pages[i].index` 发生断裂或重复，导致阅读器翻页跳页。
- **🔍 漏网根因**：局部追加只在目标章节内部自增，未在全书范围重构全局单调索引。
- **🛡️ 避坑军规与防线**：
  1. 无论在哪个章节追加图片，必须执行全局章节重排（`rebuilt_pages`），保证 `ch.start` 与 `page.index` 严格从 1 开始单调递增；
  2. 必须跑通 `backend/test_incremental_update.py`。

---

### 4. 后端：服务端路径导入沙箱隔离

- **🚨 故障现象**：恶意或误操作输入宿主机敏感路径（如 `/etc/`、`/root/`），导致任意文件扫描。
- **🛡️ 避坑军规与防线**：
  1. 所有本地路径导入必须经过 `_is_path_allowed(path)` 校验；
  2. 严格限制仅允许 `DATA_DIR`、`LIBRARY_DIR`、`TMP_DIR`、项目根目录以及用户显式配置的 `COMIC_SHELF_ALLOWED_DIRS` 目录。

---

### 5. 前端：Vue 3 响应式解包与 Composable 顶层解构

- **🚨 故障现象**：Composable 返回的 Ref 在模板绑定时表现为 `[object Object]` 或失去响应性更新。
- **🔍 漏网根因**：Vue 3 模板的自动 unwrap 机制仅对 `<script setup>` 顶层变量生效；若将 Composable 返回的包装对象（如 `const workshop = useLocalWorkshop()` 并在模板使用 `workshop.title`）直接使用，嵌套 Ref 不会自动解包。
- **🛡️ 避坑军规与防线**：
  1. 所有 Composable 返回的 Ref 必须在 `<script setup>` 顶层显式解构：
     `const { title, tags, isMulti, submit } = useLocalWorkshop()`；
  2. 严禁传递未解构的包装对象给模板。

---

### 6. 前端：View Transitions 边界与阅读器防抢占崩溃

- **🚨 故障现象**：用户在沉浸式阅读器中快速按键盘左右翻页或切话时，控制台狂报 `AbortError: The operation was aborted`，导致图片丢失或渲染白屏。
- **🔍 漏网根因**：全屏快照过渡（`document.startViewTransition`）具有全局排他性，上一帧快照未完成时发起新快照会立即被浏览器 Abort 抢占。
- **🛡️ 避坑军规与防线**：
  1. 全屏路由过渡**严禁在阅读器内部翻页/切话中触发**；
  2. 仅允许在跨页面层级跳转（书架 ⇄ 详情 ⇄ 章节 ⇄ 阅读器）中使用；
  3. 所有 `startViewTransition` 必须对 `ready` / `finished` / `updateCallbackDone` 绑定 catch 忽略 AbortError。

---

### 7. 前端：硬件图层裁剪与增量呈现

- **🚨 故障现象**：书架卡片在鼠标悬停（Hover）向上浮动（`-0.35rem`）并投射柔和阴影时，卡片顶部边框被削平、底部出现黑边。
- **🔍 漏网根因**：在 `ComicCard.vue` 上滥用 `content-visibility: auto`。W3C 规范中该属性强制启用 `contain: paint`，使得浏览器 Compositing 合成层生硬切除所有超出 padding-box 的像素。
- **🛡️ 避坑军规与防线**：
  1. 带有浮动、叠牌旋转、柔和弥散阴影的卡片，**绝对禁止**配置 `contain: paint`；
  2. 切换为 `contain: layout style`；
  3. 海量列表性能优化通过「增量分批加载（48 图预算）」+ VueUse `useIntersectionObserver` 实现。

---

## 🚦 交付前自检三步法

1. **静态代码与符号检查**：`vp check`（前端 0 error） + `pnpm test:py`（后端 0 error）；
2. **相关领域单测精准执行**：改动哪个模块，就跑哪个模块对应的单测；
3. **红线对齐**：核对本次改动是否触碰上述 7 条红线。
