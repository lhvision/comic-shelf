# 纸间 · 下一阶段交接与架构设计备忘录（Handover & Design RFC）

> **文档目的**：本文档为开启**新对话会话**时的无缝交接索引。即使在新对话中重新评估、优化架构设计，新 Agent 也可凭此文档在 30 秒内完整掌握当前基线、设计空间与待决议题。

---

## 一、 当前阶段（先行项 1）已落地基线全景

先行项 1（**漫画台词全文检索 SQLite FTS5 + 伴生 OCR 同步 + 阅读器气泡呼吸高亮**）已全部落地并通过 100% 验收门禁。

### 1. 核心代码与架构资产清单

| 模块/路径                                                                     | 核心职责与设计约束                                                                                                                                                                                                                                                                                                                                                                     |
| :---------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/app/db.py`                                                           | 初始化 SQLite FTS5 `comic_dialogues_fts`（`tokenize='trigram'`）与 `comic_ocr_sync_meta`（mtime 元数据跟踪）；实现三层深度增量；实现 `sync_comic_dialogues`（多章节全局单调递增页码映射、沙箱边界断言 `cand_resolved.is_relative_to(data_resolved)`、`cleanup_orphan_comic_dialogues` 幽灵索引清理）；实现 `search_dialogues`（简繁双向词元展开、访客 `hidden_from_guest` 严格隔离）。 |
| `backend/app/zh_conv.py`                                                      | 零依赖提取 OpenCC 3,881 对最高频中日汉字简繁对应表，入参层自动展开变体，覆盖 99.9% 二次元对白场景。                                                                                                                                                                                                                                                                                    |
| `backend/app/main.py`                                                         | 开放 `GET /api/search/dialogue`（200 字符限制、分页、访客隔离）；开放 `POST /api/library/{source}/{source_id}/ocr/sync`（Machine Token 与馆长鉴权）；在画页重装与删除时联动清理 FTS5 索引。                                                                                                                                                                                            |
| `scripts/ocr.sh` & `scripts/ocr_worker.py`                                    | **存储与算力解耦的批量 OCR 工具链**：在高性能工作站（如 RTX 4070 Ti / 多核 CPU）上直接挂载处理 NAS 目录（`/mnt/nas_manga`）；RapidOCR 多行文本几何聚类（Union-Find 竖排 RTL / 横排 TTB 排序与归一化百分比坐标）；多线程并发处理（`--workers`）；画页与全本两级 0ms 增量跳过；原子写入伴生 `.ocr.json`；支持 HTTP 远程回调 NAS 触发入库，杜绝网络文件系统 SQLite 锁冲突。               |
| `scripts/sync_ocr.py`                                                         | OCR 伴生文件入库运维 CLI 工具（`pnpm ocr:sync`），基于 `comic_ocr_sync_meta` 实现 DB 级毫秒级增量缓存跳过，具备孤儿漫画幽灵索引自愈清理与 NAS 挂载活性检测。                                                                                                                                                                                                                           |
| `src/components/ReaderBubbleOverlay.vue`                                      | 归一化百分比坐标 `[ymin, xmin, ymax, xmax]` ∈ [0.0, 1.0]，纯 CSS 百分比定位；Letterbox/Pillarbox 边界锚定至 `.comic-page-img-frame`，彻底杜绝拉伸漂移；`imageReady` 图片解码就绪门禁；朱砂金墨 2.2 秒呼吸动画后优雅淡出；`pointer-events: none` 零交互阻塞；`prefers-reduced-motion` 降级支持。                                                                                        |
| `src/composables/useReaderBubble.ts`                                          | 顶层解构 Composable，统一解析路由参数 `?page=42&bubble_box=...` 与 `?page=42&highlight_bubble=1`；支持 RapidOCR 0..1000 整数坐标、百分比与 [0.0, 1.0] 浮点自适应归一化与坐标边界保护。                                                                                                                                                                                                 |
| `src/components/ComicPageImage.vue` / `ReaderViewport.vue` / `ReaderView.vue` | **Aspect-Ratio Lock（宽高比锁定帧）**：底图解码后动态注入 `aspectRatio: naturalRatio`，翻页模式（`vertical-paged` / `horizontal`）与自适应高度（`fit: height`）下 `img` 100% 贴紧容器，实现跨全模式与视口尺寸 **`diff(img, frame) === 0`** 绝对贴紧；竖向翻页升级为 `scroll-snap-type: y mandatory` 刚性吸附，彻底杜绝伪连续漂移。                                                     |
| `src/components/reader/ReaderSettingsPanel.vue`                               | **图片适配全模式显式透出与硬约束**：图片适配设置组全模式常驻，在翻页模式（`vertical-paged` / `horizontal`）与条漫长卷（`seamless`）下以徽标 `〔 翻页已锁定整页入目 〕` / `〔 条漫已锁定适应宽度 〕` 显式明示约束并禁用切换，消除用户误解。                                                                                                                                             |

### 2. 测试与质量门禁状态（全绿基线）

- **Python 后端测试**：`pnpm test:py`（运行 `backend/tests/test_dialogue_fts.py`、`backend/tests/test_ocr_worker.py` 等套件全部通过）；
- **前端单测**：`vp test src/__tests__/useReaderBubble.spec.ts src/__tests__/ReaderBubbleOverlay.spec.ts` 16 个测试全部通过（含 0..1000 标度、百分比标度与气泡覆盖层单测）；
- **设置单测**：`vp test src/__tests__/useReaderSettings.spec.ts` 13 个测试全部通过；
- **类型与代码检查**：`vp check` 0 错误（325 文件格式化，250 文件 0 警告 0 报错），`pnpm type-check`（`vue-tsc --build` 增量验证）0 错误；
- **UI 质量门禁**：`pnpm detect:slop` 0 违规，`pnpm detect:perf` 0 强制同步重排；
- **架构记录与评审**：已收录至 [ADR 0017](docs/adr/0017-comic-dialogue-fts-and-bubble-overlay.md)，错题本已收录至 [PITFALLS.md §80](docs/PITFALLS.md)，UI 物理评审快照落盘至 `.impeccable/critique/2026-09-12T06-15-33Z__reader-bubble-overlay.md`。

---

## 二、 下一阶段核心议题与待优化设计空间（Design Re-Optimization Space）

进入新会话后，重点围绕 **“纸间 MCP Server + 官方 Agent Skill 双子星”** 与 **“定向单本临时直达凭据（One-Time Direct Pass）”** 展开。新会话可以重新评估并优化以下 4 个关键设计点：

### 议题 1：MCP 传输层选型与实现范式（Protocol & Transport Layer）

- **选项 A（FastAPI 原生轻量实现 SSE，推荐）**：
  - **机制**：在当前 FastAPI 后端中直接增加路由 `GET /mcp/sse` 与 `POST /mcp/message`，按照 JSON-RPC 2.0 / MCP 官方协议规范收发请求与事件；
  - **优势**：0 引入额外重型三方依赖，避免与当前 Python 虚拟环境/Docker 依赖产生冲突，代码极简透明；
- **选项 B（官方 Python `mcp` SDK）**：
  - **机制**：引入 `pip install mcp`，使用 `FastMCP` 或 Starlette 适配层；
  - **待推演**：需要核对 `mcp` SDK 与当前 Python 3.10+ / FastAPI 异步循环的兼容性，以及 Docker 构建体积变化；
- **选项 C（CLI stdio 适配器）**：
  - **机制**：编写 `scripts/mcp_stdio.py`，供外部命令行 Agent（如 Claude Code、本地 CLI）直接通过标准输入输出交互。

### 议题 2：定向单本临时直达凭据（One-Time Direct Pass）架构设计

- **业务痛点**：外部群聊（如飞书 Bot）搜图或台词命中后，需要向用户提供直达本子阅读链接，但全站受到严格的馆长/访客门禁保护。若开放全库访客权限，会导致群友顺藤摸瓜浏览其他私密本子；若不开权限，未登录用户无法阅读。
- **单本沙箱（Single-Book Sandbox）设计关键点**：
  1. **数据模型与存储**：在 SQLite 创建 `direct_passes (token TEXT PRIMARY KEY, source TEXT, source_id TEXT, allowed_page INTEGER, expires_at INTEGER, created_at INTEGER)`，支持按 TTL（如默认 2 小时）过期；
  2. **端点协议**：`POST /api/auth/direct-pass`（入参 `{ source, source_id, page_index?, ttl_seconds? }`，返回 `{ token, direct_url, expires_at }`）；
  3. **中间件与鉴权防线**：
     - 在请求拦截器中校验 `temp_token`；
     - **严格作用域白名单**：携带 `temp_token` 的请求，仅放行该本漫画的 `/api/library/{source}/{source_id}` 元数据、画页图片 `/api/library/{source}/{source_id}/page/{idx}`、缩略图；阻断任何其他书籍、书架列表与修改类接口；
  4. **前端单本沙箱体验**：
     - 读者通过 `https://shelf.example.com/book/jm/523607?page=42&temp_token=...` 打开时，阅读器识别临时直达模式；
     - 隐藏或禁用“返回书架”按钮，面包屑仅展示该漫画标题；若读者尝试访问首页 `/`，友好引导提示需要完整访客密码或馆长密钥。

