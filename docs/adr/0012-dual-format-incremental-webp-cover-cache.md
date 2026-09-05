# ADR 0012 — 基于 HTTP 内容协商的双模增量 WebP 封面缓存与秒级转码架构

- **日期**：2026-09-05
- **状态**：Accepted
- **关联**：升级基础设施与书架性能链路，对接 `CONTEXT.md` 封面与书架呈现规范，补充 Chrome DevTools 性能调优

## 背景

1. **首屏封面传输冗余**：Chrome DevTools 性能洞察（ImageDelivery Insight）对纸间书架首屏性能 Trace 的深度分析显示，首屏 8 张 360px 宽度卡片封面（JPEG 格式）存在约 **136.9 kB（约 35%~50%）** 的网络传输冗余。在弱网或远程穿透（Cloudflare Tunnel / 家庭宽带上行受限）环境下，直接拖慢书架卡片秒开与 LCP。
2. **多源与自定义封面特点**：纸间支持读者在阅读器或详情页自由挑选任意精彩页设为封面（`cover_indices`），同时也支持章节独立封面。封面本质上是从超大尺寸原始内页（通常 1500~2000px）抽样生成的**衍生缩略图（Derived Thumbnails）**，天然需要重新缩放与持久化。
3. **存量书库平滑过渡与低算力兼容**：书库本地磁盘已有大量旧版 `001_360.jpg`。在 ARM / 树莓派 / 低配 NAS 等 Homelab 运行环境下，严禁执行高 CPU 占用的全量离线转码，也严禁因格式变更导致旧离线 PWA 客户端或第三方脚本产生 404。

## 决策

1. **基于 HTTP `Accept` 请求头的透明内容协商（Transparent Content Negotiation）**：
   - 前端无需修改既有封面请求路径（仍请求 `/api/library/.../covers/{index}/file` 或带 `.jpg` 后缀）；
   - 后端服务嗅探客户端请求头中的 `Accept` 字段：
     - 若客户端声明支持 `image/webp`（现代浏览器 100% 原生标配），则优先寻找并生成 `.webp` 文件，返回 `media_type="image/webp"` 并注入 `Vary: Accept` 响应头指导浏览器与中间代理缓存；
     - 若客户端未声明支持或请求显式要求其他格式，则安全回落至原有 `.jpg`；
   - 彻底避免前端路由、PWA 缓存正则及以图搜图识别规则的破坏性重构。

2. **增量惰性生成（On-Demand Incremental Generation & 100% 物理落盘）**：
   - 绝不执行离线全量粗暴刷库；
   - 当收到支持 WebP 的封面请求且磁盘尚未命中 `001_360.webp` 时，后端在单次请求中就地（JIT）完成物理生成并写入磁盘（`001_360.webp`）；
   - 后续所有访问均直接命中现成物理文件，通过 `FileResponse` 毫秒级直出，运行时零二次 CPU 负担。

3. **双轨极速转码路径（Fast-path Downscaling）**：
   - **极速路径（Fast Path，2~5ms）**：若磁盘上已有旧版同规格缩略图（如 `001_360.jpg`），直接通过 Pillow 进行内存格式转存为 `001_360.webp`，跳过耗时的 Lanczos 重采样，极低算力消耗瞬时完成；
   - **基准缩放路径（Scale Path）**：若无 `_360.jpg`，则从 720px 基准封面或第一页原图执行单次重采样缩放并持久化。

4. **由双模并存演进至显式 WebP URL 收敛（Explicit WebP URL Convergence & Edge CDN Cache Key）**：
   - **Cloudflare 边缘缓存痛点**：Cloudflare 等主流 CDN 免费层默认忽略 `Vary: Accept` 标头进行缓存分片。若请求 URL 为 `file.jpg`，首次回源若为 JPEG 则 Anycast 边缘节点将永久向所有客户端缓存并下发 JPEG，导致透明内容协商在边缘层失效。
   - **URL 后缀显式收敛**：衍生缩略图（封面、章节封面、页面缩略图）在客户端 URL 层面全面显式收敛为 `.webp`（如 `/covers/{idx}/file.webp`、`/chapters/{id}/cover.webp`、`/pages/{idx}/thumbnail.webp`），为 CDN 边缘提供确定性唯一的缓存键。
   - **物理冗余清理（Zero Waste）**：存量历史 `.jpg` 缩略图在被 fast-path 转为 `.webp` 后立即自动 `unlink` 删除，避免双份文件浪费 NAS 存储；
   - **正文漫画页 100% 原始格式保真（Raw Source Page Fidelity）**：正文内页端点收敛为无后缀格式无关路径 `/pages/{idx}/file`，绝对不进行二次转码（JM 保持 WebP，哔咔等未来源保持 JPEG，本地扫描保持 PNG），兼得极致画质与衍生图轻量化。

5. **全尺寸覆盖（360px 缩略图 + 720px 基准封面）**：
   - `w=360` 缩略图：用于书架卡片网格、章节封面列表、以图搜图微缩芯片，彻底解决首屏卡片网络瀑布流瓶颈；
   - `w=None`（720px 基准封面）：用于详情页顶层 Hero 卡片与高清视网膜屏放大展示，两档尺寸享有完全对称的 WebP 缓存与更新策略。

6. **全生命周期封面与缩略图 WebP 预热（Comprehensive Lifecycle WebP Pre-warming）**：
   - 不仅在馆长更新 `cover_indices`（设为封面）时，在作品导入（`import_comic`）、全本重新装订（`rebind_archive`）、后台整本预热（`prefetch_comic`）以及单章节预热（`prefetch_chapter`）等全链路数据写入节点，后端均仅专注预热生成对应画页的 `360px` 与 `720px` 的 WebP 缩略图与封面，彻底移除过时的 JPEG 重复写入；
   - 首屏 100% 毫秒级命中磁盘与 CDN 静态缓存，减少 50% 的导入磁盘 I/O。

7. **HTTP 状态码严格语义收敛（Strict Error Semantics）**：
   - 封面与章节封面端点严格区分“资源不存在”与“服务端故障”：
     - 若底层画页文件缺失、章节未离线或画卷未导入（触发 `FileNotFoundError` 或 `KeyError`），必须精准响应 `404 Not Found`；
     - 严禁误抛 `502 Bad Gateway`，避免触发 Cloudflare 边缘错误页接管或 APM 上游故障报警；仅在解码崩溃等非预期错误时抛出 500/502。

## 影响与收益

- **带宽与流量瘦身**：首屏封面体积立减约 35%~50%（首屏 8 张封面从 ~380KB 降至 ~190KB），移动端和远程内网穿透体验显著提速。
- **解码与内存优化**：现代移动端（iOS Safari / Android Chrome）对 WebP 解码具备原生硬件级优化，降低首屏卡片渲染与滚动时的内存占用。
- **敏捷验证**：针对封面格式与协商逻辑，完全采用轻量快速的 Python 后端单测（`pnpm test:py`，秒级完成），免除耗时长且易波动的 DevTools MCP Trace 录制。
