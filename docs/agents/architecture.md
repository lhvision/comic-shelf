# 架构与不变量（详细规则）

> 给后续 AI / 维护者：先读这份文件，再改代码。品牌名「纸间 Paper Room」。目标是“本地优先的个人漫画收藏夹”，
> 不是泛化爬虫，也不是公开站点。

## 1. 项目现状

- 位置：`/home/miku/dsh/comic-shelf`
- 已实现：书架、导入禁漫车、详情页、封面流、阅读器（三种模式 + grid 分页）、本地缓存。
- 代码迁移时未复制 `backend/data/`；首次收录后会自动生成本地缓存。
- 服务启动后：
  - API: http://127.0.0.1:8000 （FastAPI docs 在 `/docs`）
  - Web: http://127.0.0.1:5173 （Vite，`/api` 代理到 8000）

## 2. 技术栈

| 层       | 技术                                                                       |
| -------- | -------------------------------------------------------------------------- |
| 前端     | Vite 8 + Vue 3 + TypeScript + Vue Router + Pinia                           |
| 样式     | 原生 CSS：`@layer`、Nesting、`color-mix()`、`oklch()`、`calc()`、`clamp()` |
| 后端     | Python 3.14 + FastAPI + uvicorn                                            |
| 禁漫源   | `jmcomic==2.7.4`（metadata 用 HTML client，图片算法用 `JmImageTool`）      |
| 图片处理 | Pillow（封面缩略图、解密）                                                 |

约定：**不用 SCSS**。新增视觉请走 `src/styles/tokens.css` 的设计 token。
设计基线见 `DESIGN_NOTES.md`：私人阅览室 / 卡片目录，禁紫色渐变，禁玻璃拟态堆叠。

## 3. 架构

```text
Browser (Vue 3)
   │  /api/*
   ▼
FastAPI (backend/app/main.py)
   │
   ├── providers/           # 站点适配层，唯一知道具体漫画站的地方
   │     base.py            # ComicProvider 抽象
   │     jm.py              # 禁漫实现
   │     registry.py        # 注册表
   │
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
| `backend/app/main.py`               | FastAPI 路由                                                                                           |
| `backend/app/models.py`             | 通用模型：`ComicMeta`（含 `Chapter`/`chapters`）/ `PageRecord.chapter` / `RemotePage` / `FetchedComic` |
| `backend/app/storage.py`            | 原子 JSON 写入、页面缓存（章节分目录路由）、封面生成、v1→v2 迁移、书库扫描                             |
| `backend/app/providers/base.py`     | Provider 接口                                                                                          |
| `backend/app/providers/jm.py`       | JM HTML 元数据、上传者解析、**多章节 episode 逐话拉取**、图片下载 + 解密                               |
| `backend/app/providers/registry.py` | `{"jm": JMProvider()}`                                                                                 |
| `backend/app/config.py`             | 数据目录、封面尺寸、预缓存上限                                                                         |

### API 摘要

- `GET /api/library`（`q` 也能命中章节标题，T11）
- `POST /api/library/import` `{id, source, prefetch_covers, prefetch_all, refresh}`
  （`refresh=true` 走增量，章节未变则复用旧 remote，T12）
- `GET /api/library/{source}/{id}`（详情含 `chapters`）
- `PATCH /api/library/{source}/{id}/favorite` `{favorite: bool}`
- `GET /api/library/{source}/{id}/pages/{n}/file`（`n` 为全局页号，多章节自动路由）
- `GET /api/library/{source}/{id}/pages/{n}/thumbnail`（同上）
- `GET /api/library/{source}/{id}/covers/{n}/file`（封面取第一章前 N 页）
- `GET /api/library/{source}/{id}/chapters/{chapterId}/cover`（章节封面端点，T17）
- `GET /api/providers`
- `POST /api/library/{source}/{id}/cache`
- `DELETE /api/library/{source}/{id}`

页面 / 封面响应带 `Cache-Control: no-cache`，防止浏览器缓存旧图或乱图。
