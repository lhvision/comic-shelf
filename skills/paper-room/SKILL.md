---
name: paper-room
description: '纸间 (Paper Room) 本地漫画收藏馆智能体协同与决策指南。当用户需要以图搜图、分镜识图找漫画、台词全文检索、语义找对白、名对白定位、书架筛选过滤、淘书与题材推荐、阅读器遥控（翻页/跳页/排版切换/气泡高亮聚焦）、一键收录/批量收录漫画、或生成单本沙箱直达分享链接时使用。触发词包括：以图搜图、搜这本漫画出处、找台词、按语义找台词、这句台词出自哪里、翻到下一页、阅读器切换瀑布流、推荐未读漫画、批量收录漫画、签发单本阅读链接、阅读器遥控、漫画详情。'
metadata:
  author: lhvision
  version: '1.5.0'
  tags:
    [
      'comic-shelf',
      'mcp',
      'webmcp',
      'agent-skill',
      'image-search',
      'dialogue-fts',
      'semantic-search',
      'batch-import',
    ]
---

# 纸间 · 智能体协同与决策指南 (Paper Room Agent Skill)

> **品牌定位**：纸间 Paper Room — 本地优先的个人漫画收藏夹，专注于私有阅览室体验与视觉/台词精准召回。

---

## ⚡ IRON LAW

1. **零全库遍历**：严禁无条件并发全库扫描，多维检索必须使用 `query_shelf` 分页或 `get_shelf_stats` 统计。
2. **访客沙箱隔离**：向外部读者或群聊分享漫画一律调用 `create_direct_pass` 签发 2 小时临时阅读票据，严禁暴露馆长密钥与全站视图。
3. **视口生命周期感知**：前端 WebMCP 工具强绑定当前活动页面（Vue Scope），离开页面时自动注销。调用报错时引导用户导航至对应页面，严禁盲目死循环重试。
4. **重操作确认门禁**：执行全量离线缓存（`detail_cache_all_pages`）或外部新漫画收录（单本 `shelf_import_comic` / 批量 `shelf_batch_import_comics`）前，必须向用户确认（列出待收录车号与本数）。
5. **凭据最小化**：接入纸间只用 `COMIC_SHELF_MCP_TOKEN` 那把子凭据；严禁把馆长口令 `COMIC_SHELF_SECRET` 或机器密钥写进 agent 配置、回复正文或任何 URL 查询串（机器密钥只给 OCR 流水线用，本就进不了 MCP）。`create_direct_pass` 对标记「对访客隐藏」的作品会直接拒绝，不要换路径绕行。

### 🚩 Red Flag Signals (出现以下情况立即中止并自查)

- 试图在前端 WebMCP 中寻找识图（ORB）或全文分词（FTS5）底层计算工具（必须走服务端 MCP）；
- 试图在未挂载阅读器的页面直接调用 `reader_jump_to_page` 等视口工具（应先走 `shelf_read_comic` 进入阅读器）；
- 尝试直接向外部用户输出 `/comic/...` 内部绝对路由而未附带 `temp_token` 沙箱票据；
- 把本节当成安全边界：门禁全在服务端（`_require_mcp_auth` 与签发处的隐藏本否决），本文件只是第二层防误操作——不装载本技能的 MCP 客户端一样受服务端约束，反之绕过本文件也绕不过服务端。

---

## 🔄 标准执行工作流 (Standard Workflow)

- [ ] Step 1: 识别意图与当前视口（书架 / 详情 / 章节 / 阅读器 / 发现榜单 / 外部） ⚠️ REQUIRED
- [ ] Step 2: 确认门禁检查（涉及全量离线缓存、车号导入需确认） ⚠️ REQUIRED
- [ ] Step 3: 分层调用 MCP 工具（服务端算力 ➔ 前端视口微操） ⛔ BLOCKING
- [ ] Step 4: 结果验证与降级交付 ⚠️ REQUIRED

---

## 🎯 核心场景决策流 (Decision Workflows)

### 1. 以图搜图 / 分镜查源 (Visual Search)

1. 调用服务端 MCP `search_by_image(image_base64, limit=5)`；
2. **命中（`score >= 0.40`）**：
   - **阅读器视口**：调用 WebMCP `reader_jump_to_page({ page: hit.page_index })` 精准跳页；
   - **书架/详情视口**：调用 WebMCP `shelf_read_comic({ source, source_id, page })` 开卷直达；
   - **外部聊天/非登录访客**：调用 `create_direct_pass(source, source_id, page_index)` 返回 2 小时沙箱票据直达链接；
3. **未命中（`score < 0.40`）**：统一回复：“未在本地私有库中检索到足够相似的画页特征，建议截取无对话框遮挡的整幅分镜，或提供台词对白线索。”

### 2. 台词全文检索 / 气泡定位 (Dialogue Search)

1. 提取关键词，调用服务端 MCP `search_by_dialogue(text, limit=5)`（`limit` 上限 50，`text` 不超过 200 字、至少 2 字）；每条结果是一整页，带 `bubble_count`（同页命中数）、`box` 与 `other_boxes`（同页其余命中气泡）和现成的 `reader_url`；
2. **命中台词记录**：
   - **书架视口**：调用 WebMCP `shelf_read_comic({ source, source_id, page, bubble_box })` 直达阅读器并触发朱砂金色气泡呼吸光效；
   - **阅读器视口**：调用 WebMCP `reader_locate_bubble({ page, box })` 聚焦气泡；
   - **外部聊天**：直接给 `reader_url` 不够（需要登录），走 `create_direct_pass`；
