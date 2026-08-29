# 纸间部署指南（Docker & TrueNAS / NAS / VPS）

当前项目：Vite+（Vite 8 / vite-plus）+ Vue 3 SPA + FastAPI + jmcomic。

支持 **All-in-One 单容器一键部署**（无需 Nginx，前后端由 FastAPI 统一在单个端口托管），非常适合 **TrueNAS Scale / Unraid / 群晖 NAS / 标准 Docker / VPS** 环境。

---

## ⚡ 30 秒部署前速查：必要参数与挂载清单

马上开始部署前，请花 30 秒核对这 3 点：

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 1. 核心存储挂载（数据生命线）：                                                  │
│    容器内路径必须严格映射为【/app/data】！                                        │
│    所有已缓存漫画原图、元数据（album.json）、搜图特征库均落在此处。挂错路径容器重启数据全丢！ │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 2. 环境变量填写决策（我到底需要填什么？）：                                      │
│    🔴 公网 / VPS / 反代部署【唯一强制必填】：                                    │
│       COMIC_SHELF_SECRET="你的管理密码" （防公网未授权，不填将导致任意人可删书/下载） │
│    🟡 纯内网 / 私人家庭环境【零配置全免填】：                                    │
│       所有环境变量直接留空！开箱即用，享受局域网免密极速阅览。                  │
│    🔵 从 NAS 外部目录直扫收录【条件必填】：                                      │
│       COMIC_SHELF_ALLOWED_DIRS="/external_manga" （放行安全沙箱白名单）         │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 3. 其余 19 个环境变量：                                                         │
│    ✅ 全部已内置生产级开箱默认值（8000端口、3路防封并发、4路缩略图限流等），无需修改！  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. 架构形态

纸间支持两种部署形态，可根据是否需要「以图搜图（局部特征截图检索）」按需选择：

### 形态 A：Docker Compose 双容器（含以图搜图 Sidecar，推荐）

```text
Browser (Web UI)
  │ :8000
  ▼
Paper Room (Web & API 核心容器)
  ├── /            → Vue 3 SPA 静态页面 (dist)
  ├── /api/*       → FastAPI 后端接口
  ├── /app/data    → 持久化数据目录（漫画原图、元数据）
  └── (HTTP IPC)   → 连接 imsearch Sidecar (:8765) 进行局部特征向量检索
```

- **完整体验**：开箱支持根据漫画局部截图、表情包、分镜秒级反查作品与具体页码；
- **开源合规隔离**：`imsearch`（GPL-3.0）作为独立容器运行并通过 HTTP API 隔离，保障纸间（MIT）源码合规。

### 形态 B：All-in-One 单容器（免以图搜图，极速轻量）

- **单容器、单端口**：单个 Docker 容器直接运行 FastAPI + 静态前端，省去配置 Nginx 反向代理和双容器网络的复杂性；
- **极速低耗**：非常适合仅需离线看书、整理收藏的低配 NAS 或轻量 VPS；
- **优雅降级**：未启动 `imsearch` 时，全站文本搜索、分类筛选、多章节阅读器 100% 正常运行。

---

## 2. 快速启动

### 方式 A：Docker Compose 一键启动（推荐）

```bash
# 1. （可选）若公网部署需设置密码，可直接编辑 docker-compose.yml 中的 environment：
#    取消注释 COMIC_SHELF_SECRET: '你的管理密码'
#    若为纯内网家庭环境，无需任何修改！

# 2. 一键构建并启动
docker compose up -d --build

# 3. 浏览器访问
# 打开 http://<你的NAS或服务器IP>:8000
```

Compose 会同时拉起纸间核心服务（`:8000`）与本地识图引擎 `imsearch`（`:8765`）。

### 方式 B：TrueNAS Scale / 群晖 Web 界面 / Docker CLI 单容器运行

```bash
# 1. 构建镜像（若直接拉取镜像则跳过）
docker build -t paper-room .

# 2. 运行单容器（通过 -e 注入环境变量，通过 -v 映射数据卷）
docker run -d \
  --name paper-room \
  -p 8000:8000 \
  -v /mnt/tank/comics:/app/data \
  -e COMIC_SHELF_SECRET="your_curator_password" \
  --restart unless-stopped \
  paper-room
```

