# 纸间 · Paper Room

一个本地优先的个人漫画书架。
支持 JMComic 禁漫收录与图片反混淆解密，同时提供本地图集与视频拆帧自建工坊。第一次收录后元数据和高清图片全部落在本机；之后浏览、重读、封面都走本地持久化缓存，**0 外部网络冗余请求**。

- **前端**：Vite+（`vp` 工具链 / Vite 8 / Rolldown / Vitest 4 / Oxlint / Oxfmt）+ Vue 3 + TypeScript + Vue Router + Pinia + VueUse
- **样式**：现代原生 CSS（`@layer`、Nesting、`color-mix()`、`oklch()`、`clamp()`，无 SCSS 依赖）
- **后端**：FastAPI + Pillow + jmcomic（基于 Provider 抽象，可轻松接入其他漫画源）
- **搜图**：`imsearch`（独立 Docker Sidecar，基于 OpenCV ORB 局部特征点 + Faiss 倒排索引）

---

## 已实现功能

- **漫画收录与元数据完整映射**：
  - 支持输入 `JM523607`（或纯数字 `523607`）秒级收录；
  - 完整映射禁漫车号、作品标题、登场人物、分类标签、作者、叙述、页数、上传者、上架日期、更新日期、观看数与站内喜欢数。
- **本地自建图集与拆帧工坊（`/create`）**：
  - 支持收录本地图片合集与视频拆帧（如 `public/tiya-frames`）作为自建漫画，与禁漫元数据、阅读器、以图搜图 100% 格式对齐；
  - 网页端多图上传采用 3 路受限并发队列（`useUploadQueue`），平稳保护服务器 IO；
  - 支持服务器本地路径秒级直扫导入（0 网络带宽开销，需通过 `COMIC_SHELF_ALLOWED_DIRS` 白名单放行）；
  - 支持单话/多章节增量追加新页面。
- **典藏资料与封面编排（`EditMetadataModal`）**：
  - 馆长可就地修改作品标题、作者、叙述，全站标签自由增删；
  - **自定义 4 张封面展示页码（`cover_indices`）**：允许指定任意全局页号（如 `[1, 12, 35, 78]`）作为书架叠牌与详情页展示封面，修改后即时击穿缓存热更新。
- **多章节体系（合集/系列平滑支持）**：
  - 详情页按「章节目录」摆放（展示章节封面 + 话标题 + 页数 + 本话缓存进度 %），**不铺开几千页**；
  - 点击某话进入「章节子路由（`/comic/:source/:id/chapter/:chapterId`）」只查看该话页面索引，支持上一话/下一话快速切换、修改章节标题与单话删除；
  - 单章节漫画追加新话时，**系统自动平滑升阶为多章节体系**（自动将旧单章封包为「第 1 话」并迁移目录，无缝衔接「第 2 话」）；
  - 目录封面走服务端章节封面端点（池化缓存，失败优雅回落书脊占位）；
  - 阅读器顶栏实时显示“第 X 話 · 标题”；读到末页浮现「本话完 · 下一话」横幅直达；键盘 `N/P` 跨话翻页；
  - 全局页码拍平设计：全书页面统一为 1..N 全局页号，阅读器、封面、继续阅读心智零割裂。
- **沉浸阅读器**：
  - 竖向连续 / 竖向翻页 / 横向翻页三种模式；
  - 横向模式支持左右滑动切页、鼠标滚轮自动映射为横向滚动，可自由切换“左→右 / 右→左（日漫）”；
  - 每屏支持 1 / 2 / 4 页多列排版；
  - 滚动驱动进度条（CSS Scroll Timeline + JS 兜底）、页码浮动指示、键盘翻页、适应宽度 / 适应高度、全屏沉浸；
  - **全幅加载骨架与独立装订插画**：每次进入漫画随机选取一张角色看板插画并伴随呼吸微光，整本书保持风格一致且彻底杜绝排版跳动；
  - 自动翻页计时辅助（5/10/15/30 秒可选，手动操作重置计时）；
  - 每本漫画独立记忆“上次阅读位置”，详情页一键直达“继续阅读”。
