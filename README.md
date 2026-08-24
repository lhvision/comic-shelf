# 纸间 · Paper Room

一个本地优先的个人漫画书架。使用 JMComic-Crawler-Python 拉取禁漫资料与图片，
第一次导入后元数据和图片全部落在本机；之后浏览、重读、封面都走本地缓存，
**不会重复请求漫画站**。

前端：Vite+（`vp` 工具链 / Vite 8 / Rolldown / Vitest 4 / Oxlint / Oxfmt）+ Vue 3 + TypeScript + Vue Router + Pinia
后端：FastAPI + jmcomic（可替换为任意漫画站的 provider）

## 已实现

- 输入 `JM523607`（或 `523607`）收录本子
- 元数据完整映射：禁漫车、作品、登场人物、分类标签、作者、叙述、页数、
  上传者、上架日期、更新日期、观看数、点击喜欢
- 封面直接用首页前 4 张生成 JPEG 缩略图；详情页是 CSS scroll-snap 封面轮播
- 阅读页：
  - 竖向连续 / 竖向翻页 / 横向翻页三种模式；
  - 横向支持左右滑动切页、鼠标滚轮自动映射为横向滚动，可切换“左→右 / 右→左（日漫）”；
  - 每屏可配置 1 / 2 / 4 页 grid 显示；
  - 滚动驱动进度条、页码指示、键盘翻页、适应宽度 / 适应高度、全屏、继续阅读；
  - 每页独立 loading：每次进入一本漫画随机选一张 WebP 插画并伴随呼吸微光，整本书保持一致；
  - 失败重试；
  - 页面索引性能：默认只渲染 48 张缩略图，滚动后增量加载；页面原图不用于索引网格。
  - 喜欢标记：书架卡片可点心形标记喜欢，支持“只看喜欢”快速筛选。
- 多章节支持（本部作品可以是多话合集/系列）：
  - 详情页按「章节目录」摆放（封面 + 话标题 + 页数 + 本地缓存 %），**不铺开几千页**；
    点某话进入「章节子路由」只看这一话的页面索引（带上一话/下一话与章节快速跳转）；
  - 目录封面走服务端章节封面端点（池化缓存，失败回落书脊占位）；
  - 阅读器：顶栏显示“第 X 話 · 标题”；读到某话末页浮现「下一话」直达；键盘 `N/P` 跨话翻页；
  - 所有页面仍按「全局页码」拍平：阅读器页面、继续阅读、封面、缓存进度沿用旧心智，
    点任意页即可从正确的章节/页码开始读；
  - 书架搜索能命中章节标题（如搜「初见」/「第 5 话」）；
  - 单章节（含旧缓存）体验完全不变——详情页直接平铺每页，无目录。
- 实验功能：书架卡片可切换为 HTML-in-Canvas 渲染（需要 Canary 149+ 并开启
  `canvas-draw-element`），把封面、标题、标签、缓存进度等多个 DOM 节点绘制进一个 canvas。
  - 阅读设置持久化在浏览器 localStorage。
- 本地优先策略：
  - 导入时先查 `album.json`，存在则直接返回（0 网络请求）
  - 图片按需懒下载；也可一键“缓存全部”
  - 删除后彻底移除本地文件
- 禁漫图片解密：页面先按原图下载，再调用 jmcomic 官方的
  `JmImageTool.decode_and_save()` 进行分割 / 拼接，和
  `JmDownloader` 使用同一套算法
- 以图搜图（Visual Search）：
  - 搜索框集成 Chrome Lens 风格识图芯片（带预览缩略图、点击放大查看、一键清除 `×`）；
  - 支持直接剪贴板粘贴截图（`Ctrl+V`）、相机图标文件上传、图片拖拽到书架；
  - 局部特征匹配（ORB + Faiss/BIVF 聚类检索）：即使只有漫画的一小块分镜/表情包截图，也能毫秒级定位是哪一本作品及具体匹配页；
  - 书架卡片呈现匹配置信度高亮（如 `第 12 页 · 94%`），并支持一键直达阅读器该页；
  - 支持多模态复合检索（图搜结果与文字关键词、标签 AND 组合筛选）；
  - 优雅降级：未启动识图服务容器时前端自动呈现提示引导，常规文本与标签检索 100% 正常运行。
