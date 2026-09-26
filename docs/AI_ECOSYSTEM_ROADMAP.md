# 纸间 · 扩展生态与 AI 演进路线图（AI Ecosystem & Evolutionary Roadmap）

> 本文档记录纸间在完成多源收录（JM / Local / PicAcg）与阅读器核心基建后，关于**外部智能连接、AI 剧本与漫画创作、私有模型微调与互动游戏化**的探索性设计方案与演进蓝图。
>
> 与确定性架构决策记录（[ADR 0013](docs/adr/0013-picacg-provider-and-architecture-fidelity.md)、[ADR 0026](docs/adr/0026-central-data-hub-and-polyrepo-ecosystem.md)）解耦，本文档作为前瞻提案库与需求蓄水池，为后续各阶段的落地与重构提供设计参考。

---

## 🗺️ 演进阶段全景图

```text
┌─────────────────────────────────────────────────────────────┐
│ 阶段一：数据沉淀与接口开放 (Data Foundation & Open API)      │
│  - 哔咔 (PicAcg) 数据源已完美落地（确立多源扩展标准蓝图）    │
│  - 纸间 MCP Server 端点开发 (/mcp/sse, JSON-RPC 2.0)        │
│  - 定向临时直达链接 (One-Time Direct Pass)                  │
│  - 漫画台词全文与语义检索 (SQLite FTS5 Trigram + 向量召回)  │
│  - OCR 43 本 1764 页全量 v6 重跑完成，质量达标结案          │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 阶段二：外部生态连接 (Ecosystem Integration)                │
│  - 飞书以图搜图 Bot (Feishu Visual Search Bridge)           │
│  - 外部 TypeScript / Python Agent (多维推荐 / 自动化巡检)   │
│  - 硬件算力：当前在开发机常驻 ➔ 远期按需迁移 Mac mini        │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 阶段三：Galgame / AVG 剧本文案与创作工坊 (Narrative Pipeline) │
│  - 首个生成目标：Galgame / AVG 剧本文案                     │
│  - 第一版零代码：编写 Agent Skill 接纸间 MCP 检索台词参考   │
│  - 使用与分级：自用/分享朋友；全年龄云端 ➔ 成人向本机 14B    │
│  - 长远工坊：剧本生成 ➔ 分镜拆解 ➔ 图像扩散 ➔ 装订入馆      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 阶段四：私有垂直模型微调与自训练边界 (Domain Fine-Tuning)    │
│  - 判别模型定位（判官/精排）：对 OCR 无用，台词检索暂缓     │
│  - 自训练 3 大严格启动条件（首版跑通+评测集/通用不达标/语料）│
│  - 算力拓扑：开发机本地微调 + 14B+ 云端租卡 │
│  - Mac mini 暂未到位（ADR 0026），本地推理亦在开发机        │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 阶段五：2D 互动分支游戏 / 视觉小说 (Interactive AVG Engine)  │
│  - 分镜气泡智能切片 (Panel Segmentation) + 剧本分支选项汇流  │
│  - 剧情决策分支树编译 ➔ 轻量 Web Canvas 互动 AVG 游戏        │
└─────────────────────────────────────────────────────────────┘
```

---

## 一、 纸间端云双轨 MCP 与配套 Agent Skill（Backend MCP + Frontend WebMCP + Skill SOP Architecture）

### 1. 定位与“三位一体”架构设计（Why Backend MCP + Frontend WebMCP + Skill?）

在现代 AI Agent 生态中，纸间构建 **“数据中枢（后端 MCP） + 视口操作面（前端 WebMCP） + 决策心智（Agent Skill）”** 三位一体架构：

- **服务端 MCP（数据面与计算中枢 / Backend Data Plane）**：
  - 由 FastAPI 暴露 `/mcp/sse`，提供原子化的重型计算与存储检索 API（如 `search_by_image`、`search_by_dialogue`、`search_by_meaning`、`get_story_context`、`create_direct_pass`）；
  - 供外部独立 Agent（飞书 Bot、Claude Desktop、Antigravity）远程调用，强制 JSON Schema 校验。
- **前端 WebMCP（视口操作面 / Frontend Viewport Operator）**：
  - 基于 W3C / Chrome 浏览器级 `document.modelContext.registerTool()` 规范与 VueUse `useWebMCP` 构建；
  - **视口生命周期绑定**：仅在对应页面存活期间向浏览器内置 AI、扩展 Agent 或自动化测试驱动暴露微操工具（如阅读器跳页、翻页、模式切换，书架标签筛选）；离开视口即刻随 Vue Scope 自动注销，杜绝跨页面非法调用与脆弱 DOM 模拟点击。
- **Agent Skill（心智与工作流层 / Playbook & SOP）**：
  - 为 LLM 提供专属的《纸间领域业务说明书（`SKILL.md`）》；
  - **明确跨端协同顺序与决策树**：如“当读者发图求出处时，优先调用后端 `search_by_image` 检索漫画与页码；若在浏览器当前会话内，联动调用前端 `reader_jump_to_page` 直达该页；若用户提供了台词碎片，联动调用 `reader_locate_bubble` 聚焦对白气泡”；
  - **剧本创作取料参考**：编写剧本或生成故事时，指示 Agent 先行调用 `search_by_meaning` 或 `get_story_context` 汲取真实漫画台词的语气、口癖与情节推进作为上下文参考；
  - **规避反模式**：杜绝 Agent 盲目并发爬取全站目录，杜绝向未授权访客泄露管理接口。

### 2. 传输协议与生命周期

- **后端通道**：FastAPI `/mcp/sse`（标准 Server-Sent Events），或本地 stdio 管道。
- **前端通道**：Chrome `document.modelContext`，通过 VueUse `useWebMCP` 实现响应式状态与组件生命周期同步（挂载注册、销毁注销、安全降级）。

### 3. 工具清单（Tools Full Matrix）