- **局部特征以图搜图（Visual Search）**：
  - 搜索框集成 Chrome Lens 风格识图芯片（带微缩预览、点击放大查看、一键清除 `×`）；
  - 支持直接剪贴板粘贴截图（`Ctrl+V`）、相机图标选择文件、图片拖拽到书架；
  - 局部 ORB 特征匹配：即使只有漫画的一小块分镜、表情包或台词截图，也能毫秒级定位是哪一本作品及具体匹配页码；
  - 书架卡片呈现匹配置信度高亮（如 `第 12 页 · 94%`），一键直达阅读器该页；
  - 支持多模态复合检索（图搜结果与文本关键词、标签 AND 组合筛选）；
  - 优雅降级：未启动识图服务时前端自动呈现提示引导，常规文本与标签检索 100% 正常运行。
- **访问安全、自设 PIN 码认领与全屏 Zero-DOM 门禁（ADR 0011）**：
  - **馆长与专属访客通行证**：环境变量 `COMIC_SHELF_SECRET` 控制馆长全权门禁；馆长在 Web 端「访客簿」中可动态派发个人专属通行证（支持设置 7/30/90/180天/永久有效、免密直达链接、一键续期与密钥换新）；未授权者 100% 拦截（HTTP 401），彻底杜绝公网扫描滥用；
  - **读者自设 PIN 码认领制（Reader PIN Claiming）**：读者首次点开通行证时自行设定 4~6 位纯数字 PIN 码确立号主归属（经 PBKDF2-HMAC-SHA256 100,000 轮安全哈希）；未授权者无法通过 PIN 校验被坚决拦截，彻底阻断群聊转发偷用与恶性互挤；支持合法号主 PIN 码防护下的多端 LRU 漫游自愈；
  - **全屏零残留门禁（Zero-DOM Gate View）**：前端根级采用两态解耦，未鉴权前绝对不挂载应用外壳与任何业务组件，屏幕仅渲染独立门禁纸室，DOM 树物理级 0 残留，彻底杜绝控制台修改 CSS 或删除节点窥探；
  - **个性化数据隔离与全局隐藏**：每位访客的红心收藏与跨端阅读进度基于轻量 SQLite WAL 严格隔离，互不干扰；馆长标记隐藏的漫画对所有访客统一 404 不可见；
  - **现代浏览器级图片防盗链**：结合 `Sec-Fetch-Site: cross-site` 与 `Referer` 拦截，杜绝外站把纸间当图床直连读取解密成品图。
- **案头藏书与卷末归档专匣（Shelf Archive Drawer）**：
  - 书架默认「最近收录」排序下实行两层分桶：案头主书架展示未读与在读作品，已读完藏书整体沉底归档至底部的「卷末归档专匣」；
  - 抽屉支持语义化一键折叠展开、无级尺寸插值（`interpolate-size: allow-keywords`）平滑高度进出场动效、微降权质感陈列，且在全架书目均已读完时智能感知展开；
  - 工具栏提供「只看已读」与「只看喜欢」快速筛选胶囊。
- **阅读器末页接卷推荐（Reader Next Reads）**：
  - 读者翻阅至全本末页结尾卡浮现智能选书微件，视口真实触达（`useIntersectionObserver`）自动将进度标记为完结；
  - 基于作者、原作与标签共有权重的启发式评分算法推荐下一本未读藏书，多端自适应响应式排版（移动端收紧为紧凑图文列表），提供「回到详情」与「返回书架」双向离开出口。
- **长章节分批展开与单话按需离线（ADR 0010）**：
  - 多章节超长连载漫画支持章节目录卡片就地触发单话后台离线下载（`Cache by Chapter`），弥补全本预缓存的粗粒度与网络风险；
  - 面对上百话长篇采用分批展开（首屏 24 话 + 滚动/按需增量），配合内存级 SWR 热复用，子章节与详情页互跳零白屏掉帧；
  - 统一章节内相对页码呈现（`第 N 話 · 第 M 页`）。
- **发现页与排行榜（`/discovery`）**：
  - 支持禁漫原站周榜、月榜、日榜与总榜切换浏览；
  - 包含原站排名徽章、外链、分类胶囊与在库状态感知，未收录漫画可「+ 一键收录」。
