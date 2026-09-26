# ADR 0015 — 万级书库分页架构、SQLite 影子索引与阈值流式展开

- **日期**：2026-09-11
- **状态**：Accepted
- **关联**：承接 ADR 0003 (鉴权与状态解耦)、ADR 0006 (SQLite 隔离)，扩充 `CONTEXT.md` 收藏夹状态与基础设施，演进 `DESIGN_NOTES.md` §55，关联 `docs/PITFALLS.md` 避坑条目

## 背景

纸间（Paper Room）定位于“本地优先的个人漫画收藏夹”。在早期设计中，书架首页采用了“服务端全量下发 + 客户端全量持有”的模型：

1. **服务端**：`/api/library` 接口递归扫描 `backend/data/library/` 目录下所有本子，反序列化 `album.json` 并拼装完整列表；
2. **客户端**：`useLibraryStore` 一次性拉取全库数据，由 `useLibraryFilter` 在主线程内存中执行关键词模糊检索、标签匹配、只看喜欢/已读与多模式排序；
3. **视图渲染**：`ComicGrid` 基于 `usePaginationFold` 按 12 本/批（48 图预算）折叠呈现，尾格提供「再看 12 本」与「展开全部」手动按钮。

随着藏书规模迈向数千乃至上万本，该架构遭遇严峻瓶颈：

- **I/O 与序列化风暴**：单次请求遍历扫描万级目录与反序列化万个 JSON，导致后端秒级延迟与数十兆 JSON 传输；
- **前端内存与算力超载**：上万个 JS 响应式对象在浏览器常驻，主线程模糊匹配与重排产生卡顿；
- **交互割裂感**：读者在浏览过程中必须反复手动点击尾格卡片（「再看 12 本」），缺乏现代化流式阅读的从容感；
- **阅读状态模糊**：现有筛选仅有「只看已读」，缺少「只看在读」，且布尔开关并列容易造成交集为空的非预期状态。

## 方案论证与权衡（Grilling Analysis）

围绕万级规模下的数据底座、交互流畅度与系统韧性，团队展开了针对性审问与技术权衡：

### 1. 后端数据源与索引选型

- **路线 A（纯文件系统游标分页）**：不引入数据库，直接在文件扫描过程中利用目录游标分页。
  - _否决理由_：无法支持多条件组合过滤（标签+在读+喜欢）、跨字段全文模糊检索，更无法实现按标题、更新时间等全局多字段排序。
- **路线 B（Python 进程级常驻缓存）**：服务启动时把全部 `album.json` 加载进 Python 内存，请求时在内存做切片。
  - _否决理由_：万级规模下启动扫描缓慢（几万次 I/O stat），重启容易发生 I/O 痉挛；多 Worker 进程下内存成倍浪费，冷启动不可靠。
- **路线 C（SQLite 藏书影子索引表，推荐）**：
  - _实现原理_：坚守“`album.json` 是本地优先唯一真理源”（目录拷贝即迁移）不变量不变；在现有单文件轻量数据库 `comic_shelf.db` 中建立 `comics_index` 影子索引表，缓存用于检索、排序与分页的元数据。系统启动时轻量校验，写入事件（导入/编辑/重装订/删除）原子同步。
  - _优点_：分页切片、字段排序、模糊检索直接由 SQLite B-Tree 与 SQL 执行，万本耗时 < 2ms；天然支持与 `user_reading_progress` 和 `user_favorites` 动态 `LEFT JOIN`，无需破坏各用户状态隔离。

### 2. 接口端点职责划分

- **路线 A（单一大复合响应）**：`/api/library` 每次分页都携带全库统计数据（总本数、总页数、缓存页数）与全库 Top 18 标签计数字典。
  - _否决理由_：切页与搜索属于高频轻量交互，每次重复序列化与传输数千个标签的计数字典造成无谓带宽损耗。
- **路线 B（端点解耦，推荐）**：
  - `/api/library/facets`：专司全貌统计与高频标签池聚合，首屏请求一次，仅在数据变动（SSE 事件）时静默对齐；
  - `/api/library`：专司受控分页切片，接收 `page`, `page_size`, `status`, `favorite`, `q`, `tag`, `sort` 等轻量参数，返回结构纯净小巧。

