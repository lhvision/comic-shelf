# 架构与不变量（详细规则）

> 给后续 AI / 维护者：先读这份文件，再改代码。品牌名「纸间 Paper Room」。目标是“本地优先的个人漫画收藏夹”，
> 不是泛化爬虫，也不是公开站点。

## 1. 项目现状

- 已实现：书架、导入禁漫车、多章节目录与子路由、详情页、封面流、阅读器（三种模式 + 分屏 + 自动翻页）、以图搜图（ORB 特征）、访问门禁与防盗链、本地持久化缓存。
- 代码迁移时未复制 `backend/data/`；首次收录后会自动生成本地缓存。
- 服务启动后：
  - API: http://127.0.0.1:8000 （FastAPI docs 在 `/docs`）
  - Web: http://127.0.0.1:5173 （Vite，`/api` 代理到 8000）

## 2. 技术栈

| 层       | 技术                                                                          |
| -------- | ----------------------------------------------------------------------------- |
| 前端     | Vite 8 + Vue 3 + TypeScript + Vue Router + Pinia + VueUse + VitePWA (Workbox) |
| 样式     | 原生 CSS：`@layer`、Nesting、`color-mix()`、`oklch()`、`calc()`、`clamp()`    |
| 后端     | Python 3.12+ / 3.14 + FastAPI + uvicorn                                       |
| 禁漫源   | `jmcomic==2.7.4`（metadata 用 HTML client，图片算法用 `JmImageTool`）         |
| 图片处理 | Pillow（封面缩略图、解密）                                                    |
| 识图引擎 | `imsearch`（Docker Sidecar / 本地独立进程，ORB 特征 + 倒排索引）              |

约定：**不用 SCSS**。新增视觉请走 `src/styles/tokens.css` 的设计 token。
设计基线见 `DESIGN_NOTES.md`：私人阅览室 / 卡片目录，禁紫色渐变，禁玻璃拟态堆叠。

## 3. 架构

```text
Browser (Vue 3 + PWA Workbox)
   │  /api/* (NetworkFirst)
   ▼
FastAPI (backend/app/main.py)
   │
   ├── providers/           # 站点适配层，唯一知道具体漫画站的地方
   │     base.py            # ComicProvider 抽象
   │     jm.py              # 禁漫实现
   │     registry.py        # 注册表
   │
   ├── gate.py              # 下载并发闸门控制
   ├── jobs.py              # 后台批量缓存任务管理
   ├── events.py            # 单向系统事件流（SSE，广播版本更新/书库变动/AI进度）
   ├── imsearch.py          # 局部特征搜图客户端（HTTP 隔离通信）
   └── storage.py           # 本地缓存与文件布局
         │
         ▼
backend/data/library/<source>/<source_id>/
   ├── album.json           # 通用元数据 + favorite + pages[].cached + chapters[]
   ├── remote.json          # 图片 URL + scramble_id + decode_version
   ├── pages/00001.webp     # 单章节（扁平）已解密成品页
   ├── pages/<chapter>/00001.webp   # 多章节：页面按章节 id 分目录
   ├── covers/001.jpg       # 由首页前 N 页（第一章）生成的封面
   └── thumbs/…            # 360px 缩略图；多章节同样按章节分目录
```

> 多章节模型：`ComicMeta.pages` 始终是**全书拍平的全局页码表**，每页带
> `chapter` 字段（空串 = 单章节扁平布局）；`ComicMeta.chapters[]` 记录各章节
> id / 序数 / 标题 / 页数 / 起始全局页（`start`）。这样阅读器页码、继续阅读、
> 封面、API 路径都不用为章节拆分端点。

### 客户端离线缓存与服务端数据边界（正交隔离）

- **端侧 CacheStorage（PWA 离线运行）**：
  - `workbox-precache`：HTML/JS/CSS/WebP 应用外壳预缓存；
  - `manga-images-cache`：漫画原图与缩略图 Cache-First（LRU 限制 1000 篇目 / 30 天）；
  - `api-metadata-cache`：动态 API Network-First；
  - **安全红线**：所有针对缓存的查看与清理（`useOfflineStorage`）**100% 局限于端侧浏览器**，零破坏性服务端 API，绝不触碰服务端持久化目录 `backend/data/`。