- **书架渲染性能与 48 图预算（Shelf Chunking）**：
  - 每本漫画展示 4 张封面，默认采用 **12 本/批（严格对应 12 × 4 = 48 张封面图）** 的增量呈现步长；
  - 接入 VueUse `useIntersectionObserver` 监听底部哨兵平滑展开；
  - 卡片使用 `contain: layout style` + `container-type: inline-size` 严格隔离，杜绝浮动裁切瑕疵。
- **统一矢量图标集与现代浮层基建**：
  - 全站图标收敛到 `src/components/icons/`（1.8px 细线条描边 / 朱砂质感），零 Unicode 伪字符（`✕`/`✓`）；
  - 基于 HTML Popover API 与 CSS Anchor Positioning 规范构建现代浮层，包含 `Modal`、`AppPopover`、`AppDropdown` 与带悬停安全桥的 `AppTooltip`。
- **PWA 独立安装、离线存储与零轮询系统事件流**：
  - **标准 PWA 规范支持**：完整支持桌面/移动端独立窗口安装（Standalone）、离线秒开与后台静默更新，符合 W3C Web App Manifest 与 Service Worker 规范；
  - **优雅装订提醒（Prompt 模式）**：前端采用非侵入式悬浮装订横幅（`UpdateBanner`），阅读器沉浸模式下自动隐退避让，新版本随时在顶栏设备卡片内就绪装订；
  - **零轮询单向系统事件流（SSE `/api/events/stream`）**：版本发布、多端书架实时同步（藏书导入/删除即时反映）与后台下载完成通过轻量 SSE 广播，0 CPU 轮询开销；
  - **分级离线缓存体系**：基于 Workbox 实现 App Shell 核心资产预缓存 + 漫画原图/缩略图 Cache-First（最大 3000 篇目 LRU 自动淘汰）+ 动态 API 内存态 SWR 直连（零脏鉴权缓存）；
  - **端侧存储独立账单与安全边界**：基于 `navigator.storage.estimate()` 毫秒级探测本机物理占用，清晰展示核心资产与漫画图片分项；
  - **两档安全清理**：日常级「清理阅览图片缓存」一键安全释放设备空间；重置级提供 5 秒两步倒计时防误触防线；
  - **绝对数据安全**：清理逻辑 100% 运行于浏览器端侧，零破坏性后端调用，**绝对不触碰服务器已下载珍藏数据（`backend/data/`）**。

---

## 本地运行与开发

项目使用 Vite+ 工具链，日常命令使用 `vp`（或通过本地 npm scripts 调用）。

```bash
# 1. 初始化 Python 后端依赖（创建 .venv 并安装依赖）
pnpm setup:py

# 2. 安装前端依赖
vp install
# 或 pnpm install

# 3. 启动开发环境（前后端热重载）
pnpm dev:all

# 或分别启动：
pnpm api       # 后端 FastAPI（端口 8000）
vp dev         # 前端 Vite+（端口 5173，已自动反代 /api 到 8000）
```

常用质量与维护命令：

```bash
vp check                               # 格式化 + Lint + 类型检查
vp test src/__tests__/<Target>.spec.ts # 精准单测验证（严禁日常全量）
pnpm reindex:image                     # 增量追加以图搜图索引（秒级完成，自动适配本地/Docker环境）
vp build                               # 生产打包
```

> 💡 **以图搜图索引构建**：批量收录或缓存新漫画后，随时可在终端执行 `pnpm reindex:image` 秒级追加新图特征至倒排索引；若宿主机未编译 `imsearch`，脚本会自动检测正在运行的 Docker 识图容器并在容器内执行。更多说明详见下文以图搜图章节。

---

## Docker & TrueNAS 部署（推荐）

纸间支持 Docker Compose 一键启动或 NAS（TrueNAS Scale / Unraid / 群晖）图形化部署，开箱即用：

```bash
# 方式 1：双容器一键启动（含以图搜图，需 CPU 支持 AVX2）
docker compose up -d --build

# 方式 2：极简轻量单容器启动（推荐低功耗 NAS 如 N5095/N5105/J4105，加 --no-deps 跳过搜图避免 132 报错）
docker compose up -d --no-deps --build paper-room

# 常用启停运维：
# docker compose down                # 停止并移除容器
# docker compose logs -f paper-room  # 查看主服务运行日志

# 访问阅览室：浏览器打开 http://<服务器IP>:8000
```

