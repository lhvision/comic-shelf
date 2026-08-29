# ADR 0005 — 渐进式 PWA 离线架构与客户端存储管理隔离机制

- **日期**：2026-08-29
- **状态**：Accepted

## 背景

纸间定位于「本地优先的个人漫画收藏夹」，读者常在手机、平板及桌面电脑上翻阅漫画。

在此场景下存在两项核心诉求与边界冲突：

1. **端侧离线运行与独立窗口（PWA）**：读者期望在通勤弱网或断网环境下能够无缝启动应用、阅读已缓存的页面，并支持直接「添加至桌面/主屏幕」作为独立应用运行。
2. **高频阅览引发的端侧存储膨胀与误删恐惧**：漫画图片文件体量大，阅览几十本本子后浏览器 CacheStorage 会占用数百 MB 乃至数 GB 的设备存储空间；用户需要获知真实空间占用并可主动清理。但系统存在一条不可逾越的红线——**服务端的漫画书库数据（`backend/data/library/`）严禁被删除**。若不从架构与概念上做出严格区隔，用户极易误以为「清理缓存」会毁掉服务器珍藏。

## 决策

1. **双层存储严格隔离与客户端自主权**：
   - 明确建立**「客户端离线缓存（Client Offline Cache）」**与**「服务端书库数据（Library Data）」**的正交概念边界；
   - 查看与清理功能 100% 作用于浏览器端侧（`StorageManager` / `CacheStorage` / `ServiceWorker`），零服务端破坏性 API 调用，用户可随时安全清空图片缓存，绝不触碰服务器数据。

2. **分级离线缓存与 PWA 规范全量达标（Tiered Offline Caching via Workbox）**：
   - 遵循 Vite PWA 官方规范与 Web App Manifest 最低要求：
     - 入口点补齐 `<meta name="description">`，替换 Apple Touch Icon 为标准的 PNG 格式与 Favicon 兼容降级；
     - Web App Manifest 完整配置 `start_url`、`scope`、`display: standalone`，以及满足 Android / iOS 规范的 `any` 与 `maskable` 双分辨率图标；
     - 引入 `workbox-window` 与 `virtual:pwa-register`，实现生命周期托管与每小时周期性更新探测（`onRegisteredSW` + 弱网安全容错）；
     - 服务端 `SPAStaticFiles` 注册 `application/manifest+json` MIME 类型，并对关键入口（`/`、`index.html`、`sw.js`、`manifest.webmanifest`）强制下发 `Cache-Control: no-cache, no-store, must-revalidate`，避免客户端被陈旧脚本死锁；
     - **App Shell 核心资产（HTML/JS/CSS/WebP/字体）**：采用 Precache 结合 Stale-While-Revalidate，实现断网毫秒级启动与静默后台更新；
     - **API 动态元数据**：采用 Network-First，避免书库增删、收藏、鉴权状态出现陈旧脏数据；
     - **漫画原图与缩略图（`/pages/.../file`、`/thumbnail`、`/covers/...`）**：采用 Cache-First（配合后端已下发的 `immutable` 响应头），并配置 `maxEntries: 1000, maxAgeSeconds: 30天` 的 LRU 自动淘汰规则，形成防止手机写满的第一道安全阀。

3. **双粒度测量与安全清理交互**：
   - 基于 `navigator.storage.estimate()` 毫秒级测量当前 Origin 的真实物理占用；
   - 细分展示「纸间核心资产」与「漫画阅览缓存（已读张数与体积）」；
   - 清理操作提供两档选择：
     - **日常级**：「清理阅览图片缓存」——只清空图片 Cache 桶，保留 App Shell 核心外壳，应用断网依然可启动；
     - **重置级**：「重置全部离线环境」——引入两步确认交互防线（5秒超时自动回滚），防止误触注销 Service Worker。

4. **私人阅览室美学落地与浮层体系闭环**：
   - 采用 `<StoragePopover />` 挂载于 `AppHeader.vue` 顶栏，基于 `AppPopover` 展开；
   - 标尺采用 3px 平直纸印规范与朱砂强调色；
   - 移动端小屏自适应收拢为 44px 舒适触控印章；
   - 全面剔除常驻红点等干扰性通知，保持阅览室静谧典雅。

## 后果

- **正面收益**：
  - 纸间正式具备完整的 PWA 独立安装与离线断网阅览能力；
  - 用户可随时直观掌控本设备存储消耗，并能安全释放空间；
  - 彻底消除了用户误删服务器 NAS 漫画的顾虑。
- **注意事项**：
  - iOS WebKit 目前对 PWA 的 `beforeinstallprompt` 事件不提供原生 API 支持，需通过 Safari 原生「分享 → 添加到主屏幕」进行安装；
  - 新版本上线后，Workbox 会在下一次页面空闲时静默完成 SW 激活。
