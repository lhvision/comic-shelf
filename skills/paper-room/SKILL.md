---
name: paper-room
description: '纸间 (Paper Room) 本地漫画收藏馆智能体协同与决策指南。当用户需要以图搜图、分镜识图找漫画、台词全文检索、名对白定位、书架筛选过滤、淘书与题材推荐、阅读器遥控（翻页/跳页/排版切换/气泡高亮聚焦）、一键收录漫画、或生成单本沙箱直达分享链接时使用。触发词包括：以图搜图、搜这本漫画出处、找台词、这句台词出自哪里、翻到下一页、阅读器切换瀑布流、推荐未读漫画、签发单本阅读链接、阅读器遥控、漫画详情。'
metadata:
  author: lhvision
  version: '1.3.0'
  tags: ['comic-shelf', 'mcp', 'webmcp', 'agent-skill', 'image-search', 'dialogue-fts']
---

# 纸间 · 智能体协同与决策指南 (Paper Room Agent Skill)

> **品牌定位**：纸间 Paper Room — 本地优先的个人漫画收藏夹，专注于私有阅览室体验与视觉/台词精准召回。

---

## ⚡ IRON LAW

1. **零全库遍历**：严禁无条件并发全库扫描，多维检索必须使用 `query_shelf` 分页或 `get_shelf_stats` 统计。
2. **访客沙箱隔离**：向外部读者或群聊分享漫画一律调用 `create_direct_pass` 签发 2 小时临时阅读票据，严禁暴露馆长密钥与全站视图。
3. **视口生命周期感知**：前端 WebMCP 工具强绑定当前活动页面（Vue Scope），离开页面时自动注销。调用报错时引导用户导航至对应页面，严禁盲目死循环重试。
4. **重操作确认门禁**：执行全量离线缓存（`detail_cache_all_pages`）或外部新漫画收录（`shelf_import_comic`）前，必须向用户确认。

### 🚩 Red Flag Signals (出现以下情况立即中止并自查)

- 试图在前端 WebMCP 中寻找识图（ORB）或全文分词（FTS5）底层计算工具（必须走服务端 MCP）；
- 试图在未挂载阅读器的页面直接调用 `reader_jump_to_page` 等视口工具（应先走 `shelf_read_comic` 进入阅读器）；
- 尝试直接向外部用户输出 `/comic/...` 内部绝对路由而未附带 `temp_token` 沙箱票据。

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

1. 提取关键词，调用服务端 MCP `search_by_dialogue(text, limit=5)`；
2. **命中台词记录**：
   - **书架视口**：调用 WebMCP `shelf_read_comic({ source, source_id, page, bubble_box })` 直达阅读器并触发朱砂金色气泡呼吸光效；
   - **阅读器视口**：调用 WebMCP `reader_locate_bubble({ page, box })` 聚焦气泡；
3. **未命中**：自动回退调用 `query_shelf(keyword=...)` 进行作品名/作者模糊兜底。

### 3. 淘书推荐与作品管理 (Browse & Management)

- **藏书淘选**：调用 `recommend_unread(tag=...)` 或 `query_shelf(status='unread', favorite=true)`；
- **书架操作**：调用 WebMCP `shelf_pick_random()`（随机开卷）或 `shelf_open_comic()`；
- **详情与章节**：调用 WebMCP `detail_start_reading()`、`detail_open_chapter({ chapter_id })`、`detail_toggle_favorite()`；
- **发现与榜单**：调用 WebMCP `discovery_get_ranking({ timeframe })` 查榜，`discovery_ingest_comic()` 或 `shelf_import_comic()` 收录。

### 4. 阅读器微操 (Reader Remote Control)

- **排版与缩放**：`reader_switch_mode({ mode: 'waterfall' | 'single' | 'double' | 'horizontal' | 'manga_rtl' })`，`reader_switch_fit({ fit: 'fit_width' | 'fit_height' | 'fit_both' | 'original' })`；
- **翻页与跳章**：`reader_turn_page({ direction })`，`reader_toggle_auto_turn({ enable, interval_seconds })`，`reader_jump_chapter({ direction })`。

---

## 🛠️ MCP 核心工具全景 (Tools Quick Reference)

- **服务端数据面 (Server MCP)**:
  `search_by_image`（识图）, `search_by_dialogue`（台词 FTS5）, `query_shelf`（多维检索）, `get_comic_detail`（章节目录元数据）, `recommend_unread`（未读淘书）, `create_direct_pass`（沙箱票据）, `get_shelf_stats`（全库统计）
- **前端视口操作面 (Frontend WebMCP)**:
  - `书架 (useShelfWebMCP)`: `shelf_search_comics`, `shelf_search_dialogue`, `shelf_search_image`, `shelf_read_comic`, `shelf_pick_random`, `shelf_open_comic`, `shelf_import_comic`
  - `详情 (useComicDetailWebMCP)`: `detail_start_reading`, `detail_cache_all_pages`, `detail_cache_chapter`, `detail_open_chapter`, `detail_get_comic_info`, `detail_toggle_favorite`, `detail_update_metadata`, `detail_create_direct_pass`
  - `阅读器 (useReaderWebMCP)`: `reader_jump_to_page`, `reader_turn_page`, `reader_switch_mode`, `reader_switch_fit`, `reader_toggle_auto_turn`, `reader_locate_bubble`, `reader_jump_chapter`
  - `发现 (useDiscoveryWebMCP)`: `discovery_get_ranking`, `discovery_switch_timeframe`, `discovery_ingest_comic`

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
