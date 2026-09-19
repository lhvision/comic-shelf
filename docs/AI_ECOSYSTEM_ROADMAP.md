# 纸间 · 扩展生态与 AI 演进路线图（AI Ecosystem & Evolutionary Roadmap）

> 本文档记录纸间在完成多源收录（JM / Local / PicAcg）与阅读器核心基建后，关于**外部智能连接、AI 漫画创作、私有模型微调与互动游戏化**的探索性设计方案与演进蓝图。
>
> 与确定性架构决策记录（[ADR 0013](docs/adr/0013-picacg-provider-and-architecture-fidelity.md)、[ADR 0026](docs/adr/0026-central-data-hub-and-polyrepo-ecosystem.md)）解耦，本文档作为前瞻提案库与需求蓄水池，为后续各阶段的落地与重构提供设计参考。

---

## 🗺️ 演进阶段全景图

```text
┌─────────────────────────────────────────────────────────────┐
│ 阶段一：数据沉淀与接口开放 (Data Foundation & Open API)      │
│  - 哔咔 (PicAcg) 数据源已完美落地（确立多源扩展标准蓝图）    │
│  - 纸间 MCP Server 端点开发 (/mcp/sse)                      │
│  - 定向临时直达票据 (One-Time Direct Pass)                   │
│  - 漫画台词全文检索 (SQLite FTS5 + Trigram) 与气泡呼吸高亮  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 阶段二：外部生态连接 (Ecosystem Integration)                │
│  - 飞书以图搜图 Bot (Feishu Visual Search Bridge)           │
│  - 外部 TypeScript Agent (多维推荐 / 自动化巡检)            │
│  - 迁移部署至 Mac mini (Homelab 低功耗全天候私有云)          │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 阶段三：AI 漫画创作工坊 (AI Comic Generation Pipeline)       │
│  - 剧本大模型生成 ➔ 分镜 Prompt 拆解 ➔ 图像扩散批量生成      │
│  - 对接 LocalProvider 标准 API，一键装订入馆上架             │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 阶段四：私有垂直模型微调 (Domain Multimodal Fine-Tuning)     │
│  - Galgame 双语脚本 + 漫画 OCR 台词汇流为二次元平行语料库    │
│  - 云端租算力进行二次元翻译/剧情微调 ➔ Mac mini (MLX) 推理   │
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
  - 由 FastAPI 暴露 `/mcp/sse`，提供原子化的重型计算与存储检索 API（如 `search_by_image`、`search_by_dialogue`、`create_direct_pass`）；
  - 供外部独立 Agent（飞书 Bot、Claude Desktop、Antigravity）远程调用，强制 JSON Schema 校验。
- **前端 WebMCP（视口操作面 / Frontend Viewport Operator）**：
  - 基于 W3C / Chrome 浏览器级 `document.modelContext.registerTool()` 规范与 VueUse 15 `useWebMCP` 构建；
  - **视口生命周期绑定**：仅在对应页面存活期间向浏览器内置 AI、扩展 Agent 或自动化测试驱动暴露微操工具（如阅读器跳页、翻页、模式切换，书架标签筛选）；离开视口即刻随 Vue Scope 自动注销，杜绝跨页面非法调用与脆弱 DOM 模拟点击。
- **Agent Skill（心智与工作流层 / Playbook & SOP）**：
  - 为 LLM 提供专属的《纸间领域业务说明书（`SKILL.md`）》；
  - **明确跨端协同顺序与决策树**：如“当读者发图求出处时，优先调用后端 `search_by_image` 检索漫画与页码；若在浏览器当前会话内，联动调用前端 `reader_jump_to_page` 直达该页；若用户提供了台词碎片，联动调用 `reader_locate_bubble` 聚焦对白气泡”；
  - **规避反模式**：杜绝 Agent 盲目并发爬取全站目录，杜绝绕过访客门禁向群聊泄露管理员接口。

### 2. 传输协议与生命周期

- **后端通道**：FastAPI `/mcp/sse`（标准 Server-Sent Events），或本地 stdio 管道。
- **前端通道**：Chrome `document.modelContext`（`chrome://flags/#enable-webmcp-testing`），通过 VueUse `useWebMCP` 实现响应式状态与组件生命周期同步（挂载注册、销毁注销、安全降级）。