> **⚡ 容器环境变量与部署核对（Docker 零依赖，无需 .env 文件）**：
>
> - 🔴 **公网 / VPS 部署唯一必配**：设置容器环境变量 `COMIC_SHELF_SECRET="你的管理密码"`（可在 `docker-compose.yml` 的 `environment` 节直接填入，或在 NAS 图形界面添加；纯内网家庭环境直接留空免密）；
> - 🟡 **存储持久化生命线**：将宿主机存储卷映射至容器内的 `/app/data`（所有漫画原图、元数据与搜图索引均保存在此处）；
> - 🟢 **其余所有 20 个环境变量**：全部内置生产级默认值（8000 端口、3 路防封下载并发、4 路缩略图限流等），初次部署完全不用改动。
>
> 📖 **完整部署指引与参数字典**：包含 TrueNAS Scale、Unraid、群晖 NAS 挂载配置、22 个环境变量详解、反向代理与权限排查，请参阅 **[DEPLOYMENT.md](DEPLOYMENT.md)**。

---

## 部署后如何触发以图搜图索引（`reindex:image`）

纸间对已缓存的漫画采用**增量索引机制**：导入漫画时不会阻塞主线程，由管理员在批量导入后按需更新特征库。

### 1. Docker Compose 容器内一键触发（最常用）

无需在服务器安装 Rust 或任何依赖，直接在终端执行：

```bash
# 【日常增量追加】扫描新增漫画并秒级推入倒排索引（旧特征 100% 保留，零重复计算）：
docker compose exec imsearch sh -c "imsearch add /app/data/library && imsearch build"
docker compose restart imsearch

# 【全量重置重训】重新训练 512 聚类中心并重建索引（首次初始化或强制重构时使用）：
docker compose exec imsearch sh -c "imsearch add /app/data/library && imsearch train -c 512 -i 800 -m 30 && rm -f /root/.config/imsearch/invlists.bin && imsearch build"
docker compose restart imsearch
```

### 2. 宿主机 / WSL2 一键服务运维（分布式高性能识图）

当 NAS 为低功耗 CPU 时，可在电脑/WSL2 上运行 `imsearch`，通过 SMB 挂载 NAS 漫画目录进行高性能识图：

```bash
pnpm imsearch start    # 后台启动识图服务 (:8765)
pnpm imsearch stop     # 停止服务
pnpm imsearch restart  # 重启服务
pnpm imsearch status   # 查看运行状态与健康度
pnpm imsearch reindex  # 日常增量追加新本子特征并自动热重载（秒级）
pnpm imsearch train    # 全量重新训练 512 聚类中心并重建索引
pnpm imsearch logs     # 查看实时搜索日志
```

### 3. 宿主机一键脚本智能代理（单机 Docker 模式）

如果你在项目根目录下，也可直接运行：

```bash
# 日常增量构建（脚本会自动检测正在运行的 Docker 识图容器并自动在容器内执行）
pnpm reindex:image
# 或直接运行
bash scripts/reindex.sh

# 全量重训模式
bash scripts/reindex.sh --full
```

---

## 存储路径与数据结构

数据目录统一受 `COMIC_SHELF_DATA` 控制（默认 `backend/data`，Docker 内为 `/app/data`）：

```text
$COMIC_SHELF_DATA/
├── jm_html_domain.json                  # 禁漫网页域名 6 小时缓存
├── imsearch/                            # 识图索引与特征库（centroids.bin / invlists.bin / imsearch.db）
└── library/
    └── <source>/                         # provider key：jm / local
        └── <source_id>/                  # 禁漫车号或自建 ID（如 523607 / LOC_tiya-frames）
            ├── album.json                # 元数据 + favorite + pages[].cached + chapters[] + cover_indices[]
            ├── remote.json               # 远端 URL + scramble_id + decode_version
            ├── pages/00001.webp          # 单章节：已解密拼好的成品页（扁平）
            ├── pages/<chapter>/00001.webp# 多章节：页面按章节 ID 分落子目录
            ├── covers/001.jpg            # 展示封面
            ├── covers/chapters/<cid>.jpg # 章节封面池
            ├── thumbs/00001.jpg          # 单章节：360px 索引缩略图
            └── thumbs/<chapter>/00001.jpg# 多章节：分章节 360px 缩略图
```