### 3. 阅读状态交互维度

- **问题**：「只看喜欢」与「只看已读」当前为独立 Chip。若直接新增「只看在读」Chip，用户若同时勾选「在读」与「已读」，两者的数学交集必定为空，造成白屏困惑。
- **决策**：将阅读状态重构为单选互斥维度（`status: 'all' | 'reading' | 'completed'`），在 UI 上以典雅的**三态分段胶囊（Segmented Control）**呈现；「只看喜欢」保持为正交独立的偏好开关；状态通过 URL Query（`?status=...`）双向同步，确保刷新与回跳精准还原。

### 4. 滚动流式加载与防逃逸平衡

- **问题**：直接滚动到底部自动加载 12 本虽然消除了点击割裂，但若读者快速连滚几十次，会产生两个致命次生灾难：
  1. _归档专匣饥饿（Drawer Starvation）_：主网格底部的「卷末归档专匣（已读完作品）」和页脚被无限向下推远，读者永远无法滑到底；
  2. _显存与 GPU 预算崩溃_：每本包含 4 张高分封面图，连滚 50 批相当于 600 本、2400 张图片塞满 DOM，导致移动端浏览器标签页 OOM 闪退。
- **决策（阈值流式展开与安全刹车）**：
  - 前 5 批（共 60 本 / 240 张封面图）实行**视口触底无感自动平滑加载**，读者滚动即加载，彻底消除点击阻滞；
  - 达到安全阈值（60 本）后，系统主动触发**安全刹车**：停止贪婪自动追加，并在网格末尾露出折叠函套卡，提供「继续展开 24 本」与「展开全部」的主动掌控权，同时确保底部的卷末归档专匣可平滑触达。

---

## 决策与架构契约

### 1. SQLite 影子索引表（`comics_index`）

在 `backend/app/db.py` 中扩展数据库初始化脚本：

```sql
CREATE TABLE IF NOT EXISTS comics_index (
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    display_id TEXT NOT NULL,
    title TEXT NOT NULL,
    authors_json TEXT NOT NULL DEFAULT '[]',
    works_json TEXT NOT NULL DEFAULT '[]',
    actors_json TEXT NOT NULL DEFAULT '[]',
    tags_json TEXT NOT NULL DEFAULT '[]',
    chapter_titles_json TEXT NOT NULL DEFAULT '[]',
    page_count INTEGER NOT NULL DEFAULT 0,
    cached_pages INTEGER NOT NULL DEFAULT 0,
    cover_count INTEGER NOT NULL DEFAULT 4,
    views INTEGER NOT NULL DEFAULT 0,
    likes INTEGER NOT NULL DEFAULT 0,
    published_at TEXT,
    updated_at TEXT,
    imported_at TEXT,
    hidden_from_guest INTEGER NOT NULL DEFAULT 0,
    mtime REAL NOT NULL DEFAULT 0.0,
    PRIMARY KEY (source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_comics_index_imported ON comics_index(imported_at DESC);
CREATE INDEX IF NOT EXISTS idx_comics_index_source ON comics_index(source);
CREATE INDEX IF NOT EXISTS idx_comics_index_title ON comics_index(title);
```

- **同步契约**：
  1. _服务启动_：非阻塞检查 `comics_index` 记录数与 `data/library/` 目录数，若有新增或缺失，后台异步线程池对齐，不阻碍 API 响应；
  2. _写入原子更新_：`Storage.save_fetched()`、`update_metadata()`、`delete()`、`rebind()` 等动作同步执行 `comics_index` 的 Upsert/Delete；
  3. _请求期动态 JOIN_：查询拼装时，动态 `LEFT JOIN user_reading_progress` 和 `LEFT JOIN user_favorites`，按当前请求的 `user_id`（馆长或访客）实时注入 `last_page` 与 `favorite`。

### 2. API 接口规范

#### A. 分页列表查询：`GET /api/library`