- 访问安全与防盗链（Security & Hotlink Protection）：
  - 双口令门禁体系（`COMIC_SHELF_SECRET` 馆长口令 + `COMIC_SHELF_GUEST_SECRET` 访客口令）：留空即内网免密；设置后全站启用门禁保护，单输入框智能识别馆长与访客，未授权请求 100% 拦截（HTTP 401），彻底杜绝公网肉鸡与扫描滥用；
  - 现代浏览器级图片防盗链拦截：结合 `Sec-Fetch-Site: cross-site` 与 `Referer` 白名单校验，彻底杜绝外站把纸间当图床/存储桶直连读取解密成品图；
  - 双轨凭证支持：`SameSite=Lax` Cookie 与 `Authorization: Bearer` 自动联动，原生 `<img>` 标签零改造安全加载。
- 本地自建图集与拆帧工坊（Local Workshop & Ingestion）：
  - 支持收录本地图片合集与视频拆帧（如 `public/tiya-frames`）作为自建漫画，与禁漫漫画元数据、阅读器、以图搜图 100% 无缝兼容；
  - 开辟大画幅自建工坊（`/create`）与书架快速通道，支持单话平铺与多章节编排；
  - 网页多图上传采用 3 路受限并发上传队列（`useUploadQueue`），保护服务器 IO；支持服务端本地目录秒级直扫收录（0 网络开销）；
  - 支持单话/多章节增量追加页面；
  - 典藏资料与标签编排（`EditMetadataModal`）：支持标题、作者、叙述修改，自定义 4 张封面展示页码（`cover_indices`，支持任意全局页号并带热更新缓存击穿），全站标签增删（仅限馆长权限）与全书库热门快选推荐。

- 架构上把站点差异隔离在 `backend/app/providers/`，UI 与存储层只认通用模型

## 运行

项目已迁移到 Vite+，日常命令使用 `vp`。仓库的 `vite-plus` 依赖会在
`node_modules/.bin` 提供本地 `vp`，所以 `pnpm run dev/build` 也能工作。

```bash
# 0) 安装 vp CLI（本仓库已迁移；换机器时先安装）
curl -fsSL https://vite.plus | bash

# 1) Python 后端依赖（支持一键初始化 .venv）
pnpm setup:py
# 或手动：python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt

# 2) 前端依赖（vp 会使用 package.json 声明的 pnpm 11.22.0）
vp install

# 3) 启动后端（端口 8000，智能探测虚拟环境并支持热重载）
pnpm api

# 4) 另开终端启动前端（端口 5173，已代理 /api 到 8000）
vp dev
```

常用质量命令：

```bash
vp check   # fmt + lint + type-check
vp test    # Vitest
vp build   # 生产构建
vp preview # 预览 dist
```

或一键启动前后端全套开发环境（自动热重载）：

```bash
pnpm dev:all   # 或 ./scripts/dev.sh
```

打开 <http://127.0.0.1:5173>。

## 存储路径与变量标识

**根目录只有一个变量，所有路径都由它派生：**

| 变量 / 常量          | 默认值                      | 说明                               |
| -------------------- | --------------------------- | ---------------------------------- |
| `COMIC_SHELF_DATA`   | `backend/data`              | 数据根目录，所有漫画缓存都在它下面 |
| `LIBRARY_DIR`        | `$COMIC_SHELF_DATA/library` | 书库根目录                         |
| `TMP_DIR`            | `$COMIC_SHELF_DATA/tmp`     | 下载临时文件目录                   |
| `COVER_WIDTH`        | `840`                       | 封面宽度 px                        |
| `COVER_QUALITY`      | `82`                        | 封面 JPEG 质量                     |
| `PAGE_THUMB_WIDTH`   | `360`                       | 页面索引缩略图宽度 px              |
| `PAGE_THUMB_QUALITY` | `78`                        | 页面索引缩略图 JPEG 质量           |
| `MAX_PREFETCH`       | `600`                       | 一次“缓存全部”的最大页数           |

对应代码位置：`backend/app/config.py`。

**单本漫画的固定布局：**