### 3. 工具清单（Tools Full Matrix）

#### (1) 后端数据面工具（Backend Data Tools）

- `search_by_image(image_bytes | image_base64)`：
  调用内部 `imsearch` 引擎比对局部特征，输出命中的漫画 `source`、`source_id`、具体页码及置信度。
- `search_by_dialogue(text, source?, limit=5)`：
  基于 SQLite FTS5（Trigram 分词）模糊检索台词与名对白，返回匹配漫画、具体画页、气泡归一化坐标与上下文。
- `query_shelf(keyword?, tag?, source?, limit?)`：
  多维检索书架藏书，返回符合条件的本子元数据与封面。
- `get_comic_detail(source, source_id)`：
  获取单本漫画的完整目录、章节划分与全局页数。
- `recommend_unread(user_id?, limit=5)`：
  基于当前读者的阅读进度与红心偏好，推荐同标签或同作者的未读藏书。
- `create_direct_pass(source, source_id, page_index=1, ttl_seconds=7200)`：
  签发单本锁定的带时效直达阅读链接。

#### (2) 前端视口操作面工具（Frontend WebMCP Tools 全量 4 大视口矩阵）

##### 1. 书架视口工具（Shelf Viewport / `useShelfWebMCP`）

- `shelf_search_comics({ keyword?, tag?, tags?, sortBy?, favoritesOnly?, readingStatus?, reset? })`：
  多维检索与过滤书架漫画藏书（支持标题/作者关键词、单标签/多标签复合 AND 筛选、排序规则、红心收藏、阅读进度及前置清空重置）。
- `shelf_search_dialogue({ query, source?, limit? })`：
  基于 SQLite FTS5 全文索引在全站漫画分镜中检索台词对白，并返回匹配漫画、具体画页与气泡归一化坐标。
- `shelf_search_image({ image_base64 })`：
  通过传入图片的 Base64 编码数据在全库中进行视觉向量特征匹配，精准定位到所属漫画、画页及相似度评分。
- `shelf_read_comic({ source, source_id, page?, fromBeginning?, chapter_id?, bubble_box?, bubble_text? })`：
  直接从书架打开指定漫画并跳转到特定画页阅读，可附带章节、强制首开与对白气泡坐标进行朱砂色呼吸光效高亮。
- `shelf_import_comic({ id?, source_id?, source?, local_path?, prefetch_all?, prefetch_covers?, favorite?, tags?, open_after? })`：
  将远端或服务器本地漫画收录导入至书架（支持省略 `source` 自动智能推断图源、支持后台全本离线预缓存、初始喜欢标记、自定义标签追加与导入后自动直达详情页）。**【仅馆长权限】**
- `shelf_pick_random({ favoritesOnly?, source?, openReader? })`：
  从当前书架藏书中随机淘选一本漫画，支持限定已收藏或特定图源，并可选择直达详情页或直接进入阅读器。
- `shelf_open_comic({ source, source_id, chapter_id? })`：
  通过图源和车号直达打开指定漫画的详情页或章节专注子路由。

##### 2. 详情与章节视口工具（Detail & Chapter Viewport / `useComicDetailWebMCP`）

- `detail_start_reading({ page?, chapter_id?, fromBeginning? })`：
  启动当前漫画阅读器（支持从第 1 页开篇、从上次历史进度继续、直达指定页码或直达特定章节开卷）。
- `detail_cache_all_pages()`：
  触发服务端后台将当前漫画全本所有画页进行离线预缓存与解密。**【仅馆长权限】**
- `detail_cache_chapter({ chapter_id? })`：
  触发服务端后台将当前漫画指定章节的所有画页进行离线预缓存与解密。**【仅馆长权限】**
- `detail_open_chapter({ chapter_id })`：
  进入当前漫画指定章节的独立子路由专注页。
- `detail_get_comic_info()`：
  获取当前漫画完整元数据、离线缓存进度比例、全书章节目录及上次阅读记录快照。
- `detail_toggle_favorite({ favorite? })`：
  切换或显式设定当前漫画的红心收藏（喜欢/取消喜欢）状态。