> **全书拍平设计**：`album.json` 的 `pages` 始终是全书拍平的全局页码表（1..`page_count`），每页记录所属 `chapter`；`chapters[]` 记录各章节的 id、标题、页数及起始全局页（`start`）。单章节与多章节数据结构向前兼容，旧缓存零迁移。

---

## 接口与开发文档索引

纸间拥有完备的接口定义与系统设计文档体系：

| 文档                                                           | 内容与定位                                                                                                            |
| :------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------- |
| **交互式 API 文档**                                            | 启动服务后浏览器直接访问 `http://localhost:8000/docs`（Swagger UI）或 `/redoc` 查看全部实时端点、请求模型与参数定义   |
| **[CONTEXT.md](CONTEXT.md)**                                   | 纸间领域模型与术语表（单一语义源，核心概念、收藏夹状态、阅读器与基础设施定义）                                        |
| **[DEPLOYMENT.md](DEPLOYMENT.md)**                             | 生产容器化部署全景：Docker Compose、TrueNAS Scale / Unraid / 群晖 NAS 挂载配置、22 个环境变量详解、反向代理与权限排查 |
| **[docs/PITFALLS.md](docs/PITFALLS.md)**                       | 错题本与避坑红线速查表（历史故障复盘、高频反模式与避坑红线速查，提交前必读）                                          |
| **[docs/CSS_RADAR.md](docs/CSS_RADAR.md)**                     | CSS 前瞻技术雷达（已落地特性用法、渐进增强降级方案与前沿规范追踪）                                                    |
| **[docs/JS_RADAR.md](docs/JS_RADAR.md)**                       | JavaScript 前瞻技术雷达（原生异步承诺管线、AbortSignal 规范与集合运算）                                               |
| **[docs/agents/architecture.md](docs/agents/architecture.md)** | 后端架构设计、数据存储模型、Provider 扩展体系、安全门禁与 SSE 单向事件流                                              |
| **[docs/agents/frontend.md](docs/agents/frontend.md)**         | 前端视图与 Composable 地图、阅读器分页与手势、PWA 离线缓存与性能策略                                                  |
| **[DESIGN_NOTES.md](DESIGN_NOTES.md)**                         | 纸间设计系统规范（Living Design System）、品牌哲学、色彩/组件层级与核心设计定律（历史演进见 `docs/design-archive/`）  |
| **[docs/adr/](docs/adr/)**                                     | 架构决策记录（Architecture Decision Records，涵盖系统重大架构抉择，ADR 0001 ~ 0011）                                  |

---

## 扩展其他漫画站（Provider 体系）

1. 在 `backend/app/providers/` 新建文件，继承 `ComicProvider`；
2. 实现 `normalize_id`、`fetch`（只抓取元数据与图片 URL，不下载实体图片）和 `download_page`；
3. 在 `backend/app/providers/registry.py` 中注册该 Provider。

存储层、缓存管理、API、前端封面与阅读器将自动获得新站点支持，前端不需要改动任何业务渲染代码。

---

## 开源协议与鸣谢（License & Acknowledgements）

本项目基于 **MIT License** 开源。感谢以下优秀的开源项目与社区生态：

- [JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python) (MIT License) — 提供了可靠的禁漫元数据解析与图片反混淆解密算法。
- [imsearch](https://github.com/lolishinshi/imsearch) (GPL-3.0 License) by @aloxaf — 高性能二次元局部特征点图片搜索引擎（本项目通过独立容器 HTTP API 网络隔离调用，严格保障纸间项目的 MIT 开源合规性）。
- [FastAPI](https://fastapi.tiangolo.com/) & [Uvicorn](https://www.uvicorn.org/) — 高性能 Python 异步后端。
- [Vue.js](https://vuejs.org/) / [VueUse](https://vueuse.org/) / [Pinia](https://pinia.vuejs.org/) — 优雅轻盈的前端生态。
- [Vite+](https://viteplus.dev/) — 现代化统一前端工具链。

---

## 版权提示

请只缓存你有权保存、且用于个人学习交流的内容。不要公开部署、不要传播。