```text
$COMIC_SHELF_DATA/
├── jm_html_domain.json                  # 禁漫网页域名 6 小时缓存
└── library/
    └── <source>/                         # provider key：jm / picacg ...
        └── <source_id>/                  # 例如 523607
            ├── album.json                # ComicMeta：元数据 + favorite + pages[].cached + chapters[]
            ├── remote.json               # 页面 URL + scramble_id + decode_version
            ├── pages/00001.webp          # 单章节：已解密、拼好的成品页（扁平）
            ├── pages/<chapter>/00001.webp# 多章节：页面按章节 id 落到子目录
            ├── covers/001.jpg            # 首页（第一章）生成的封面
            └── thumbs/00001.jpg          # 单章节：详情页索引用的 360px 缩略图
            └── thumbs/<chapter>/00001.jpg# 多章节：缩略图同样按章节分目录
```

> 多章节说明：`album.json` 的 `pages` 仍是**全书拍平的全局页码表**，只是每页多了
> `chapter` 字段；`chapters[]` 记录每个章节的 id / 序数 / 标题 / 页数 / 起始全局页。
> 旧单章节缓存没有 `chapter` 与 `chapters`，读取时按默认值处理，零迁移。

前端存储键：

| Key                                   | 用途                              |
| ------------------------------------- | --------------------------------- |
| `comic-shelf:reader-settings:v1`      | 阅读模式 / 每屏页数 / 方向 / 适配 |
| `comic-shelf:experiments:v1`          | HTML-in-Canvas 实验开关           |
| `comic-shelf:last-read:<source>/<id>` | 每本最后阅读页                    |

`remote.json` 里的 `decode_version` 当前为 `2`。旧版 v1 缓存如果存了
未解密的原始图，后端会在读取书架时**用本地文件直接解密迁移**，不需要
重新下载。封面会在迁移后自动用解密图重新生成。

## API 一览

| Method | Path                                             | 说明                                                                   |
| ------ | ------------------------------------------------ | ---------------------------------------------------------------------- |
| GET    | `/api/library`                                   | 书架列表（支持 `q` 过滤）                                              |
| POST   | `/api/library/import`                            | 收录，body: `{id, source, prefetch_covers, prefetch_all, refresh}`     |
| GET    | `/api/library/{source}/{id}`                     | 详情 + 缓存状态（含 `chapters`）                                       |
| GET    | `/api/library/{source}/{id}/pages/{n}/file`      | 页面原图（`n` 为全局页号，多章节自动路由到所在章节），未缓存时自动下载 |
| GET    | `/api/library/{source}/{id}/pages/{n}/thumbnail` | 页面 360px 缩略图（同上，全局页号），页面索引使用                      |
| GET    | `/api/library/{source}/{id}/covers/{n}/file`     | 第 n 张封面缩略图                                                      |
| POST   | `/api/library/{source}/{id}/cache`               | 缓存全部页面                                                           |
| PATCH  | `/api/library/{source}/{id}/favorite`            | 标记 / 取消喜欢                                                        |
| DELETE | `/api/library/{source}/{id}`                     | 删除本地缓存                                                           |
| GET    | `/api/providers`                                 | 已注册站点 provider                                                    |

## 扩展其他漫画站

1. 在 `backend/app/providers/` 新建文件，继承 `ComicProvider`；
2. 实现 `normalize_id`、`fetch`（只取元数据和图片 URL，不下载图片）、
   `download_page`；
3. 在 `backend/app/providers/registry.py` 注册。

存储、缓存、API、前端封面 / 阅读器自动获得新站点支持，前端不需要改渲染逻辑。

## HTML-in-Canvas 说明

这是一个实验性、可开关的渲染路径：

- 书架页有“实验：HTML-in-Canvas 卡片”开关；
- 开启后 `HtmlCanvasCard.vue` 会把整张卡片的多个 DOM 节点
  （封面、标题、作者、标签、缓存进度）通过 `HtmlCanvasSurface.vue`
  绘制进一个 canvas；
- 交互由透明 `<RouterLink>` overlay 保留；
- 不支持时自动回退为普通 DOM 卡片，页面不因此受影响；
- 需要 Canary 149+ 开启 `chrome://flags/#canvas-draw-element`；正式域名
  还需在 `index.html` 填入 Origin Trial token。

## CSS 说明

- 未使用 SCSS。生产样式全部是原生 CSS：`@layer`、CSS Nesting、
  `color-mix()`、`oklch()`、`clamp()`、`calc()`；