- `detail_update_metadata({ title?, authors?, tags?, description?, cover_indices? })`：
  就地编辑修改漫画的标题、作者列表、分类标签、简介及 4 张展示封面页码序号。**【仅馆长权限】**

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
  在阅读器中快速切换或显式设定当前漫画的红心收藏状态。
- `reader_locate_bubble({ page, box?, text? })`：
  定位画页并以朱砂色呼吸线框高亮指定的对白气泡框。
- `reader_jump_chapter({ direction: "next" | "prev" })`：
  在多章节漫画中跨话切换上一话或下一话。

##### 4. 发现与排行视口工具（Discovery Viewport / `useDiscoveryWebMCP`）

- `discovery_get_ranking({ timeframe?, refresh?, limit?, category? })`：
  获取禁漫官方精选与排行数据（周榜/月榜/日榜），支持数量截取与题材过滤，返回作品标题、作者、分类标签及是否已收录状态。
- `discovery_switch_timeframe({ timeframe: "week" | "month" | "day" })`：
  切换官方精选榜单的时间跨度分类标签。
- `discovery_ingest_comic({ source_id, open_after? })`：
  一键将排行榜中的指定漫画收录导入至本地书库（后台自动开启预缓存，支持收录后直达详情页）。**【仅馆长权限】**
- `discovery_open_detail({ source?, source_id })`：
  导航进入榜单中某本漫画的详情页。

#### (3) WebMCP 角色与权限分层模型（Curator vs Guest vs Direct Pass）

WebMCP 作为运行在浏览器宿主内的模型上下文通道，遵循**最小权限与按需暴露**原则：

| 操作分类                 | 涵盖工具                                                                                                                                                                                                                                                                                                        | 馆长（Curator） |     访客（Guest Pass）      |     单本直达（Direct Pass）     | 权限防线机制                                                                                                                                          |
| :----------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------: | :-------------------------: | :-----------------------------: | :---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **视口阅读与排版控制**   | `reader_jump_to_page`<br>`reader_turn_page`<br>`reader_switch_mode`<br>`reader_switch_fit`<br>`reader_toggle_auto_turn`<br>`reader_locate_bubble`<br>`reader_jump_chapter`                                                                                                                                      |     ✅ 允许     |           ✅ 允许           |             ✅ 允许             | 纯前端响应式状态与 DOM 视口调度，零后端写操作，所有在读读者均可自由由 Agent 遥控排版与翻页。                                                          |
| **书架淘书与检索查询**   | `shelf_search_comics`<br>`shelf_search_dialogue`<br>`shelf_search_image`<br>`shelf_pick_random`<br>`shelf_open_comic`<br>`shelf_read_comic`<br>`detail_start_reading`<br>`detail_open_chapter`<br>`detail_get_comic_info`<br>`discovery_get_ranking`<br>`discovery_switch_timeframe`<br>`discovery_open_detail` |     ✅ 允许     |  ✅ 允许（自动过滤隐藏本）  | ❌ 视口隔离（离开阅读器不暴露） | 只读查询；访客查询书架时后端自动应用 `hidden_from_guest` 隐私白名单过滤；单本直达用户离开该本子阅读视口后工具自动注销。                               |
| **偏好与红心标记**       | `reader_toggle_favorite`<br>`detail_toggle_favorite`                                                                                                                                                                                                                                                            |     ✅ 允许     |  ✅ 允许（本地/借阅账单）   |             ❌ 禁用             | 访客标记喜欢保存在客户端 IndexedDB 离线账本，不污染馆长云端元数据。                                                                                   |
| **藏书收录与元数据写入** | `shelf_import_comic`<br>`discovery_ingest_comic`<br>`detail_update_metadata`                                                                                                                                                                                                                                    |     ✅ 允许     | ❌ 零暴露（不注册进上下文） |   ❌ 零暴露（不注册进上下文）   | 前端 `canWrite` 哨兵在注册层直接掐断（`undefined` 不注册进 `document.modelContext`，Agent 零感知无 token 浪费），后端对直接 API 写入执行 403 强校验。 |
| **服务端全本预缓存触发** | `detail_cache_all_pages`<br>`detail_cache_chapter`                                                                                                                                                                                                                                                              |     ✅ 允许     | ❌ 零暴露（不注册进上下文） |   ❌ 零暴露（不注册进上下文）   | 防止访客消耗服务器大带宽与解密算力，前端注册层直接掐断，后端中间件执行 403 强阻断。                                                                   |