- **Query 参数**：
  - `page` (int, default: 1): 当前页码；
  - `page_size` (int, default: 24): 每页条数（配合流式加载，首屏 24 本，后续按 12/24 本步进）；
  - `source` (str, optional): 来源站点过滤（`jm` / `picacg` / `local`）；
  - `status` (str, default: 'all'): 阅读状态（`all` / `reading` / `completed`）；
  - `favorite` (bool, default: false): 是否只看喜欢；
  - `q` (str, optional): 关键词检索（匹配标题、车号、作者、原作、演员、标签及章节名）；
  - `tag` (str, optional): 单标签精准过滤；
  - `sort` (str, default: 'recent'): 排序（`recent` / `title` / `pages` / `cached`）。
- **响应体**：
  ```json
  {
    "items": [/* LibrarySummary 数组 */],
    "total": 12850,
    "page": 1,
    "page_size": 24,
    "has_more": true
  }
  ```

#### B. 全貌统计聚合：`GET /api/library/facets`

- **Query 参数**：`source` (str, optional), `bypass_cache` (bool, optional, 仅限馆长强制跳过进程缓存重算)
- **响应体**：
  ```json
  {
    "stats": {
      "total_books": 12850,
      "total_pages": 482910,
      "cached_pages": 120400
    },
    "top_tags": [
      ["同人", 840],
      ["全彩", 620]
    ]
  }
  ```

### 3. 前端交互与状态设计

1. **左侧筛选栏三态分段胶囊**：
   - `TagFilterBar.vue` 结构演进：
     `[ ♥ 只看喜欢 ]` ｜ `[ 全部 | 在读 | 已读 ]` ｜ `[ 标签池... ]`
   - 切换状态时触发服务端分页刷新，当处于 `reading` 时，底部的「卷末归档专匣」自动隐藏，聚焦案头；
2. **路由持久化（URL Query）**：
   - 筛选状态双向同步至路由：`/?status=reading` 或 `/?status=completed`；
   - 跨路由回跳与前进后退无缝自愈；
3. **阈值流式加载（Stream Loading with Safety Brake）**：
   - 前端集成 VueUse `useIntersectionObserver` 监听列表末尾哨兵；
   - 触底自动触发 `loadMore()`，拉取下一批（12 本）；
   - 连续自动加载达到 5 批（60 本）后进入**安全暂停态**，呈现优雅的折叠函套卡，提示“已呈现案头前 60 本，点击【再看 24 本】或【展开全部】继续”，把控滚动条与内存主权。

---

### 4. 全貌统计（Facets）进程级内存缓存与防击穿保护（2026-09 修订）

针对万级书库下高频请求 `/api/library/facets` 引发全库 `tags_json` 反复执行 `json_each` 虚拟表解包与 Hash 聚合的问题，确立双端闭环内存缓存方案：

1. **服务端进程级内存缓存（0 I/O 读与即时一致性）**：
   - 内存中维护带 `(is_curator, source)` 物理隔离维度的字典缓存，读操作 99.9% 场景耗时降至 0.005ms（零数据库查询）；
   - 写入事件（收录、追更、改标签、删除）执行 `invalidate_facets_cache()` 精准标记失效时间戳，下一次读取自然重算并缓存；
   - 后台单页缓存推进仅更新数据库计数值，待后台任务完成时统一触发失效，从源头杜绝单页下载高频无效失效；
   - 防击穿与时序安全：采用 Double-Checked Locking 避免并发计算风暴（Cache Stampede），时间戳严格锚定计算发起前以规避 TOCTOU 脏读覆写竞态；
   - 权限与安全兜底：支持 `bypass_cache=true` 仅限馆长强制重算；来源参数合法性校验配合 FIFO 淘汰保障容量受控。
2. **前端热门标签对齐全馆真实分布**：
   - `TagManager.vue` 热门快选从当前页 24 本对齐至全馆聚合的 `store.facets?.top_tags`，彻底打通本地上传与编辑标签的热门推荐体验。

---

## 影响与风险评估

1. **历史数据兼容**：老版本升级后首次启动需构建 `comics_index`。通过异步后台冷启动自愈机制处理，不阻塞已有服务；
2. **本地自建与手动拷入感知**：若用户直接在 NAS 操作系统层面手动复制文件夹，下次服务重启时探测扫描自动入库，保持零配置体验；
3. **前端断点与单测覆盖**：现有基于全量内存的 `useLibraryFilter` 单元测试与组件需升级为适配服务端分页契约，确保 0 lint error / 0 regression。