#### (1) 后端数据面工具（Backend Data Tools）

- `search_by_image(image_bytes | image_base64)`：
  调用内部 `imsearch` 引擎比对局部特征，输出命中的漫画 `source`、`source_id`、具体页码及置信度。
- `search_by_dialogue(query, source?, limit=5)`：
  基于 SQLite FTS5（Trigram 分词）模糊检索台词与名对白，返回匹配漫画、具体画页、气泡归一化坐标与上下文。
- `search_by_meaning(query, source?, limit=5)`：
  基于 `bge-small-zh-v1.5` 向量嵌入进行台词语义检索，返回含义相似的台词、所属画页及归一化气泡坐标。
- `get_story_context(source, source_id, page_index, window=2)`：
  获取指定画页前后滑窗范围内的连贯台词序列，为剧情理解与故事生成提供上下文流。
- `query_shelf(keyword?, tag?, source?, limit?)`：
  多维检索书架藏书，返回符合条件的本子元数据与封面。
- `get_comic_detail(source, source_id)`：
  获取单本漫画的完整目录、章节划分与全局页数。
- `recommend_unread(user_id?, limit=5)`：
  基于读者的阅读进度与喜欢偏好，推荐同标签或同作者的未读藏书。
- `create_direct_pass(source, source_id, page_index=1, ttl_seconds=7200)`：
  签发单本锁定的带时效直达阅读链接。

#### (2) 前端视口操作面工具（Frontend WebMCP Tools 全量 4 大视口矩阵）

##### 1. 书架视口工具（Shelf Viewport / `useShelfWebMCP`）

- `shelf_search_comics({ keyword?, tag?, tags?, sortBy?, favoritesOnly?, readingStatus?, reset? })`：
  多维检索与过滤书架漫画藏书（支持标题/作者关键词、单标签/多标签复合 AND 筛选、排序规则、喜欢标记、阅读进度及前置清空重置）。
- `shelf_search_dialogue({ query, source?, limit? })`：
  基于 SQLite FTS5 全文索引在全站漫画分镜中检索台词对白，并返回匹配漫画、具体画页与气泡归一化坐标。
- `shelf_search_image({ image_base64 })`：
  通过传入图片的 Base64 编码数据在全库中进行视觉向量特征匹配，精准定位到所属漫画、画页及相似度评分。
- `shelf_read_comic({ source, source_id, page?, fromBeginning?, chapter_id?, bubble_box?, other_boxes?, bubble_text? })`：
  直接从书架打开指定漫画并跳转到特定画页阅读，可附带章节、强制首开、代表气泡坐标与同页其余命中气泡（`other_boxes`，最多 5 组静态描边）进行朱砂色呼吸光效高亮。
- `shelf_import_comic({ source, id?, source_id?, local_path?, prefetch_all?, prefetch_covers?, favorite?, tags?, open_after? })`：
  将远端或服务器本地漫画收录导入至书架（必须显式指定 `source` 图源 Provider 以杜绝多平台车号冲突；支持后台全本离线预缓存、初始喜欢标记、自定义标签追加与导入后自动直达详情页）。**【仅馆长权限】**
- `shelf_batch_import_comics({ source, items, prefetch_all?, prefetch_covers?, favorite?, tags? })`：
  批量收录导入多部漫画至本地书库（必须显式指定统一 `source` 图源 Provider，单批次严格同源；支持纯文本多行/逗号分隔或字符串数组，智能容错剥离 Markdown 列表点与序号，上限 50 本，内部 5s 安全间隔串行防风控并附带页面防误关保护；单本失败隔离容错）。**【仅馆长权限】**
- `shelf_pick_random({ favoritesOnly?, source?, openReader? })`：
  从当前书架藏书中随机淘选一本漫画，支持限定已标记喜欢或特定图源，并可选择直达详情页或直接进入阅读器。
- `shelf_open_comic({ source, source_id, chapter_id? })`：
  通过图源和车号直达打开指定漫画的详情页或章节专注子路由。

##### 2. 详情与章节视口工具（Detail & Chapter Viewport / `useComicDetailWebMCP`）

- `detail_start_reading({ page?, chapter_id?, fromBeginning? })`：
  启动当前漫画阅读器（支持从第 1 页开篇、从上次历史进度继续、直达指定页码或直达特定章节开卷）。
- `detail_cache_all_pages()`：
  触发服务端后台将当前漫画全本所有画页进行缓存与解密。**【仅馆长权限】**
- `detail_cache_chapter({ chapter_id? })`：
  触发服务端后台将当前漫画指定章节的所有画页进行缓存与解密。**【仅馆长权限】**
- `detail_open_chapter({ chapter_id })`：
  进入当前漫画指定章节的独立子路由专注页。
- `detail_get_comic_info()`：
  获取当前漫画完整元数据、缓存进度比例、全书章节目录及上次阅读记录快照。
- `detail_toggle_favorite({ favorite? })`：
  切换或显式设定当前漫画的喜欢（喜欢/取消喜欢）状态。
- `detail_create_direct_pass({ page?, ttl_seconds? })`：
  为当前漫画签发单本沙箱临时直达阅读链接（携带独立 `temp_token`，默认有效时长 2 小时，受访者仅能阅读当前漫画且无法访问书架其他私密典藏与写接口）。**【仅馆长权限】**

##### 3. 阅读器视口工具（Reader Viewport / `useReaderWebMCP`）

- `reader_jump_to_page({ page })`：
  在当前打开的漫画阅读器中，精准跳转至指定的 1-based 全局页码。
- `reader_turn_page({ direction: "next" | "prev", count? })`：
  在阅读器中向前或向后步进翻页（支持多页并排与分屏模式，支持传入 `count` 一次连翻多页/多屏）。