---

## 二、 外围智能生态与群聊机器人（Feishu / QQ Bot Integration）

### 1. 架构拓扑与多项目独立性

- **物理分仓独立演进**：飞书 / QQ 搜图 Bot 作为独立的微服务项目（如 `paper-feishu-bot`，基于 Node/Bun/TypeScript 或 Python），遵循 [ADR 0026](docs/adr/0026-central-data-hub-and-polyrepo-ecosystem.md) 多项目独立仓库规范，绝不侵入纸间核心读者端代码；
- **通道协议标准连接**：Bot 接收到群聊或私聊中的图片与指令后，通过标准 MCP 协议（`POST /api/mcp/rpc` 或 `/api/mcp/sse`）及 REST API 与纸间通信；
- **凭据隔离（Machine Token Auth）**：Bot 环境变量配置专用的 `MACHINE_TOKEN`（请求头 `Authorization: Bearer <MACHINE_TOKEN>`），享有机器级接口接入权，与馆长 Web 端登录凭据（`AUTH_SECRET`）严格隔离。

### 2. 机器人群私双轨权限分流（Group vs Private Chat Dual-Track Gating）

为坚守“纸间是馆长的私人漫画收藏室，只有馆长本人才能收录与全本离线”的不变量，Bot 实施群聊与私聊的严格双轨权限分流：

| 交互场景                     | 目标用户                       | 开放功能与工具                                                                                                                  | 权限防线机制                                                                                                                                                                  |
| :--------------------------- | :----------------------------- | :------------------------------------------------------------------------------------------------------------------------------ | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **群聊交互（Public Group）** | 所有群成员 / 陌生群友          | • 以图搜图（`search_by_image`）<br>• 台词全文搜书（`search_by_dialogue`）<br>• 签发单本沙箱免密阅读链接（`create_direct_pass`） | **绝对只读 + 沙箱限制**：群聊中彻底屏蔽入库与缓存指令。即使群友发送车号，Bot 亦静默忽略或报错拒绝；发出的链接严格锁死为单本沙箱，禁止看书架全貌。                             |
| **私聊交互（Private DM）**   | 仅限白名单内的**馆长本人账号** | • 群聊全部搜图与查出处功能<br>• 车号一键收录入库（`POST /api/library/import`）<br>• 触发全本离线预缓存与转码                    | **身份白名单强校验**：Bot 内部写死 `CURATOR_USER_IDS`（如馆长的 QQ 号或飞书 `open_id`）。仅当消息来源为白名单私聊时，才调用纸间后端的作品收录与后台预缓存接口，群友无法触发。 |

### 3. 单本沙箱（Single-Book Sandbox）与动态时效策略（Dynamic TTL Allocation）

当群友在群里找本子出处并命中时，Bot 调用 `create_direct_pass` 签发临时阅读凭证：

1. **阅读范围物理死锁**：
   - 链接格式：`https://comic.yourdomain.com/comic/{source}/{source_id}/read/{page}?temp_token=...`；
   - 访客在浏览器打开后，后端中间件将权限限制为 `direct:{source}:{source_id}`。仅放行该本漫画的详情、章节与画页请求；任何试图访问书架列表（`/api/library`）或其他漫画的请求直接被 `403 Forbidden` 击落；
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
  - **边界**：承载剧本大模型生成、分镜 Prompt 编排、ComfyUI 图像批量去噪、修脸修手、以及 **VTracer 矢量化分层压制**；生成完毕后通过 API 向纸间一键推送入库。

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
- **台词全文索引表（`comic_dialogues_fts`）**：纸间后端基于 SQLite FTS5 原生 `tokenize='trigram'` 构建倒排索引，0 依赖秒级模糊匹配中日文无空格文本；
- **气泡呼吸高亮（Breathing Bubble Overlay）**：读者从搜索下拉点击台词命中直达阅读器对应页码（`?page=42&bubble=1`），画卷视口在该气泡坐标浮现朱砂金色半透明高亮框呼吸 2 秒淡出，零 DOM 重排且不扰乱主阅读流。