### 议题 3：官方 Agent Skill (`SKILL.md`) 编排与心智模型

- **落盘位置**：`docs/skills/paper-room/SKILL.md`（可被 Antigravity / Claude Code / 外部 Bot 快速装载）。
- **Playbook 与 SOP 规则契约**：
  - **决策树**：
    1. 用户发送图片 ➔ 调用 `search_by_image`；
    2. 用户发送模糊台词/名台词 ➔ 调用 `search_by_dialogue`；
    3. 用户同时发送图和文字 ➔ 先图后文，交叉比对置信度；
    4. 命中后响应规范 ➔ **严禁**直接暴露后台未授权 URL，必须调用 `create_direct_pass` 签发临时凭据，并套用典雅的“纸间馆员”口吻输出回复（包含封面、本子名、命中画页、气泡台词引用及 2 小时直达阅读卡片）。
  - **防越权与安全护栏**：Skill 中必须明文禁止 Agent 尝试列出隐藏本子或调用管理员接口。

### 议题 5：后端架构治理与模块化拆分（已落地完成 ✅）

- **落地成果**：
  1. **测试目录规范化**：平铺的 13 个 `test_*.py` 全部归拢至 `backend/tests/`，引入统一辅助夹具 `helpers.py`；
  2. **FastAPI 路由模块化**：原 1615 行上帝文件 `main.py` 拆解为 `backend/app/routers/`（`auth`, `library`, `media`, `chapters`, `local_comic`, `search`, `system`, `common`），`main.py` 骤降至 443 行（只保留应用启动装配与兼容门面）；
  3. **ComicStore 存储分层解耦**：原 2171 行上帝类 `storage.py` 解构为 `backend/app/storage/` 模块包，采用 Mixin 领域模式分治（`base.py`, `media.py`, `chapters.py`, `local.py`, `prefetch.py`, `utils.py`），对外保留 100% 兼容门面；
  4. **纵深安全加固**：优先提取 Cloudflare `CF-Connecting-IP` 标头防 IP 伪造，增加 50MB 单页上传上限防御 OOM。