3. **字面未命中**：改用 `search_by_meaning(meaning, limit=5)` 按意思找（用户记得大意、记不清原话时直接用它）。它的 `similarity` 只在同一次查询的结果之间比高低，没有"命中阈值"，相关与否要读台词判断；`reason` 非空表示这次没真正检索（`query_too_short` 换个完整说法；`encoder_unavailable` 等是环境状态，别重试）；
4. **两条腿都落空**：再回退 `query_shelf(keyword=...)` 做作品名/作者模糊兜底。

### 2.1 按剧情取台词原文 (Story Context)

- 需要连续读一段剧情（总结、续写、找前因后果）时，用 `get_story_context(source, source_id, page_start, page_end, budget_lines)`：按页码与阅读顺序给原始台词，不带高亮；
- **`truncated=true` 表示没取完**（行预算撞顶或页跨度被夹到 200 页），按返回的 `requested_pages` 接着往后取，不要把片段当全书；
- 书不在库里会返回 `isError`，这和"这本没有台词"（`lines` 为空）是两回事。

### 3. 淘书推荐与作品管理 (Browse & Management)

- **藏书淘选**：调用 `recommend_unread(tag=...)` 或 `query_shelf(status='unread', favorite=true)`；
- **书架操作**：调用 WebMCP `shelf_pick_random()`（随机开卷）或 `shelf_open_comic()`；
- **单本/批量收录**：调用 WebMCP `shelf_import_comic({ id: ... })` 或 `shelf_batch_import_comics({ items: "JM111111, JM222222" })`（上限 50 本，内部 1.5s 安全间隔串行防风控）；
- **详情与章节**：调用 WebMCP `detail_start_reading()`、`detail_open_chapter({ chapter_id })`、`detail_toggle_favorite()`；
- **发现与榜单**：调用 WebMCP `discovery_get_ranking({ timeframe })` 查榜，`discovery_switch_timeframe` 切榜，`discovery_switch_source` 切换榜源，`discovery_open_detail` 查看榜单详情，`discovery_ingest_comic()` 或 `shelf_import_comic()` 收录。

### 4. 阅读器微操 (Reader Remote Control)

- **排版与缩放**：`reader_switch_mode({ mode: 'waterfall' | 'single' | 'double' | 'horizontal' | 'manga_rtl' })`，`reader_switch_fit({ fit: 'fit_width' | 'fit_height' | 'fit_both' | 'original' })`；
- **翻页与跳章**：`reader_turn_page({ direction })`，`reader_toggle_auto_turn({ enable, interval_seconds })`，`reader_jump_chapter({ direction })`；
- **收藏红心**：`reader_toggle_favorite({ favorite })`。

---

## 🛠️ MCP 核心工具全景 (Tools Quick Reference)

- **服务端数据面 (Server MCP，9 工具 / 2 提示词)**:
  `search_by_image`（识图）, `search_by_dialogue`（台词 FTS5）, `search_by_meaning`（按意思找台词，分数只在同一次查询内比高低）, `query_shelf`（多维检索）, `get_comic_detail`（章节目录元数据）, `recommend_unread`（未读淘书）, `create_direct_pass`（沙箱票据）, `get_shelf_stats`（全库统计）, `get_story_context`（按剧情原序取原始台词）；提示词 `find_comic_by_scene`（凭场景线索找本）、`recommend_comic`（按口味推荐）
- **前端视口操作面 (Frontend WebMCP)**:
  - `书架 (useShelfWebMCP)`: `shelf_search_comics`, `shelf_search_dialogue`, `shelf_search_image`, `shelf_read_comic`, `shelf_pick_random`, `shelf_open_comic`, `shelf_import_comic`, `shelf_batch_import_comics`
  - `详情 (useComicDetailWebMCP)`: `detail_start_reading`, `detail_cache_all_pages`, `detail_cache_chapter`, `detail_open_chapter`, `detail_get_comic_info`, `detail_toggle_favorite`, `detail_create_direct_pass`
  - `阅读器 (useReaderWebMCP)`: `reader_jump_to_page`, `reader_turn_page`, `reader_switch_mode`, `reader_switch_fit`, `reader_toggle_auto_turn`, `reader_locate_bubble`, `reader_jump_chapter`, `reader_toggle_favorite`
  - `发现 (useDiscoveryWebMCP)`: `discovery_get_ranking`, `discovery_switch_timeframe`, `discovery_switch_source`, `discovery_open_detail`, `discovery_ingest_comic`

---

## 🚫 反模式与避坑红线 (Anti-Patterns)

| 严禁做法 (Anti-Pattern)                 | 正确做法 (Correct Pattern)                                              |
| :-------------------------------------- | :---------------------------------------------------------------------- |
| 对外直接输出无 Token 的内网链接         | 调用 `create_direct_pass` 签发临时 2h 单本沙箱链接                      |
| 在单本沙箱（isDirectPass）下注册 WebMCP | 单本沙箱读者全面休眠 WebMCP 注册，严格防范外部 Agent 越权渗透与高频探测 |
| 在非阅读器页面调用 `reader_*` 工具      | 检查当前视口，优先调用 `shelf_read_comic` 导航直达                      |
| 外部再次对 JM 画页做反混淆解密          | 纸间后端已自动完成解密保存，直接按标准 WebP 读取                        |
| 一次性拉取全量藏书详情                  | 使用 `query_shelf` 分页或 `get_shelf_stats` 聚合统计                    |

---

## ✅ 交付前自检清单 (Pre-Delivery Checklist)

- [ ] **意图与视口对齐**：调用的 WebMCP 工具与用户当前所在页面一致；
- [ ] **外部直达票据合规**：非内网直连请求已附带 `create_direct_pass` 签发的 2h 临时 Token；
- [ ] **重度操作获得确认**：执行全量离线下载或新车号导入前已向用户确认；
- [ ] **未命中降级友好**：识图/对白检索无结果时提供了清晰的替代检索建议。