- `reader_switch_mode({ mode?, pagesPerView?, direction?, seamless? })`：
  动态配置与切换阅读器排版布局（排版模式：瀑布流/单页吸附/横向切页；分屏：1/2/4页；翻页方向：从左往右 / 从右往左日漫模式；无缝连续拼接滚动）。
- `reader_switch_fit({ fit: "width" | "height" })`：
  切换画页在阅读视口中的缩放适配策略（适应宽度 / 适应高度）。
- `reader_toggle_auto_turn({ enable?, interval? })`：
  开启、关闭自动翻页功能，或调节自动翻页倒计时秒数间隔。
- `reader_toggle_favorite({ favorite? })`：
  在阅读器中快速切换或显式设定当前漫画的喜欢状态。
- `reader_locate_bubble({ page, box?, text? })`：
  定位画页并以朱砂色呼吸线框高亮指定的对白气泡框。
- `reader_jump_chapter({ direction: "next" | "prev" })`：
  在多章节漫画中跨话切换上一话或下一话。

##### 4. 发现与排行视口工具（Discovery Viewport / `useDiscoveryWebMCP`）

- `discovery_get_ranking({ timeframe?, refresh?, limit?, category? })`：
  获取官方精选与排行数据（周榜/月榜/日榜），支持数量截取与题材过滤，返回作品标题、作者、分类标签及是否已收录状态。
- `discovery_switch_timeframe({ timeframe: "week" | "month" | "day" })`：
  切换精选榜单的时间跨度分类标签。
- `discovery_ingest_comic({ source_id, open_after? })`：
  一键将排行榜中的指定漫画收录导入至本地书库（后台自动开启预缓存，支持收录后直达详情页）。**【仅馆长权限】**
- `discovery_open_detail({ source?, source_id })`：
  导航进入榜单中某本漫画的详情页。

#### (3) WebMCP 角色与权限分层模型（Curator vs Guest vs Direct Pass）

WebMCP 作为运行在浏览器宿主内的模型上下文通道，遵循**最小权限与按需暴露**原则：

| 操作分类                 | 涵盖工具                                                                                                                                                                                                                                                                                                        | 馆长（Curator） |     访客（Guest Pass）      |      单本直达（Direct Pass）      | 权限防线机制                                                                                                                                               |
| :----------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------: | :-------------------------: | :-------------------------------: | :--------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **视口阅读与排版控制**   | `reader_jump_to_page`<br>`reader_turn_page`<br>`reader_switch_mode`<br>`reader_switch_fit`<br>`reader_toggle_auto_turn`<br>`reader_locate_bubble`<br>`reader_jump_chapter`                                                                                                                                      |     ✅ 允许     |           ✅ 允许           |    ❌ 零暴露（不注册进上下文）    | **Zero MCP Attack Surface**：单本沙箱彻底全局关停 WebMCP，避免外部 AI Agent / 自动化爬虫脚本高频批量刷页抓取；临时受访者仅允许使用原生鼠标/触摸/键盘阅读。 |
| **书架淘书与检索查询**   | `shelf_search_comics`<br>`shelf_search_dialogue`<br>`shelf_search_image`<br>`shelf_pick_random`<br>`shelf_open_comic`<br>`shelf_read_comic`<br>`detail_start_reading`<br>`detail_open_chapter`<br>`detail_get_comic_info`<br>`discovery_get_ranking`<br>`discovery_switch_timeframe`<br>`discovery_open_detail` |     ✅ 允许     |  ✅ 允许（自动过滤隐藏本）  | ❌ 零暴露（路由守卫踢回单本阅读） | 只读查询；访客查询书架时后端自动应用 `hidden_from_guest` 隐私白名单过滤；单本直达用户全局关闭 WebMCP，且路由层禁止进入书架与发现。                         |
| **偏好与喜欢标记**       | `reader_toggle_favorite`<br>`detail_toggle_favorite`                                                                                                                                                                                                                                                            |     ✅ 允许     |  ✅ 允许（本地访客通行证）  |    ❌ 零暴露（不注册进上下文）    | 访客标记喜欢保存在客户端 IndexedDB 本地账本；临时沙箱用户不开放标记工具。                                                                                  |
| **藏书收录**             | `shelf_import_comic`<br>`discovery_ingest_comic`                                                                                                                                                                                                                                                                |     ✅ 允许     | ❌ 零暴露（不注册进上下文） |    ❌ 零暴露（不注册进上下文）    | 前端 `canWrite` 哨兵在注册层直接掐断（`undefined` 不注册进 `document.modelContext`，Agent 零感知无 token 浪费），后端对直接 API 写入执行 403 强校验。      |
| **单本直达链接签发**     | `detail_create_direct_pass`                                                                                                                                                                                                                                                                                     |     ✅ 允许     | ❌ 零暴露（不注册进上下文） |    ❌ 零暴露（不注册进上下文）    | 前端 `canWrite` 哨兵在注册层直接掐断，后端无条件执行 `require_curator` 强校验，严禁二次转签。                                                              |
| **服务端全本预缓存触发** | `detail_cache_all_pages`<br>`detail_cache_chapter`                                                                                                                                                                                                                                                              |     ✅ 允许     | ❌ 零暴露（不注册进上下文） |    ❌ 零暴露（不注册进上下文）    | 防止访客消耗服务器大带宽与解密算力，前端注册层直接掐断，后端中间件执行 403 强阻断。                                                                        |

---

## 二、 外围智能生态与群聊机器人（Feishu / QQ Bot Integration）

### 1. 架构拓扑与多项目独立性

- **物理分仓独立演进**：飞书 / QQ 搜图 Bot 作为独立的微服务项目（如 `paper-feishu-bot`，基于 Node/Bun/TypeScript 或 Python），遵循 [ADR 0026](docs/adr/0026-central-data-hub-and-polyrepo-ecosystem.md) 多项目独立仓库规范，绝不侵入纸间核心读者端代码；
- **通道协议标准连接**：Bot 接收到群聊或私聊中的图片与指令后，通过标准 MCP 协议（`POST /api/mcp/rpc` 或 `/api/mcp/sse`）及 REST API 与纸间通信；
- **凭据隔离（MCP Token Auth）**：Bot 配置专用的 `COMIC_SHELF_MCP_TOKEN`，享有只读机器级接口接入权，与馆长 Web 端登录凭据（`COMIC_SHELF_SECRET`）严格隔离。