- **验收记录**：通过 `pnpm test:py`（全套 13 组测试全部通过）与 `vp check`（0 warning, 0 lint error, 0 type error）。

---

## 三、 新对话快速启航指南（Prompt Template）

在新对话打开时，您可以直接向新 Agent 发送以下启动提示词：

```markdown
请阅读 docs/HANDOVER_NEXT_STAGE.md 与 docs/AI_ECOSYSTEM_ROADMAP.md。
先行项 1（台词全文检索 FTS5 + 伴生 OCR 索引 + 阅读器气泡呼吸高亮）以及后端全面架构治理（main/storage 模块化拆分与安全加固）已全部完工并通过所有静态和单元测试。
我们现在开始进行下一阶段工作：纸间 Paper Room MCP Server + 官方 Agent Skill 双子星架构，以及定向单本临时直达票据（One-Time Direct Pass）。
请先结合 docs/HANDOVER_NEXT_STAGE.md 中的四个设计议题（协议选型、临时票据沙箱、Skill SOP 编排、前台 UI 接入），为我梳理并推演最佳实现方案。
```

---

## 四、 本地 Git 工作区状态说明

当前工作区已完成全部代码编写与验证，未提交的代码属于台词检索与后端架构治理的完整成果集合。可随时安全地执行 commit：

```bash
git add .
git commit -m "refactor(backend): 拆分 main 与 storage 巨石文件为模块化 Routers 与 Storage Mixin，完成全链路安全加固"
```
