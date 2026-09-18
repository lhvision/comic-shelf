---
name: paper-room
description: 纸间 (Paper Room) 本地漫画收藏馆智能体协同与决策指南。指导 AI Agent 如何通过服务端 MCP (FastAPI /mcp/sse)、前端 WebMCP (Chrome Model Context) 与 REST API 协同完成以图搜图、台词全文检索、书架筛选、阅读器遥控与单本沙箱票据签发。
metadata:
  author: lhvision
  version: '1.0.0'
  tags: ['comic-shelf', 'mcp', 'webmcp', 'agent-skill', 'image-search', 'dialogue-fts']
---

# 纸间 · 智能体协同与决策指南 (Paper Room Agent Skill)

> **品牌定位**：纸间 Paper Room — 本地优先的个人漫画收藏夹，专注于私有阅览室体验与视觉/台词精准召回。

---

## 🧭 三位一体架构定位 (Architecture Overview)

纸间采用 **“后端数据面 (Server MCP) + 前端视口操作面 (Frontend WebMCP) + 智能体决策心智 (Agent Skill)”** 三位一体架构：

```text
┌────────────────────────────────────────────────────────────┐
│                AI Agent (Claude / Antigravity)             │
│                 《纸间领域业务说明书 (SKILL.md)》            │
└─────────────────────────────┬──────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌───────────────────────────┐   ┌────────────────────────────┐
│ 服务端 MCP (Data Plane)    │   │ 前端 WebMCP (Operator)     │
│ - FastAPI /mcp/sse / stdio│   │ - Chrome Model Context     │
│ - search_by_image (ORB)   │   │ - 视口生命周期绑定 (Vue Scope)│
│ - search_by_dialogue(FTS5)│   │ - 翻页/跳页/排版/气泡聚焦  │
│ - create_direct_pass      │   │ - 零 DOM 模拟与跨页安全降级 │
└───────────────────────────┘   └────────────────────────────┘
```

---

## 🎯 核心场景决策树 (Decision Trees)

### 场景一：用户提供分镜截图 / 表情包求出处 (Visual Search Workflow)

```text
1. 接收图片 Base64 / 数据
   │
   ▼
2. 调用服务端 MCP [search_by_image(image_base64, limit=5)]
   │
   ├── 命中 (score >= 0.40):
   │   ├── (A) 读者在 Web 浏览器阅读器视口内:
   │   │   └─► 调用前端 WebMCP [reader_jump_to_page({ page: hit.page_index })]
   │   │
   │   ├── (B) 读者在书架首页视口:
   │   │   └─► 调用前端 WebMCP [shelf_read_comic({ source, source_id, page })]
   │   │
   │   └── (C) 外部聊天群 / 访客求直达链接:
   │       ├─► 调用服务端 MCP [create_direct_pass(source, source_id, page_index)]
   │       └─► 返回带 2 小时单本沙箱临时票据的阅读链接 (如 /comic/jm/523607?page=12&temp_token=...)
   │
   └── 未命中: 提示用户尝试截取更大面积、更少遮挡的分镜或提供台词线索
```

### 场景二：用户提供台词片段 / 名对白求漫画 (Dialogue Search Workflow)

```text
1. 提取台词关键词
   │
   ▼
2. 调用服务端 MCP [search_by_dialogue(text, limit=5)]
   │
   ├── 命中台词记录:
   │   ├─► 返回漫画标题、具体页码、上下文高亮 (<mark>...</mark>)
   │   │
   │   ├── 若在书架视口: 调用 [shelf_read_comic({ source, source_id, page, bubble_box })]
   │   │   └─► 阅读器自动直达该页并在气泡坐标处呈现朱砂金色呼吸光效 2 秒
   │   │
   │   └── 若在阅读器视口: 调用 [reader_locate_bubble({ page, box })]
   │
   └── 未命中: 调用 [query_shelf(keyword=...)] 进行标题/作品名模糊兜底
```

### 场景三：读者让 Agent 淘书或推荐藏书 (Recommendation Workflow)

```text
1. 分析读者喜好 (如 "纯爱", "全彩", "单行本")
   │
   ▼
2. 调用服务端 MCP [recommend_unread(tag=..., limit=5)] 或 [query_shelf(status='unread', favorite=true)]
   │
   ▼
3. 结合 [get_comic_detail] 获取章节目录与总页数，向读者推荐并生成直达阅读链接
```

---