- **服务端 SPAStaticFiles 部署中间件**：
  - 对 `/`、`/index.html`、`/sw.js`、`/registerSW.js`、`/manifest.webmanifest` 强制下发 `Cache-Control: no-cache, no-store, must-revalidate`；
  - 显式注册 `application/manifest+json` 对应 `.webmanifest`。

### Provider 扩展点

新增漫画站只做三件事：

1. `backend/app/providers/<site>.py` 继承 `ComicProvider`；
2. 实现：
   - `normalize_id(raw) -> str`
   - `fetch(raw_id) -> FetchedComic`（只拿元数据和页面 URL，不下载图片）
   - `download_page(fetched, remote_page) -> bytes`（返回**成品字节**）
3. 在 `registry.py` 注册。

前端不用改渲染逻辑。

## 4. 关键不变量（改代码前必读）

### 4.1 本地优先

- `POST /api/library/import` 先查 `album.json`；命中则 `from_cache=true`，**不请求远端**。
- 只有显式 `refresh=true` 才更新元数据。
- 图片按需懒下载；`POST .../cache` 才批量缓存。

### 4.2 JM 图片必须解密

JM 原始图是打乱的，**绝不能直接保存下载字节**。

正确路径：

```python
from jmcomic import JmImageTool

num = JmImageTool.get_num_by_url(page.scramble_id, page.url)
JmImageTool.decode_and_save(num, source_image, save_path)
```

现在 `JMProvider.download_page()` 会：
下载 raw bytes → `get_num_by_url()` → `decode_and_save()` → 返回成品 bytes。
`remote.json` 中 `decode_version=2` 表示页面已是成品图。

### 4.3 decode_version 迁移

- `decode_version=1`：旧缓存，页面是未解密 raw 图。
- 读取书架时会自动本地迁移：用已有 raw 文件解密替换，**不重新下载**，
  然后删除旧封面，让封面从成品图重建。
- 不要随便把 `CURRENT_DECODE_VERSION` 改成 2 以上；只有图片管线变更时才加迁移逻辑。

### 4.4 多章节不变量

- **全局页码拍平**：`ComicMeta.pages` 按全书拍平（1..`page_count`），每页带 `chapter`。
  阅读器页码、继续阅读、封面、API 路径都建立在全局页号上，**不要**为章节拆分新的
  page/thumbnail/cover 端点。
- **单章节零迁移**：`PageRecord.chapter` 与 `ComicMeta.chapters` 带默认值；旧 `album.json`
  没有这些字段时按空串/空表处理，存储仍走扁平 `pages/`。多章节才写子目录
  `pages/<chapter>/<file>`。
- **旧多章缓存本地回填（不重新下载）**：曾在某个窗口导入的多章缓存，页面带 `chapter`
  但没有 `ComicMeta.chapters`（只落在 `raw.chapters`）。读取时用 `raw.chapters` 本地重建
  `chapters`（压平标题空白）并原位修复 `album.json`，和 v1→v2 迁移同一哲学——不碰远端。
- **Provider 边界**：章节概念只存在于 provider 的 `fetch()`（读 `album.episode_list`）；
  storage / API 只认 `Chapter{id,index,title,page_count,start}`，不感知禁漫具体字段。
- **封面归属**：封面永远取全局前 `cover_count` 页（即第一章），不按章节生成。

## 5. 后端文件地图

| 文件                                | 职责                                                                                                   |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `backend/app/main.py`               | FastAPI 路由与安全中间件、GZip 传输层压缩、SPA 静态文件回落挂载                                        |
| `backend/app/auth.py`               | 鉴权校验、Cookie 会话管理、Sec-Fetch-Site 与 Referer 防盗链校验                                        |
| `backend/app/gate.py`               | 运行时下载并发控制闸门（支持环境变量锁定与设置持久化）                                                 |
| `backend/app/jobs.py`               | 后台异步缓存任务执行器与进度追踪                                                                       |
| `backend/app/models.py`             | 通用模型：`ComicMeta`（含 `Chapter`/`chapters`）/ `PageRecord.chapter` / `RemotePage` / `FetchedComic` |
| `backend/app/storage.py`            | 原子 JSON 写入、页面缓存（章节分目录路由）、封面生成、v1→v2 迁移、书库扫描                             |
| `backend/app/providers/base.py`     | Provider 接口                                                                                          |
| `backend/app/providers/jm.py`       | JM HTML 元数据、上传者解析、**多章节 episode 逐话拉取**、图片下载 + 解密                               |
| `backend/app/providers/registry.py` | `{"jm": JMProvider()}` 注册表                                                                          |
| `backend/app/imsearch.py`           | 局部特征识图客户端（ORB 特征匹配、健康探测、路径解析）                                                 |
| `backend/app/config.py`             | 数据目录、访问密钥、防盗链开关、封面尺寸、识图服务地址配置                                             |

