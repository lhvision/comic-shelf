# ADR 0013 — 哔咔漫画 (PicAcg) 数据源接入与架构定力决策

- **日期**：2026-09-07
- **状态**：Accepted
- **关联**：承接 ADR 0006 (双轨存储与轻量 SQLite 状态隔离)，扩展 `CONTEXT.md` 来源（Source / Provider）与哔咔漫画规范

## 背景

随着纸间（Paper Room）核心功能（书架流、多章节阅读器、以图搜图、双口令门禁与离线 PWA）全面成熟，系统计划扩展第三个核心数据源——**哔咔漫画（PicAcg）**。在方案论证过程中，团队梳理了底层架构与接入路径的关键抉择：

1. **架构重构诱惑**：探讨是否需要引入 PostgreSQL 替代现有文件/SQLite 存储，或推倒当前技术栈改用 Nuxt SSR + Hono.js 全栈 TypeScript；
2. **哔咔接口特性与误区**：用户最初认知为“无公开 API，需要网页端无头浏览器登录抓取”，但哔咔网页端常年受高防 CDN 拦截、域名漂移频繁且渲染高消耗；而其移动端官方 App 实际上全量运行于成熟的 HMAC-SHA256 签名 REST 协议之上；
3. **架构纪律与未来边界解耦**：团队一致认同应避免将长远的“MCP 服务端、AI 本子生成、2D 互动游戏化”等未来愿景过早杂糅进当前实施阶段的 ADR，保持架构记录的原子性（Atomics）与现实聚焦。

## 决策

### 1. 坚守核心技术栈定力（拒绝过度工程与重写陷阱）

- **否决 PostgreSQL 全量重构**：纸间核心资产坚守“本地优先（Local-First）与目录自包含”。图卷与静态元数据继续由 `album.json` + `pages/` 承载，可自由拷贝、便携迁移、永无数据库损坏即全站丢失的隐患；用户行为与访客状态由内置 Python `sqlite3` (WAL 模式) 承载，引入外部关系数据库只会徒增 NAS/Docker 运维负担与网络往返延迟。
- **否决 Nuxt SSR 重构**：纸间是私人鉴权阅览室，全站实施严格的 `Zero-DOM Gate`（未登录时甚至不渲染书库 DOM，彻底反爬与防窥探）。Nuxt 的核心收益在公开 SEO 与服务端渲染，引入只会制造客户端 PWA 水合不一致并增加 Node 运行时开销。
- **坚守 Python FastAPI 后端底座**：Python 是图像解码（Pillow）、反爬逆向（curl_cffi / HMAC 签名）及未来计算机视觉生态的坚实底座。FastAPI 异步高并发足以胜任家庭与朋友私有部署。

### 2. 哔咔数据源接入技术规范 (`PicacgProvider`)

- **权威参考实现收敛（Canonical Reference Source）**：
  - 团队将开源项目 `wgh136/PicaComic`（[https://github.com/wgh136/PicaComic](https://github.com/wgh136/PicaComic)）确立为纸间对接哔咔漫画逆向协议、端点契约与 HMAC 签名的**唯一事实源（Single Source of Truth）**；
  - 后续任何接口调用、分页排错与分流变动一律对照该项目，严禁在外部搜索引擎盲目搜索未经验证的散落代码或误搜 "piacg"。
- **移动端 App 逆向 REST API 与 Query 签名全量约束**：
  - 在 `backend/app/providers/picacg.py` 实现 `PicacgProvider`（继承 `ComicProvider`），内置 HMAC-SHA256 签名算法与 Header 构造（`api-key`, `signature`, `app-channel`），直接对接官方稳定后端；
  - **Query 签名必选红线**：官方服务端在校验签名时，要求相对 URI 路径**必须完整保留 Query 字符串**（如 `comics/{id}/eps?page=1` 与 `comics/{id}/order/{order}/pages?page=1`）。若剥离 Query，服务端将静默返回不含 `data` 的空 200 假成功报文；计算签名与发起请求时必须全量包含 Query。
- **双模封面与官方 Thumb 融合（Dual-Source Cover Fusion）**：
  - **Cover 1（正房门面）**：预缓存阶段优先通过 Provider 下载哔咔官方 `thumb`（`{fileServer}/static/{path}`），并高质量转码为 720px 与 360px 的 WebP 封面；
  - **Cover 2~4（内页展开）**：依序由正文画卷第 1、2、3 页生成，保持书架卡片 3D 悬浮 4 叠牌展开的生动层次感；
  - **安全降级**：若官方 thumb 发生 CDN 异常，自动平滑降级回落至画页第 1 页生成封面，确保书架零破图。
- **宽容输入与车号规约（Lenient ID Parsing）**：
  - 哔咔原生作品编号为 24 位十六进制 ObjectId（如 `5822a61e0e84b80695d10a26`）；
  - 系统同时支持用户输入纯 24 位 ID、带 `PICA:` 前缀，或直接粘贴哔咔官方/镜像网页端分享 URL，由 `normalize_id()` 自动正则提取规范车号。
- **多 CDN 分流自动轮换降级（Multi-CDN Failover）**：
  - 哔咔画页资源分布在多个分流域名（如 `storage1.bwaa.co`、`storage2`、`storage3`）；
  - 在 `download_page` 执行阶段，若遇到超时或 502/503 异常，自动在可用分流节点间无缝轮换重试，保障离线缓存成功率。
- **集中凭据与会话保活（Curator Session Management）**：
  - 馆长在环境变量或系统配置中统一配置哔咔账号密码；
  - 后端启动或首次收录时自动登录并换取 JWT，会话持久化于 `backend/data/picacg_session.json`，支持自动刷新与保活。
- **坏档自愈与字段人性化规约（Self-Healing & Metric Formatting）**：
  - **上架日期**：`published_at` 严格映射为 `created_at`，格式化为标准 `YYYY-MM-DD`；
  - **统计指标**：`views` 与 `likes` 采用标准公制缩写（如 `3.4M`、`78k`）；
  - **坏档自愈**：在 `/api/library/import` 导入阶段，若本地已有缓存但 `page_count == 0`，自动判定为受损坏档，穿透缓存触发回源重拉与预缓存。

### 3. 多章节模型无缝对齐

- 哔咔的多卷/多话结构（Episodes）平滑映射至纸间 `ComicMeta.chapters`；
- 全书画页拍平为单调递增的全局页号（`1..page_count`），每页携带 `chapter` 标识，完全复用详情页目录展开、章节子路由与阅读器 HUD。

### 4. 未来扩展正交解耦

- 关于外部 TS Agent、飞书 Bot、纸间 MCP 服务端及长远 AI 创作演进，均作为外部消费端或独立阶段演进，待实施时单独建立对应 ADR，不在本决策中提前越权锁定。

## 影响与收益

1. **架构纯粹零负担**：无需迁移已有书库和数据库，零新增外部服务依赖；
2. **收录吞吐提升 10 倍**：相比无头浏览器模拟抓取，基于 REST API 的元数据获取与多线程分流下载性能提升一个数量级，内存占用降低 90%；
3. **输入体验丝滑**：支持直接粘贴网页链接或车号，多章节连载漫画无缝融入现有阅读器；
4. **决策资产边界清晰**：ADR 严格聚焦当下确定性实现，杜绝臆测性架构堆砌。