## 🛠️ MCP 工具清单与契约 (Tools Full Matrix)

### 1. 服务端数据面工具 (Backend MCP Tools)

| 工具名               | 入参说明                                                                     | 出参 / 核心职责                                                      |
| -------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `search_by_image`    | `image_base64: string, limit?: int`                                          | ORB 局部特征识图比对，返回漫画 ID、页码及相似度评分（`score`）       |
| `search_by_dialogue` | `text: string, source?: string, limit?: int`                                 | SQLite FTS5 (Trigram) 模糊检索台词，返回画页、气泡归一化坐标与上下文 |
| `query_shelf`        | `keyword?, tag?, tags?, source?, status?, favorite?, sort?, limit?, offset?` | 多维度检索与筛选藏书，返回符合条件的元数据列表与总数                 |
| `get_comic_detail`   | `source: string, source_id: string`                                          | 查询单本漫画完整结构化元数据、章节列表及离线缓存进度                 |
| `recommend_unread`   | `limit?: int, tag?: string, source?: string`                                 | 淘选读者尚未阅读的高分或符合题材的藏书                               |
| `create_direct_pass` | `source, source_id, page_index?, ttl_seconds?`                               | 签发单本沙箱临时直达阅读 Token 与专属链接（默认 2 小时有效）         |
| `get_shelf_stats`    | _(无参数)_                                                                   | 获取全站藏书、在读、完读、总画页数及高频标签分布                     |

### 2. 前端视口操作面工具 (Frontend WebMCP 4 大视口矩阵)

- **书架视口 (`useShelfWebMCP`)**：
  - `shelf_search_comics`：多维检索与过滤藏书；
  - `shelf_search_dialogue`：在书架触发台词全文检索；
  - `shelf_search_image`：上传图片进行视觉搜图；
  - `shelf_read_comic`：直接打开漫画并跳转到指定页码与气泡；
  - `shelf_pick_random`：随机淘选一本漫画直达；
  - `shelf_open_comic`：打开指定漫画详情页；
  - `shelf_import_comic`：输入车号收录新漫画。
- **详情与章节视口 (`useComicDetailWebMCP`)**：
  - `detail_start_reading`：开卷阅读（从第 1 页或上次进度）；
  - `detail_cache_all_pages` / `detail_cache_chapter`：触发离线缓存；
  - `detail_open_chapter`：进入单章节独立子路由；
  - `detail_get_comic_info`：获取完整元数据快照；
  - `detail_toggle_favorite`：切换红心收藏。
- **阅读器视口 (`useReaderWebMCP`)**：
  - `reader_jump_to_page`：精准跳到指定 1-based 页码；
  - `reader_turn_page`：步进翻页（`direction: "next" \| "prev"`）；
  - `reader_switch_mode`：切换布局排版（瀑布流 / 单页吸附 / 横向切页 / 分屏 / 日漫从右往左）；
  - `reader_switch_fit`：切换宽度/高度缩放适配；
  - `reader_toggle_auto_turn`：启闭自动翻页与调节速率；
  - `reader_locate_bubble`：朱砂呼吸光圈聚焦指定气泡；
  - `reader_jump_chapter`：跨话切换上一话/下一话。
- **发现与排行视口 (`useDiscoveryWebMCP`)**：
  - `discovery_get_ranking`：获取官方精选榜单；
  - `discovery_switch_timeframe`：切换日榜 / 周榜 / 月榜；
  - `discovery_ingest_comic`：一键收录排行榜漫画。

---

## 🚫 反模式与安全红线 (Anti-patterns & Safety Rules)

1. **零暴力全库遍历**：严禁在未带筛选条件时通过死循环并发拉取全量藏书详情，优先使用 `query_shelf` 分页或 `get_shelf_stats`；
2. **访客与沙箱隔离 (Single-Book Sandbox)**：对外部非登录用户或群聊，**绝不泄露馆长密钥**；统一调用 `create_direct_pass` 签发有时效的临时直达链接，受后端沙箱保护禁止访问书库全景；
3. **尊重视口生命周期**：前端 WebMCP 工具只在对应 Vue 页面存活时注册，离开视口即注销。Agent 遇工具不存在报错时应引导用户导航至对应页面，严禁盲目重试；
4. **JM 漫画图片解密**：若涉及底层文件分析，必须知晓 JM 漫画画页磁盘上已通过 `JmImageTool` 自动解密为成品 WebP，无需外部重复解混淆。