- `GET /api/auth/status`（查询是否开启鉴权及当前登录态）
- `POST /api/auth/login`（验证口令并写入 Cookie）
- `POST /api/auth/logout`（清除登录凭据）
- `GET /api/settings` / `PUT /api/settings`（获取与修改运行时配置，如并发数）
- `GET /api/discovery/ranking`（发现页与排行榜数据：周榜/月榜/日榜/总榜，支持 `time_type` 与分类筛选）
- `GET /api/library`（`q` 也能命中章节标题）
- `POST /api/library/import` `{id, source, prefetch_covers, prefetch_all, refresh}`（`refresh=true` 走增量，章节未变则复用旧 remote）
- `POST /api/library/local/create`（自建工坊创建本地图集/多章节元数据骨架）
- `POST /api/library/local/import-path`（扫描服务器本地目录如 `public/tiya-frames` 秒级收录）
- `POST /api/library/local/{source_id}/upload-pages`（向本地图集分批上传图片）
- `POST /api/library/local/{source_id}/append`（增量追加页面或新章节，单章节追加新话时自动升阶）
- `PATCH /api/library/{source}/{id}/metadata`（更新标题/作者/标签/叙述/自定义封面页码 `cover_indices`）
- `PATCH /api/library/{source}/{id}/chapters/{chapterId}`（修改单章节名称）
- `DELETE /api/library/{source}/{id}/chapters/{chapterId}`（物理删除单个章节并重排全书全局页码）
- `GET /api/library/{source}/{id}`（详情含 `chapters`）
- `GET /api/library/{source}/{id}/pages/{n}/file`（`n` 为全局页号，带防盗链校验，支持 `.{ext}` 静态扩展名别名）
- `GET /api/library/{source}/{id}/pages/{n}/thumbnail`（同上，支持 `.{ext}` 别名）
- `GET /api/library/{source}/{id}/covers/{n}/file`（封面取 `cover_indices` 或前 N 页，带防盗链校验，支持 `.{ext}` 别名）
- `GET /api/library/{source}/{id}/chapters/{chapterId}/cover`（章节封面端点，带防盗链校验，支持 `.{ext}` 别名）
- `GET /api/search/image/status`（以图搜图 Sidecar 服务健康探测）
- `GET /api/curator/passes`（馆长获取访客名册列表）
- `POST /api/curator/passes` `{username, expires_days, custom_token}`（馆长登记印发专属通行证）
- `PATCH /api/curator/passes/{id}` `{username, is_active, extend_days, reset_token}`（通行证续期、密钥换新、启停）
- `DELETE /api/curator/passes/{id}`（注销指定通行证）
- `GET /api/library/{source}/{id}/progress`（获取当前用户阅读进度）
- `PUT /api/library/{source}/{id}/progress` `{last_page}`（保存当前用户阅读进度，防抖上报）
- `PATCH /api/library/{source}/{id}/favorite` `{favorite: bool}`（独立用户收藏切换）
- `GET /api/providers`
- `POST /api/library/{source}/{id}/cache`
- `GET /api/library/{source}/{id}/chapters/{chapterId}/cache`（查询单章节离线缓存进度，受 `_require_meta` 隐私保护）
- `POST /api/library/{source}/{id}/chapters/{chapterId}/cache`（触发单章节后台异步离线下载任务）
- `DELETE /api/library/{source}/{id}`

页面 / 封面响应带 `Cache-Control: public, max-age=2592000, immutable`（30 天浏览器长效强缓存），配合 `_meta_cache` 内存二级缓存与 Fast-Path 直通，实现多章节和二次浏览秒开。

## 6. 以图搜图（imsearch）架构与工作流