### 6. 服务间认证凭据与推送 Webhook（Machine-to-Machine Auth）

外部 Paper Studio 完成整本编排后，携带专用 `Machine API Token` 调用 `POST /api/library/local/create` 推送画页与伴生资产；纸间后端完成校验后自动触发缩略图预热并广播 `library_changed` 事件，前台书架即时无缝呈现。

### 7. 数据质量保障与关键暗礁防御（Critical Safeguards & Edge Cases）

在将 OCR 与剧本语料引入生产环境时，必须筑牢五道质量防线：

1. **伴生文件被动感知与幽灵索引清理（Sidecar Ingestion Sync & Ghost Index Mitigation）**：
   - 外部 Studio 产出 `{index}.ocr.json` 后，通过 `POST /api/library/:source/:source_id/ocr/sync` 或 CLI `pnpm ocr:sync` 增量同步进 SQLite FTS5，避免每次重启全盘轮询卡死；
   - 漫画被删除或重新装订（Re-binding）时，联动事务原子清空该作品所有 FTS5 记录，彻底杜绝“搜得出台词但画页不存在或页码错位”的幽灵索引。
2. **简繁双向互通归一化（Simplified/Traditional Bidirectional Search）**：
   - 汉化组多为港台或民间繁体，读者常输入简体；在检索层对关键词进行双向展开匹配，确保无论输繁搜简还是输简搜繁均 100% 召回。
3. **气泡级多行文本几何聚类（Bubble-level Line Clustering）**：
   - 严禁把原始 OCR 吐出的碎片行直接存为独立气泡；外部管线必须按几何欧氏距离与排版流向聚类为完整对白句子，输出包围整个气泡的单个 `box`。
4. **主流引擎聚焦与开源语料冷启动（Engine Diversity Fallback & Open Corpus Cold Start）**：
   - Galgame 解包脚本聚焦成熟开放生态（KiriKiri / Ren'Py），杜绝从零发明通用解包器；优先引入开源社区已整理的中日双语平行语料库（JSONL）进行冷启动。
5. **图文双模联合检索（Multimodal Hybrid Search）**：
   - 搜索端点原生支持限定作品/作者下的台词搜索，识图结果页亦可带出命中页码的对白预览，形成图文双重校验。

---

## 四、 领域多模态模型微调与二次元专精翻译（Domain Multimodal Fine-Tuning & Anime Translation）

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
2. **云端租算力 SFT 微调**：利用 AutoDL 等算力平台，按小时租赁 RTX 4090，基于高质量开源底座（如 Qwen2.5-7B/14B、Gemma-2-9B）进行 LoRA 指令微调，专精二次元人称、口癖（如「〜のだ」「〜わ」「先輩」）、梗文化与本子特定语境；
3. **本地 Mac mini (Apple Silicon MLX) 高速推理**：训练完成的 LoRA 权重拉回本地，由 Mac mini 利用统一内存全天候低功耗常驻运行，为纸间未来收录的「日文生肉本子」提供本地 100% 离线、0 审查的即时汉化机翻。

### 3. 算力拓扑：训练与推理分离

- **训练在云端（低成本按需）**：租赁算力跑批量 LoRA 微调（仅需几元人民币），生成数百兆的轻量权重文件；
- **本地常驻推理**：Mac mini (Apple Silicon) 通过 MLX 或 llama.cpp 极低功耗常驻提供 HTTP/OpenAI 兼容推理端点。

---

## 五、 Mac mini（Apple Silicon）Homelab 私有云演进

### 1. 为什么是 Mac mini？

- **统一内存（Unified Memory）优势**：CPU 与 GPU 共享内存（如 32GB/64GB/128GB）。结合苹果 **MLX** 框架或 **llama.cpp**，可以在内存中高效加载运行 14B~32B 参数的开源大模型，完全打破传统显卡显存瓶颈；
- **全天候静音与低功耗**：整机待机仅数瓦，满负荷 30~50 瓦，无刺耳风扇噪音，适合作为 24 小时开机的家庭书房核心；
- **一体化架构**：单台设备同时跑 Docker（FastAPI 后端 + Vue 前端 + imsearch 搜图）与本地大模型推理端点。