> **TrueNAS Scale / 群晖等 Web 界面配置指引**：
>
> - **端口映射**：宿主机端口（如 `8000`） $\rightarrow$ 容器内部端口 `8000`
> - **存储卷挂载**：宿主机真实路径（如 `/mnt/tank/paper-room`） $\rightarrow$ 容器内部路径 **`/app/data`**
> - **环境变量设置**：在表单的“环境变量”卡片中添加名称 `COMIC_SHELF_SECRET`，值为你的访问密码。

---

## 3. 环境变量参数配置字典

> **关于环境变量注入**：
>
> - Docker 容器部署**完全不需要** `.env` 文件（`.env` 也不会提交到代码仓库）。
> - 你可以通过以下任一标准方式配置环境变量：
>   1. **Docker Compose**：直接在 `docker-compose.yml` 的 `environment` 节修改或取消注释；
>   2. **NAS Web 图形界面（TrueNAS / 群晖 / Portainer）**：在应用的“环境变量”设置表单中填入 Key 与 Value；
>   3. **Docker 命令行**：启动时增加 `-e KEY="value"` 参数；
>   4. （可选）本地开发或习惯使用 dotenv 的用户，可参考根目录 [`.env.example`](file:///home/miku/lhvision/comic-shelf/.env.example) 模版查阅参数说明。

### 3.1 核心权限与安全配置（必看）

| 环境变量                                | 必填等级                     | 默认值   | 说明                                                                                                                                                                                                                                  |
| :-------------------------------------- | :--------------------------- | :------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `COMIC_SHELF_SECRET`                    | 🔴 **公网必设** / 内网免密   | _(留空)_ | **馆长访问口令**。留空则为局域网免密模式；公网或多用户部署强烈建议设置。输入此口令后获得全站收录、编辑元数据、删除、全量缓存等全部读写管理权限。                                                                                      |
| `COMIC_SHELF_ALLOWED_DIRS`              | 🔵 **直扫NAS外部目录时必设** | _(留空)_ | **允许从服务器本地路径扫描导入的额外根目录白名单**（安全沙箱放行）。用于将 NAS 现有图库目录或挂载盘快速录入纸间。多个路径在 Linux/macOS 使用冒号 `:` 分隔，Windows 使用分号 `;` 分隔（例：`/mnt/tank/comics:/mnt/media/downloads`）。 |
| `COMIC_SHELF_GUEST_SECRET`              | ⚪ **可选**                  | _(留空)_ | **访客阅览口令**（可选）。设置后允许朋友输入此口令只读看书，未提供有效口令者 100% 拦截（HTTP 401）；界面自动隐藏所有写操作控件。留空则仅馆长可访问。                                                                                  |
| `COMIC_SHELF_ENABLE_HOTLINK_PROTECTION` | ⚪ **默认已开启**            | `true`   | **图片防盗链保护**。基于现代浏览器 `Sec-Fetch-Site: cross-site` 与 `Referer` 拦截，彻底杜绝外站把纸间当图床跨站盗图。                                                                                                                 |

### 3.2 基础服务与持久化配置

| 环境变量                   | 默认值                  | 说明                                                                                              |
| :------------------------- | :---------------------- | :------------------------------------------------------------------------------------------------ |
| `COMIC_SHELF_DATA`         | `backend/data`          | 数据根目录。Docker 容器内固定为 `/app/data`。所有已下载漫画、封面、元数据与索引均保存在此目录下。 |
| `COMIC_SHELF_HOST`         | `127.0.0.1`             | 服务绑定地址。Docker 容器内已配置为 `0.0.0.0`。                                                   |
| `COMIC_SHELF_PORT`         | `8000`                  | 服务监听端口。可在 Compose 中将宿主机端口任意映射（如 `8080:8000`）。                             |
| `COMIC_SHELF_IMSEARCH_URL` | `http://localhost:8765` | 局部特征识图 Sidecar 服务地址。Docker Compose 内部网络已配置为 `http://imsearch:8765`。           |
| `COMIC_SHELF_ENABLE_DOCS`  | `false`                 | 是否开放 FastAPI 交互式 API 文档页面（`/docs` 与 `/redoc`）。公网环境建议保持 `false`。           |

### 3.3 性能调优与并发控制（低配 NAS / 进阶调优）

| 环境变量                               | 默认值 | 说明                                                                                                                                                          |
| :------------------------------------- | :----- | :------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `COMIC_SHELF_MAX_CONCURRENT_DOWNLOADS` | `3`    | **远端图片下载并发数**。JM 官方 CDN 对高并发极为敏感，建议维持在 `2`~`4`，避免触发风控或请求超时。                                                            |
| `COMIC_SHELF_THUMB_CONCURRENCY`        | `4`    | **缩略图处理并发门禁**。限制同时进行 Pillow 转换的 CPU worker 线程数。在单核/双核低配 NAS（如 J1900、ARM 盒子）上建议设为 `1` 或 `2`，防止冷访问时 CPU 跑满。 |
| `COMIC_SHELF_MAX_PREFETCH`             | `600`  | 单次点击“缓存全部”允许下载的单本最大页数上限，保护磁盘与网络。                                                                                                |
| `COMIC_SHELF_PAGE_THUMB_WIDTH`         | `360`  | 详情页与子章节网格缩略图宽度（px）。                                                                                                                          |
| `COMIC_SHELF_PAGE_THUMB_QUALITY`       | `78`   | 缩略图 JPEG 压缩质量（兼顾清晰度与微秒级传输）。                                                                                                              |
| `COMIC_SHELF_COVER_WIDTH`              | `840`  | 书架与详情页大封面宽度（px）。                                                                                                                                |
| `COMIC_SHELF_COVER_QUALITY`            | `82`   | 大封面 JPEG 质量。                                                                                                                                            |
| `COMIC_SHELF_COVER_COUNT`              | `4`    | 每本漫画默认生成的封面预览张数。                                                                                                                              |
| `COMIC_SHELF_WORKERS`                  | `1`    | Uvicorn 工作进程数。多核服务器可适当调大。                                                                                                                    |
| `COMIC_SHELF_LOG_LEVEL`                | `info` | 后端运行日志级别（可选 `debug`, `info`, `warning`, `error`）。                                                                                                |

---

## 4. 部署后如何触发以图搜图索引（`reindex:image`）

纸间的以图搜图基于二次元局部 ORB 特征与倒排索引。为了防止频繁收录漫画导致服务器 CPU 持续高载，纸间采用**智能异步增量机制**：收录漫画时不会阻塞重构索引，由管理员在批量导入后按需触发。

### 4.1 核心机制：增量追加 vs 全量重训

- **日常增量追加（默认行为，推荐，耗时数秒）**：
  仅扫描新缓存的图片并提取 ORB 特征，随后直接追加至已有倒排索引。**旧图片特征与聚类模型 100% 复用，零重复计算**。
- **全量重置重训（初次初始化或聚类重训）**：
  重新运行 K-Means 聚类训练（512 聚类中心）并重建整库倒排索引。仅在特征库损坏或首次初始化时需要。

### 4.2 方式一：Docker Compose 容器内一键触发（最常用）

无需在宿主机安装 Rust 或任何依赖，直接在终端执行：

```bash
# 【推荐】日常增量追加（导入新本子后执行，秒级完成）：
docker compose exec imsearch sh -c "imsearch add /app/data/library && imsearch build"
docker compose restart imsearch

# 【全量重置】全量重训聚类中心并重建索引（首次或重构时使用）：
docker compose exec imsearch sh -c "imsearch add /app/data/library && imsearch train -c 512 -i 800 -m 30 && rm -f /root/.config/imsearch/invlists.bin && imsearch build"
docker compose restart imsearch
```

> **提示**：索引完成后执行 `docker compose restart imsearch` 可确保搜图服务立即热加载最新的索引文件。

### 4.3 方式二：宿主机一键脚本智能转发

如果你保留了源码目录，可以直接在项目根目录下执行：

```bash
# 日常增量构建
pnpm reindex:image
# 或直接运行
bash scripts/reindex.sh

# 强制全量重训
bash scripts/reindex.sh --full
```

`scripts/reindex.sh` 具备**环境自适应探测**：若宿主机未安装 `imsearch`，脚本会自动检测运行中的 Docker Compose 识图容器并自动将命令代理至容器内执行，体验与本地完全一致。

### 4.4 方式三：NAS / Linux Crontab 定时任务自动化（可选）

如果希望全自动维护搜图索引，可以在 NAS 或 Linux 服务器的 crontab 中加入定时增量追加任务（例如每周日凌晨 3 点自动追加）：

```bash
0 3 * * 0 cd /path/to/comic-shelf && docker compose exec -T imsearch sh -c "imsearch add /app/data/library && imsearch build" && docker compose restart imsearch >/dev/null 2>&1
```

---

## 5. 数据持久化与备份迁移

所有漫画元数据、图片和搜图特征库统一存放在数据目录（`COMIC_SHELF_DATA`，容器内为 `/app/data`）：

```text
backend/data/
├── jm_html_domain.json          # 禁漫可用域名缓存
├── imsearch/                   # 以图搜图特征库与倒排索引
│   ├── centroids.bin           # 聚类量化器模型
│   ├── invlists.bin            # 倒排索引
│   └── imsearch.db             # 向量数据库
└── library/                    # 漫画资源库
    ├── jm/523607/              # 禁漫作品目录
    │   ├── album.json          # 元数据与全局页码映射
    │   ├── remote.json         # 远端分块与解密状态
    │   ├── covers/             # 封面 JPEG
    │   ├── pages/              # 已解密的高清成品页面 (WebP)
    │   └── thumbs/             # 360px 索引缩略图
    └── local/                  # 本地自建图集 / 视频拆帧
```

- **零依赖单点备份**：备份或迁移时，**只需复制整个 `backend/data/` 目录**。
- **跨平台兼容**：元数据采用向前兼容的 JSON 结构，无外部重型数据库锁，直接复制粘贴即可在其他设备完美还原。

---

## 6. 镜像体积与构建控制

纸间采用 **多阶段构建（Multi-stage Build）** 严格控制生产镜像体积：

- **Node.js 编译阶段（打包后完全丢弃）**：使用轻量 `node:22-alpine` 仅执行前端构建（`pnpm build`），**Node.js、pnpm 及庞大的 `node_modules` 均不会打包进最终镜像**。
- **最终生产镜像**：仅基于官方精简镜像 `python:3.12-slim`，安装纯 Python 运行时依赖，附带约 2MB 的前端静态成品，镜像极小、拉取速度极快。

---

## 7. 多用户高并发建议（Nginx / Caddy 反向代理）

在多访客（如 20+ 人）局域网或公网部署场景下，建议在前置增加 Nginx 或 Caddy 反向代理：

1. **启用 HTTP/2 / HTTP/3**：开启 HTTP/2 多路复用，彻底解除浏览器同域名 6 个并发连接排队的瓶颈。
2. **利用静态强缓存**：纸间后端图片与缩略图响应均内置了 `Cache-Control: public, max-age=2592000, immutable`（30 天强缓存），客户端二次加载 100% 命中浏览器本地缓存，0 服务端负载。
3. **冷缓存预热**：导入漫画时勾选“缓存全部”，后台会自动完成解密与缩略图预生成，避免多访客同时翻阅未缓存作品时触发实时下载与动态缩放。

---

## 8. 和 Vite+ / vp 的关系说明

仓库已全面迁移至 Vite+：

- `package.json` 使用 `vite-plus` 与 `vite` override；
- `Dockerfile` 构建阶段直接使用 `pnpm build` 调用本地打包器；
- Docker 部署环境无需额外安装 `vp` CLI。