- **定位与算法**：基于 OpenCV ORB 局部特征点 + Faiss 倒排索引（`lolishinshi/imsearch`），针对二次元局部截图、表情包、台词框具备极强抗裁剪匹配能力。
- **开源许可证隔离（Sidecar 模式）**：`imsearch` 为 GPL-3.0 许可证，纸间核心为 MIT 许可证。纸间采用 Docker Sidecar（`:8765` 端口）独立运行 + HTTP API 转发 `backend/app/imsearch.py`，源码零依赖、零编译链接。
- **存储结构**：数据持久化于 `backend/data/imsearch/`：
  - `imsearch.db`：SQLite 数据库，记录图片文件映射、特征向量统计与哈希；
  - `centroids.bin`：512 个 K-Means 视觉词典聚类中心；
  - `invlists.bin`：倒排索引文件，支撑毫秒级向量相似度匹配。
- **索引触发与增量构建机制**：
  - **收录新漫画时**：不实时同步重构索引（避免频繁触发 CPU 密集的特征提取与聚类重训）；
  - **日常增量追加（默认行为，秒级完成）**：运行 `pnpm reindex:image`（执行 `scripts/reindex.sh`）。脚本检测到已存在 `centroids.bin` 时，**仅执行 `add`（提取新图特征）+ `build`（追加未索引特征至倒排索引）**，旧特征与聚类模型 100% 保留，零重复计算；
  - **全量重置重训**：仅在显式传入 `--full` 参数（`bash scripts/reindex.sh --full`）或首次初始化时，重新运行 K-Means 训练聚类中心并重构全量倒排索引。

## 7. 存储架构与规模演进分析（千万级性能评估）

### 7.1 当前存储机制（本地优先 + 零依赖）

- **核心书库**：采用 **文件系统分片 + 原子 JSON（`album.json` / `remote.json`）+ 内存二级缓存（`_meta_cache`）**，保持本地优先与自包含，脱离数据库亦可独立迁移与阅读。
- **状态与通行证**：采用 **轻量 SQLite WAL（`comic_shelf.db`）**，管理动态访客通行证（`guest_passes`）、按用户红心收藏（`user_favorites`）与跨端阅读进度（`user_reading_progress`），彻底实现个性化数据隔离。
- **识图模块**：采用 **SQLite（`imsearch.db`）+ 二进制倒排索引（`invlists.bin`）**。

### 7.2 性能表现与规模分层评估

- **千本~~万本级（1,000 ~ 10,000 本，数万~~数十万页，个人收藏基线）**：
  - **核心书库**：内存占用约 20~80MB，单本详情与图片读取直接走文件系统 O(1) 路径命中，延迟 <5ms；书架列表全内存秒级过滤。
  - **以图搜图**：特征库体积约数百 MB，检索延迟 10~50ms，单机极速运行。
- **十万本级（100,000 本，数百万页，大型 NAS / 私人资料库）**：
  - **核心书库**：冷启动全量扫描耗时 ~~1-2 秒，内存占用约 300~~600MB；详情与阅读完全不受总书量影响（直接路径查找）。
  - **以图搜图**：SQLite 与倒排索引膨胀至数 GB，内存占用约 1~~2GB，单次检索约 50~~150ms。
- **千万本级（10,000,000 本，数亿页，超大规模极端场景）**：
  - **文件系统瓶颈**：单一目录（如 `library/jm/`）下数千万个子文件夹会导致 ext4/ZFS 目录项遍历变慢，需引入哈希二级分桶（如 `library/jm/ab/cd/<id>/`）；
  - **元数据检索瓶颈**：全量 JSON 无法全驻留内存（需数以十 GB），必须引入 **嵌入式 B-Tree 索引（SQLite / DuckDB / RocksDB）**，书架列表改为 SQL 分页游标；
  - **以图搜图瓶颈**：单机 SQLite 与单机 Faiss 无法承载数亿特征点，需迁移至分布式向量数据库（如 Milvus / Qdrant）与分布式任务队列。
- **设计定位备忘**：纸间品牌定位为「本地优先的个人漫画收藏夹」（个人阅览室），避免为了千万级泛化爬虫场景过早引入重型数据库抽象，遵循当前极简无依赖的高效设计。