### 2. 外接大容量硬盘柜（DAS）冷热分层存储拓扑

Mac mini 内置 SSD 加装成本高昂（通常为 512GB/1TB），面对海量漫画库与多模态模型文件需建立物理分层：

- **外接雷电 4 / USB-C 多盘位硬盘柜（DAS / RAID 阵列）**：格式化为 APFS 挂载至 `/Volumes/ComicStorage/data`，专供 `library/` 原图海量仓库、离线画页与训练冷数据，彻底解放内置容量；
- **内置极速 SSD**：专供 macOS 系统、Docker 运行时、SQLite 数据库、以图搜图向量索引与 MLX 大模型热权重。

### 3. 端侧 100% 离线隐私 VLM（Apple Silicon MLX）

利用 Mac mini 的统一内存，在本地常驻运行开源视觉多模态大模型（如 `Qwen2.5-VL-7B/14B`）：

- **全天候自动打标**：对入库本子自动执行打标（Captioning）与剧情分镜理解，0 API 调用成本；
- **100% 隐私闭环**：私密漫画资产全生命周期不流出家庭局域网，彻底免除第三方云端 API 审查与封号风险。

---

## 六、 长远 2D 互动游戏 / 视觉小说演化（Interactive Narrative & AVG）

### 1. 技术路线抉择：为什么坚持 2D 路线？

- **3D WebGL / Blender MCP 的局限**：漫画本质是高度风格化的手绘 2D 艺术。当前 Image-to-3D 模型生成的 3D 资产拓扑杂乱、骨骼动作绑定困难，极易造成画风严重失真，投入产出比极低；
- **2D 互动视觉小说（AVG）的优势**：完美契合漫画资产特性，100% 保留原作细腻作画。

### 2. 演化管线：漫画分镜与 Galgame 剧本深度融合

1. **分镜切片与台词抽取**：利用轻量模型分割漫画分镜格子（Panel），OCR 抽取气泡对白生成 `{index}.ocr.json` 与 `{index}.panels.json`；
2. **多源剧本融合编译（Comic Panels + Galgame Scripts）**：
   - 将漫画的高清视觉分镜作为立绘/CG 演出舞台；
   - 将 `backend/data/corpus/galgame/` 提取的典型选择支、好感度分支与心理描写作为模板；
   - 由 LLM（通过本地 Mac mini MLX 或云端）解析剧情主线，自动生成玩家可参与的二选一/三选一抉择点，编译为紧凑的 AVG 决策状态机；
3. **Web 端轻量引擎**：利用 Web Canvas / Pixi.js 在纸间展馆中编译为零依赖、可在现代浏览器即点即玩的沉浸式 2D 互动分支视觉小说。

---

## 📌 下一步落地实施路径建议

在哔咔 (PicAcg) 数据源已顺利落地的前提下，AI 生态落地推荐的阶梯路径：

1. **第一步（通道就绪）**：优先实施 **“纸间 MCP 服务端”** 与 **“定向临时直达票据”**，打通外部 Agent 与飞书搜图 Bot；
2. **第二步（即时价值与索引双翼）**：在纸间主干落地 **“漫画台词全文检索（SQLite FTS5 + Trigram）”**，确立 `{index}.ocr.json` 伴生契约与气泡呼吸高亮，瞬间解决“记得台词找不到本子”的痛点，并打通图文双模检索；
3. **第三步（平行语料汇流与翻译专精）**：在外部 Studio 启动 **Galgame 中日双语脚本解包与清洗**，在 `backend/data/corpus/galgame/` 沉淀黄金平行语料，微调二次元翻译模型并在 Mac mini 本地常驻，赋能生肉本子即时阅读；
4. **第四步（游戏化与创作工坊）**：待图文与对白资产充实后，推进 2D 互动 AVG 游戏引擎演进与 AI 漫画工坊装订入馆。