- 封面轮播使用 `scroll-snap` + `view-timeline` 滚动驱动动画；
- 阅读进度条使用 `scroll-timeline` 滚动驱动动画，并带 JS fallback；
- 项目未使用 `@function`（该语法尚未稳定），当前使用的原生函数为
  `calc()` / `clamp()` / `min()` / `max()` / `color-mix()` / `oklch()`。

## 元数据来源说明

JM 的 HTML 页面包含你列的全部字段；本项目首次导入会抓取 `/album/{id}` 与
`/photo/{id}` 两个 HTML 页面（两次请求），之后元数据不再请求。
“上传者”是从 HTML 的 `上传者：` 字段解析的，API 端没有该字段。
观看 / 喜欢保存为站内展示值（如 `221K`、`13K`）。

## Docker & TrueNAS 部署（All-in-One 单容器，免 Nginx）

纸间支持 **All-in-One 单容器部署**：FastAPI 后端内置托管 Vue 3 SPA 前端与静态资源，单个容器、单个端口（8000）、无需配置 Nginx，非常适合 **TrueNAS Scale / Unraid / 群晖 / 树莓派 / 标准 Docker** 环境。

### 方式 1：Docker Compose 一键启动（含以图搜图 Sidecar）

```bash
docker compose up -d --build
# 浏览器打开 http://127.0.0.1:8000
```

_(同时拉起纸间核心服务 `:8000` 与本地识图引擎 `:8765`)_

### 方式 2：TrueNAS / Docker CLI 单容器运行

```bash
docker build -t paper-room .

docker run -d \
  --name paper-room \
  -p 8000:8000 \
  -v ./backend/data:/app/data \
  --restart unless-stopped \
  paper-room
```

漫画数据与元数据持久化挂载在宿主机 `./backend/data`（或 NAS 存储池），容器升级重建数据不丢失。

## 以图搜图服务配置与索引管理（可选）

纸间支持通过局部截图检索漫画作品（基于局部 ORB 特征点匹配）：

- **Docker 运行（推荐）**：使用 `docker compose up -d` 即可自动启动官方 `aloxaf/imsearch:latest` 容器，开箱即用。
- **本地源码编译运行（可选）**：
  ```bash
  # 1. 安装系统 C++ 依赖
  sudo apt update && sudo apt install -y cmake clang libopencv-dev libopenblas-dev libssl-dev pkg-config
  # 2. 编译安装 imsearch
  cargo install --git https://github.com/lolishinshi/imsearch --locked
  ```
  安装后运行 `pnpm dev:all`，启动脚本会自动检测并拉起本地 `imsearch` 服务。
- **数据持久化与迁移**：
  - 识图索引与特征数据库统一保存在 **`backend/data/imsearch/`** 目录下；
  - 备份、打包迁移只需复制整个 `backend/data/` 目录，所有漫画、元数据与搜图索引一同保留。
- **主动重新训练 / 构建索引**：
  当批量导入新漫画后，如需更新搜图特征库，可随时在终端运行：
  ```bash
  pnpm reindex:image
  # 或直接运行
  bash scripts/reindex.sh
  ```
  该命令会自动扫描全部已缓存页面与封面、进行 2048 聚类中心训练并生成倒排索引。
- **未启动状态**：未启用识图服务时，纸间所有常规功能（文本/标签检索、阅读器、多章节等）**100% 正常工作**，前端搜索框会自动展示提示引导。

## 开源协议与鸣谢（License & Acknowledgements）

本项目基于 **MIT License** 开源。感谢以下优秀的开源项目与社区生态：

- [JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python) (MIT License) — 提供了可靠的禁漫元数据解析与图片反混淆算法。
- [imsearch](https://github.com/lolishinshi/imsearch) (GPL-3.0 License) by @aloxaf — 优秀的高性能局部特征点图片搜索引擎（本项目通过独立进程 HTTP API 网络隔离调用，保障项目 MIT 开源纯洁性）。
- [FastAPI](https://fastapi.tiangolo.com/) (MIT License) & [Uvicorn](https://www.uvicorn.org/) (BSD-3-Clause) — 高性能 Python 异步后端。
- [Vue.js](https://vuejs.org/) / [VueUse](https://vueuse.org/) / [Pinia](https://pinia.vuejs.org/) (MIT License) — 优雅轻盈的前端生态。
- [Vite+](https://viteplus.dev/) — 现代化前端构建与开发工具链。

## 版权提示

请只缓存你有权保存、且用于个人学习的内容。不要公开部署、不要传播。