### 2. 机器人群私双轨权限分流（Group vs Private Chat Dual-Track Gating）

为坚守“纸间是馆长的私人漫画收藏室，只有馆长本人才能收录与全本缓存”的不变量，Bot 实施群聊与私聊的严格双轨权限分流：

| 交互场景                     | 目标用户                       | 开放功能与工具                                                                                                                                        | 权限防线机制                                                                                                                                              |
| :--------------------------- | :----------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **群聊交互（Public Group）** | 所有群成员 / 陌生群友          | • 以图搜图（`search_by_image`）<br>• 台词全文搜书（`search_by_dialogue` / `search_by_meaning`）<br>• 签发单本沙箱免密阅读链接（`create_direct_pass`） | **绝对只读 + 沙箱限制**：群聊中彻底屏蔽入库与缓存指令。即使群友发送车号，Bot 亦静默忽略或报错拒绝；发出的链接严格锁死为单本沙箱，禁止看书架全貌。         |
| **私聊交互（Private DM）**   | 仅限白名单内的**馆长本人账号** | • 群聊全部搜图与查出处功能<br>• 车号一键收录入库（`POST /api/library/import`）<br>• 触发全本预缓存与转码                                              | **身份白名单强校验**：Bot 内部配置 `CURATOR_USER_IDS`。仅当消息来源为白名单私聊且持有馆长口令时，才调用纸间后端的作品收录与后台预缓存接口，群友无法触发。 |

### 3. 单本沙箱（Single-Book Sandbox）与动态时效策略（Dynamic TTL Allocation）

当群友在群里找本子出处并命中时，Bot 调用 `create_direct_pass` 签发临时阅读凭证：

1. **阅读范围物理死锁**：
   - 链接格式：`https://comic.yourdomain.com/comic/{source}/{source_id}/read/{page}?temp_token=...`；
   - 访客在浏览器打开后，后端中间件将权限限制为 `direct:{source}:{source_id}`。仅放行该本漫画的详情、章节与画页请求；任何试图访问书架列表（`/api/library`）或其他漫画的请求直接被 `403 Forbidden` 阻断；
   - 前端顶栏导航与结尾卡推荐彻底隐退，防止顺藤摸瓜外泄全站私人藏书；同时绑定 180 页/分钟令牌桶限流，防止脚本爬虫。
2. **长篇漫画动态时效（Dynamic TTL）**：
   - **短篇单行本（≤ 100 页）**：Bot 传入 `ttl_seconds=7200`（默认 2 小时有效），满足即时查证阅读；
   - **多章节 / 超长篇连载（> 100 页）**：Bot 可根据总页数或章节数自动将时效提升为 `ttl_seconds=86400`（24 小时 / 1 天有效），为读者提供充足完整的整卷阅览时间；
   - 系统支持最长 7 天（`ttl_seconds <= 604800`）配置。
3. **三重无残留自动清理机制（Triple Auto-Purge）**：
   - **即时查验**：SQL 查询硬绑定 `expires_at > now`，到期毫秒级自然失效；
   - **被动懒清理**：每次任何客户端签发新票据时，系统自动顺手执行 `DELETE FROM direct_passes WHERE expires_at <= now`，零额外后台进程开销；
   - **冷启动与级联删除**：FastAPI 后端重启时自愈清盘；馆长彻底删除某本漫画时，级联原子清空该作品所有历史签发外链。

---

## 三、 AI 漫画生成工坊与手稿回放（AI Comic Generation & Making-of Pipeline）

### 1. 双平台架构边界（Paper Studio 独立创作台 vs Paper Room 纯净展馆）

为防止将庞大的生图库（PyTorch、Diffusers、OpenCV、ComfyUI 依赖）与复杂创作交互侵入纸间核心读者端，系统确立 **“创作与消费松耦合”** 双平台架构：

- **纸间展馆（Paper Room / comic-shelf 本仓库）**：
  - **角色**：**读者端与轻量展览馆**。
  - **边界**：坚守纯净的本地优先阅读、书架管理与以图搜图；仅提供一个极轻量（≤150 行代码）的「手稿分层回放台（Making-of Player）」模态窗，通过原生 `new Path2D(d)` 零 DOM 消耗播放外部传入的矢量层；
  - **接口契约**：复用成熟的 `LocalProvider`（`POST /api/library/local/create`）一键收录已装订好的成品与伴生手稿资产（`.layers.json`）。
- **外部创作工坊（Paper Studio 独立平台 / Agent）**：
  - **角色**：**重型生产力工作台**（独立仓库或微服务）。
  - **边界**：承载分镜 Prompt 编排、ComfyUI 图像批量去噪、修脸修手、以及 **VTracer 矢量化分层压制**；生成完毕后通过 API 向纸间一键推送入库。

### 2. VTracer 智能矢量化分层管线（Raster-to-Vector Pipeline）

在 Paper Studio 后端利用 [visioncortex/vtracer](https://github.com/visioncortex/vtracer) 原生引擎对生图成品进行拓扑矢量化提取：

1. **色彩指纹探测与双预设路由**：
   - **黑白线稿（Manga Line Art）**：启用 `--preset bw --adaptive`，自适应二值化过滤网点噪点，生成极简锐利的单色骨架与墨线层（呈现“草稿 ➔ 勾线 ➔ 涂黑”）；
   - **全彩插画（Color Illustration）**：启用 `--clustering color-cluster --hierarchical stacked --filter-speckle 4`，多层次区域聚类堆叠（呈现“大块铺底色 ➔ 明暗阴影 ➔ 细节高光”）。
2. **伴生资产打包（`00001.layers.json`）**：
   - 将 VTracer 产出的分层贝塞尔曲线提炼为紧凑 JSON 格式（`[{ id: 1, type: "base", fill: "#f5f5f5", path: "M..." }, ...]`）；
   - 与原图 `00001.webp` 平级存放于 `backend/data/library/local/{id}/` 目录，体积比原始 XML SVG 减少 40%，且前端 0 解析损耗。

### 3. 纸间手稿回放台（Making-of Player）流式呈现

- **零 DOM 压力硬件加速**：前端直接利用 Canvas 2D 原生 `new Path2D(layer.path)` 与 WebGL 流式绘制，全过程跳过 DOM 树与 CSS 重排，稳定维持 120 FPS 丝滑动画；
- **沉浸式花絮交互**：作为详情页与阅读器的“制作过程 / 手稿生长”独立模态窗，提供时间轴进度条、分层独立显隐控制与运笔速度调节，完全不干扰主阅读心流。

### 4. 训练原料清洗：分镜裁切与对白脱敏（Panel & Dialogue Inpainting）

整页漫画直接喂入 LoRA 训练会导致模型强行记忆多格边框与破碎文字。在外部 Studio 洗料管线中引入自动化脱敏：

- **分镜切割（Panel Segmentation）**：利用轻量目标检测（YOLO/SAM）将整页自动裁切为单格独立分镜画面；
- **对白气泡抹除（Bubble Inpainting）**：检测气泡位置，以 LaMa / SD Inpaint 自动消除文字与气泡，生成纯净无字的原始角色/场景训练对。

### 5. 多模态伴生资产契约（Sidecar Asset Protocol）

`backend/data/library/local/{id}/pages/` 目录下统一收敛标准伴生文件命名空间：

- `{index}.layers.json`：VTracer 矢量分层生长路径；
- `{index}.panels.json`：分镜格子几何坐标 `[{ id, x, y, w, h }]`；
- `{index}.ocr.json`：分镜台词对白结构化转录；
- `{index}.caption.txt`：用于模型微调的 Booru / 自然语言标注提示词。

#### 契约细则：`{index}.ocr.json` 标准 Schema 与检索联动

```json
{
  "version": 1,
  "lang": "zh",
  "bubbles": [
    {
      "id": 1,
      "order": 1,
      "box": [0.12, 0.45, 0.28, 0.68],
      "text": "这就是最后的波纹吗……",
      "confidence": 0.98,
      "orientation": "vertical",
      "type": "dialogue"
    }
  ]
}
```

- **归一化百分比坐标**：`box` 统一采用 `[ymin, xmin, ymax, xmax]` ∈ [0.0, 1.0]，与原图分辨率解耦，纯 CSS 原生百分比自适应，杜绝缩略图与原图尺寸换算开销；
- **台词全文索引表（`comic_dialogues_fts`）**：纸间后端基于 SQLite FTS5 原生 `tokenize='trigram'` 构建倒排索引，0 外部重依赖秒级模糊匹配中日文无空格文本；倒排只建在 `text_norm`（写入时统一折成简体字形）上，其余列全部 `UNINDEXED`，含 `reading_order`（页内阅读顺序）与 `kind`（`dialogue` 台词 / `paratext` 副文本；水印与页码等噪声不入库），检索侧固定只取 `dialogue`；
- **气泡呼吸高亮（Breathing Bubble Overlay）**：读者从搜索下拉点击台词命中直达阅读器对应页码（`?page=42&bubble_box=...&bubble_boxes=a;b&highlight_bubble=1`，一行代表一整页），画卷视口在该气泡坐标浮现朱砂金色半透明高亮框呼吸 2 秒淡出，代表气泡呼吸、同页其余命中气泡静态描边，零 DOM 重排且不扰乱主阅读流。

### 6. 服务间认证凭据与推送 Webhook（Machine-to-Machine Auth）

外部 Paper Studio 完成整本编排后，携带专用 `Machine API Token` 调用 `POST /api/library/local/create` 推送画页与伴生资产；纸间后端完成校验后自动触发缩略图预热并广播 `library_changed` 事件，前台书架即时无缝呈现。

### 7. 数据质量保障与关键暗礁防御（Critical Safeguards & Edge Cases）

在将 OCR 与剧本语料引入生产环境时，必须筑牢五道质量防线：

1. **伴生文件被动感知与幽灵索引清理（Sidecar Ingestion Sync & Ghost Index Mitigation）**：
   - 外部 Studio 产出 `{index}.ocr.json` 后，通过 `POST /api/library/:source/:source_id/ocr/sync` 或 CLI `bash scripts/ocr.sh sync` 增量同步进 SQLite FTS5，避免每次重启全盘轮询卡死；
   - 漫画被删除或重新装订（Re-binding）时，联动事务原子清空该作品所有 FTS5 记录，彻底杜绝“搜得出台词但画页不存在或页码错位”的幽灵索引。
2. **简繁双向互通归一化（Simplified/Traditional Bidirectional Search）**：✅ 已落地并升级
   - 汉化组多为港台或民间繁体，读者常输入简体。**台词出口采用索引侧归一**：`comic_dialogues_fts.text_norm` 在写入时折成简体字形，倒排只建这一列，查询侧单次归一，繁简混排行不再漏召回（全库 100% 可命中，展示与高亮仍保留页面原字形）；书架元数据出口因写入侧无法规范，继续走查询侧多组 `LIKE` OR 补偿。详见 [ADR 0017](docs/adr/0017-dialogue-search-fts5.md)「决策 2 · 修订」。
3. **气泡级多行文本几何聚类（Bubble-level Line Clustering）**：
   - 严禁把原始 OCR 吐出的碎片行直接存为独立气泡；外部管线必须按几何欧氏距离与排版流向聚类为完整对白句子，输出包围整个气泡的单个 `box`。
4. **主流引擎聚焦与开源语料冷启动（Engine Diversity Fallback & Open Corpus Cold Start）**：
   - Galgame 解包脚本聚焦成熟开放生态（KiriKiri / Ren'Py），杜绝从零发明通用解包器；优先引入开源社区已整理的中日双语平行语料库（JSONL）进行冷启动。
5. **图文双模联合检索（Multimodal Hybrid Search）**：
   - 搜索端点原生支持限定作品/作者下的台词搜索，识图结果页亦可带出命中页码的对白预览，形成图文双重校验。

### 8. OCR 识别管线与质量判定（不做自训练，v6 判定结案）

在漫画 OCR 识别与伴生数据生产上，确立明确边界与最终实测结论：

- **原则：不做自训练**：OCR 模型本身不进行私有微调或自训练。实践证明，提升识别质量最便宜、最立竿见影的手段是提升推理引擎的字符表覆盖与预/后处理规则，而非从零训练 OCR 网络。
- **历史基线与短板定位（2026-09-24 重跑前）**：
  - 书库 43 本 1764 页（全为 JM 源）中，日文 legacy（4 本 124 页，445 气泡）置信度中位数仅 0.64（低于 0.7 占 71.7%），旧引擎 v3 字符表仅包含 5 个假名，导致假名大面积被错误识别为形近汉字或乱码碎片；中文 legacy（38 本，7132 气泡）置信度中位数为 0.74。
- **全量 v6 重跑与复测结果（2026-09-25 验证）**：
  - 43 本 1764 页已全部使用 v6 引擎重跑（`bash scripts/ocr.sh run --source jm --force --workers 4`）并完成增量同步入库（`bash scripts/ocr.sh sync --source jm`）。
  - **复测统计指标**：
    - `jav6`（日文 v6，798 气泡）：置信度中位数跃升至 **0.97**（低于 0.7 仅 12.4%，竖排 0.98、横排 0.95），日文台词假名占比达 78.2%，随机抽样 10 条中 7 条完全通顺（读不通者仅 3 条，未超判定上限）；
    - `zhv6`（中文 v6，12407 气泡）：置信度中位数达 **0.97**（低于 0.7 仅 12.1%），随机抽样 10 条全部通顺；
    - 全库台词索引覆盖 43 本 1708 页，FTS 全文表 10889 行，向量索引 7426 条（15.2MB）。
- **结论与裁定**：
  - 日文 v6 置信度中位数 0.97 ≥ 0.9，且抽样通顺度达标，**判定正式结案**；
  - **不上 manga-ocr，亦不引入 comic-text-detector**，保持当前轻量、无复杂 PyTorch 重依赖的 ONNX Runtime GPU 架构。

---

## 四、 领域模型微调、判别模型与自训练边界（Domain Fine-Tuning & Model Boundaries）

### 1. 数据资产价值：漫画分镜与 Galgame 剧本双轨汇流

漫画具备极强的视觉-空间张力，而 Galgame 具备高度结构化的文学叙事与对白树。两者分轨沉淀，并在下游任务中按需投影：

- **黄金中日平行语料（Galgame Gold Parallel Corpus）**：
  - 存放于 `backend/data/corpus/galgame/{game_id}.jsonl`；
  - 每一行收录场景 ID、说话人（Speaker）、日文原文（`text_ja`）、中文译文（`text_zh`）与分支选项；
  - 官方双语与优质民间汉化文本按行天然 100% 严格对齐，信噪比极高，是微调**二次元专精翻译模型**的黄金级原材料。
- **漫画单语对话与分镜语料**：
  - 通过 `{index}.ocr.json` 沉淀海量漫画对白与语气助词，作为领域风格适配（Domain Adaptation）的无监督语料；
- **画风与角色视觉样本**：
  - 收集去字（Bubble Inpainting）后的纯净高清分镜，微调专属 Character / Style LoRA。

### 2. 二次元专精翻译模型落地路线（Anime Translation SFT Pipeline）

1. **语料抽取与清洗**：通过外部工坊脚本从主流引擎（Kirikiri/XP3、Siglus、CatSystem 等）解包提取中日双语对白，过滤乱码与系统控制符，沉淀标准 JSONL 平行对；
2. **领域 SFT 微调**：基于高质量开源底座（如 Qwen2.5-7B/14B、Gemma-2-9B）进行 LoRA 指令微调，专精二次元人称、口癖（如「〜のだ」「〜わ」「先輩」）、梗文化与特定语境；
3. **本地常驻推理**：训练完成的权重在本地常驻运行，为纸间未来收录的「日文生肉本子」提供本地 100% 离线、0 审查的即时汉化机翻。

### 3. 算力拓扑与训练位置：开发机本地微调 + 按需租卡

替代原方案中“训练一律在云端”的设想，结合现有硬件确立务实的算力拓扑：

- **本地开发机承担中小规模微调**：
  - **几亿参数的编码器（如 XLM-R 等）**：可在 12GB 显存内轻松进行**全参数微调**；
  - **7B / 8B 级生成底座（如 Qwen2.5-7B）**：采用 **QLoRA（4bit 量化低秩微调）**，配合较小的 Batch Size 与约 2k 的上下文序列长度，可在 12GB 显存内顺利微调；
  - **14B 及以上超大规模模型**：超出单卡训练显存阈值，采用按需租赁云端高显存算力卡（如 RTX 4090 / A100）集中微调；
  - **环境隔离提醒**：开发机当前的 `.venv-ocr` 虚拟环境仅包含 ONNX Runtime GPU 运行时，未安装 PyTorch。实际启动训练时需在外部独立创建专用的 PyTorch 训练环境。
- **本地推理现状与演进**：
  - 由于规划中的 Mac mini（Apple Silicon / MLX）暂未到位（[ADR 0026](docs/adr/0026-central-data-hub-and-polyrepo-ecosystem.md)），**当前本地推理亦在开发机上承载**；
  - 在关闭图形桌面等高显存应用后，可流畅推理 14B 参数的 4bit 量化模型（如通过 llama.cpp 提供 OpenAI 兼容的 HTTP 接口）。

### 4. 判别模型定位与台词检索重排（XLM-R / Reranker 判官，维持暂缓）

- **本质与定位**：
  - XLM-R 等编码器后接线性打分头（`Linear(768, 1)`），采用成对偏好（RLCD 式 `-log σ(r₁ - r₂)`）、二分类判断（BCE）、多选一（CE）、打分分布（软标签交叉熵）多任务联合训练；
  - 业内称此类模型为**精排模型（Reranker）**，其本质是“判官”：把 Query（查询）和 Candidate（候选文本）放在一起拼成单一序列输入，输出匹配概率或分数。**它不生成文字，也无法理解图像**。
- **针对各下游任务的效能评估**：
  - **对 OCR**：**没有帮助**。OCR 的核心瓶颈是文本行检测与字符识别解码，判别模型既不能切图也不能吐字，无法改善 OCR 准确率；
  - **对台词检索**：**维持暂缓**。它只能用来对 FTS5 / 向量召回的候选进行第二轮重排。然而当前纸间语义出口的主要使用者是 AI Agent（[ADR 0028](docs/adr/0028-dialogue-semantic-search.md)），Agent 依靠自身上下文理解就是更强大的判官；检索的瓶颈主要在脏 OCR 语料（现已通过 v6 重跑解决）且缺乏成规模的人类偏好评测集。后续若确实需要引入精排，**优先尝试现成开源的 `bge-reranker`（同类编码器架构，已成熟支持中日英多语言），坚决不自己从零训练**；
  - **对剧本生成**：**第一版完全用不上**。其能力仅限于对生成的多个候选文案打分挑选，或辅助语料离线打标，在首期零代码流程中属于过度设计。
- **维持暂缓的三个启用前提（缺一不可）**：
  1. **成规模的评测集与标注数据**：拥有成规模的“查询 → 应命中页”标注与成对偏好样本，否则无法证明其比当前排序更优；
  2. **满足毫秒级延迟预算**：书架与阅读器检索须维持亚秒响应，重排只能作用于极少量候选，且需实测 CPU/GPU 推理开销；
  3. **出现真实人类用户直接交互**：现阶段台词检索主要服务于 Agent 取料，待书架面向人类读者提供复杂查询界面时收益才成立。
- 本条仅作架构结论记录，**代码维持不动**。

### 5. 私有模型自训练启动条件（严格门禁：3 条件全部满足才启动）

自训练（无论是 LoRA 还是全参微调）伴随着沉重的数据清洗、Prompt 标注与超参数调试成本。为防范过度工程化，确立**三项硬性门禁条件，只有当且仅当 3 项全部满足时，才允许启动自训练**：

1. **第一版已跑通且有评测集**：基于 Agent Skill 的第一版剧本生成工作流已跑顺，并沉淀了**约 30 个典型场景、由人类馆长打分的小型评测集（Gold Benchmark）**；
2. **通用模型文风/人设稳定不达标**：评测集指标明确证实，通用的商业或开源大模型在文风还原度、人设一致性或二次元特定语境上**稳定不达标**，且经过详尽 Prompt 调整与检索参考注入（Few-shot Retrieval）后依然无法弥补；
3. **语料已彻底清洗重跑**：底层台词与剧本语料库已完成高质量清洗重构，38 本 legacy 侧车已全部用 v6 重跑完毕，副文本、水印与低质噪声已完全过滤。

_特别注意：当前漫画 OCR 侧车未标注说话人（Speaker）且无独立分镜信息（[ADR 0017](docs/adr/0017-dialogue-search-fts5.md) 决策不做说话人标注），在启动自训练前必须重新评估这一语料结构缺失对对话剧本微调的影响。_

---

## 五、 远期 Mac mini（Apple Silicon）Homelab 私有云演进

> **现状说明**：根据 [ADR 0026](docs/adr/0026-central-data-hub-and-polyrepo-ecosystem.md)，Mac mini 硬件**目前暂未到位**。当前阶段所有的本地离线推理与微调计算均在开发机上执行。本节作为未来硬件就绪后的低功耗私有云迁移与终态演进蓝图保留。

### 1. 为什么是 Mac mini？

- **统一内存（Unified Memory）优势**：CPU 与 GPU 共享内存（如 32GB/64GB/128GB）。结合苹果 **MLX** 框架或 **llama.cpp**，可以在内存中高效加载运行 14B~32B 参数的开源大模型，完全打破传统消费级显卡显存瓶颈；
- **全天候静音与低功耗**：整机待机仅数瓦，满负荷 30~50 瓦，无刺耳风扇噪音，适合作为 24 小时开机的家庭书房核心；
- **一体化架构**：单台设备同时跑 Docker（FastAPI 后端 + Vue 前端 + imsearch 搜图）与本地大模型推理端点。

### 2. 外接大容量硬盘柜（DAS）冷热分层存储拓扑

Mac mini 内置 SSD 加装成本高昂（通常为 512GB/1TB），面对海量漫画库与多模态模型文件需建立物理分层：

- **外接雷电 4 / USB-C 多盘位硬盘柜（DAS / RAID 阵列）**：格式化为 APFS 挂载至 `/Volumes/ComicStorage/data`，专供 `library/` 原图海量仓库、缓存画页与训练冷数据，彻底解放内置容量；
- **内置极速 SSD**：专供 macOS 系统、Docker 运行时、SQLite 数据库、以图搜图向量索引与 MLX 大模型热权重。

### 3. 端侧 100% 离线隐私 VLM（Apple Silicon MLX）

利用 Mac mini 的统一内存，在本地常驻运行开源视觉多模态大模型（如 `Qwen2.5-VL-7B/14B`）：

- **全天候自动打标**：对入库本子自动执行打标（Captioning）与剧情分镜理解，0 API 调用成本；
- **100% 隐私闭环**：私密漫画资产全生命周期不流出家庭局域网，彻底免除第三方云端 API 审查与封号风险。

---

## 六、 2D 互动游戏与 Galgame / AVG 剧本生成（Interactive AVG & Script Generation）

### 1. 生成方向与第一版形态（Galgame / AVG 剧本文案，零代码 Skill）

- **首个生成目标**：明确将**首个 AI 内容生成目标定为 Galgame / AVG 剧本文案**，而非过早投入高复杂度的全本图像扩散生成或分镜整页装订。
- **第一版形态：零代码落地（Zero-Code via Agent Skill）**：
  - **不提前自研生成微服务**：不编写专用的后端 Python 生成代码，而是编写一个专属的 **Agent Skill**；
  - **联动纸间 MCP 检索参考**：让接驳了纸间 MCP 的 Agent 在创作剧本时，主动调用 `search_by_meaning`（语义向量检索特定情境/情绪）、`search_by_dialogue`（关键词精准定位名台词）、`get_story_context`（提取上下文对话流）在本地高信噪比台词库中检索相似场景的经典台词作为 Few-shot 参考素材；
  - **生成剧本**：Agent 借鉴这些真实漫画分镜的台词风格、口癖、情绪张力与情节推进节奏，辅助撰写连贯的角色对白与分支剧情；
  - **输出格式契约**：纯文本 Markdown 剧本文案或 Ren'Py 脚本格式，开工实现 Skill 时根据下游需要确定。

### 2. 使用范围与内容分级策略（Content Rating & Dual Backend Strategy）

- **使用范围**：
  - **自用或分享朋友，绝不商用**。纯粹作为个人创作辅助与同好交流工具。
- **内容分级与双后端策略**：
  - **阶段一（全年龄题材）**：先用全年龄题材，搭配 Agent 自带的云端商业模型（如 Claude / Gemini），快速验证“检索本地相似台词作参考”这一提示词与取料工作流是否有效；
  - **阶段二（成人向 / R-18 题材）**：受制于云端 API 的内容合规审查限制，成人向题材切换为**开发机本地运行的开源大模型**。本地独立显卡（12GB 显存）在关闭高显存程序后，显存可流畅运行 **14B 参数的 4bit 量化模型**（如 Qwen2.5-14B-Instruct-GGUF via llama.cpp）。Claude Code / Agent 可通过切换 API Base URL 直连本地兼容端点，**上层 Skill 本身无需修改，实现前后端无缝切换**。

### 3. 技术路线抉择：为什么坚持 2D 路线？

- **3D WebGL / Blender MCP 的局限**：漫画本质是高度风格化的手绘 2D 艺术。当前 Image-to-3D 模型生成的 3D 资产拓扑杂乱、骨骼动作绑定困难，极易造成画风严重失真，投入产出比极低；
- **2D 互动视觉小说（AVG）的优势**：完美契合漫画资产特性，100% 保留原作细腻作画。

### 4. 长远演化管线：漫画分镜与 Galgame 剧本深度融合

1. **分镜切片与台词抽取**：利用轻量模型分割漫画分镜格子（Panel），OCR 抽取气泡对白生成 `{index}.ocr.json` 与 `{index}.panels.json`；
2. **多源剧本融合编译（Comic Panels + Galgame Scripts）**：
   - 将漫画的高清视觉分镜作为立绘/CG 演出舞台；
   - 将 `backend/data/corpus/galgame/` 提取的典型选择支、好感度分支与心理描写作为模板；
   - 由 LLM 解析剧情主线，自动生成玩家可参与的二选一/三选一抉择点，编译为紧凑的 AVG 决策状态机；
3. **Web 端轻量引擎**：利用 Web Canvas / Pixi.js 在纸间展馆中编译为零依赖、可在现代浏览器即点即玩的沉浸式 2D 互动分支视觉小说。

---

## 📌 下一步落地实施路径建议

在哔咔 (PicAcg) 数据源落地、台词检索与 OCR 全量达标的前提下，AI 生态落地推荐的阶梯路径：

1. **第一步（基础设施与数据底座，已结案 ✅）**：
   - 纸间 MCP 服务端与定向临时直达链接稳定上线；
   - 漫画台词全文与语义检索落地（SQLite FTS5 Trigram + bge-small 向量 + 气泡呼吸高亮）；
   - 全库 43 本 1764 页经 v6 重跑与 sync，日文置信度 0.97，质量达标结案，确认不上 manga-ocr。
2. **第二步（当前核心任务 · Galgame / AVG 剧本创作 Skill）**：
   - 编写首版零代码 Agent Skill，通过纸间 MCP 调用 `search_by_meaning`、`search_by_dialogue`、`get_story_context` 获取台词参考；
   - 坚持自用/分享朋友（不商用）；以全年龄题材在云端模型验证检索工作流 ➔ 成人向题材切换本地开源模型（14B 4bit）。
3. **第三步（质量评测与自训练门禁评估）**：
   - 沉淀约 30 个典型场景的人类打分评测集；
   - 严格审查自训练三大门禁条件（第一版已跑通、通用模型不达标、语料已清洗）；
   - 仅当三条件全部满足时，才在开发机上为 7B/8B 模型开启 QLoRA 领域微调（14B+ 则考虑租卡）；若通用模型表现优异，则继续保持零代码。
4. **第四步（长远 · 2D 互动 AVG 游戏引擎与 AI 漫画工坊）**：
   - 推进分镜切片与决策分支树编译为轻量 Web Canvas 视觉小说；
   - 视未来硬件采购情况平滑迁移至 Mac mini Homelab。
