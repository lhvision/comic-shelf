# 纸间部署规划（Docker & TrueNAS / NAS）

当前项目：Vite+（Vite 8 / vite-plus）+ Vue 3 SPA + FastAPI + jmcomic。

支持 **All-in-One 单容器一键部署**（无需 Nginx，前后端由 FastAPI 统一在单个端口托管），非常适合 **TrueNAS Scale / Unraid / 群晖 NAS / 标准 Docker** 环境。

## 1. 推荐部署形态（All-in-One 单容器，免 Nginx）

```text
Browser
  │ :8000
  ▼
Paper Room (Single Container)
  ├── /            → Vue 3 SPA 静态页面 (dist)
  ├── /api/*       → FastAPI 后端接口
  └── /app/data    → 持久化数据目录（本地漫画缓存、元数据）
```

- **单容器、单端口**：单个 Docker 容器直接运行 FastAPI + 静态前端，省去配置 Nginx 反向代理和双容器网络的复杂性。
- **TrueNAS / NAS 友好**：只需映射一个端口（8000）和一个持久化卷（`/app/data`）。
- **极速响应**：多级内存元数据缓存 + 本地已缓存文件零锁直通 + HTTP Immutable 缓存头。

## 2. 启动方式

### 方式 A：Docker Compose 一键启动（含以图搜图 Sidecar）

```bash
docker compose up -d --build
# 浏览器打开 http://127.0.0.1:8000
```

Compose 会同时拉起纸间服务（`:8000`）与基于 ORB 特征检索的本地识图容器 `imsearch`（`:8765`）。

### 方式 B：TrueNAS Scale / Docker CLI 单容器运行

```bash
# 构建镜像
docker build -t paper-room .

# 运行容器
docker run -d \
  --name paper-room \
  -p 8000:8000 \
  -v /mnt/tank/comics:/app/data \
  --restart unless-stopped \
  paper-room
```

## 镜像体积与构建控制

纸间采用 **多阶段构建（Multi-stage Build）** 控制镜像体积：

- **Node 编译阶段（丢弃）**：使用超轻量 `node:22-alpine` 仅用于执行前端打包（`pnpm build`），**Node.js、pnpm 及庞大的 `node_modules` 均不会打包进最终镜像**。
- **最终运行镜像**：仅基于 `python:3.12-slim` + pip 无缓存依赖 + 约 2MB 的静态页面成品（`dist`），镜像小巧干净，NAS 拉取与部署极为轻快。

## 持久化

容器重建后仍保留：

```text
backend/data/
├── jm_html_domain.json
├── imsearch/                   # 识图索引与特征库（若启用 imsearch）
└── library/
    ├── jm/523607/
    │   └── pages/<chapter>/…   # 多章节作品页面在章节子目录
    └── ...
```

备份 / 迁移只需复制整个 `backend/data/`。多章节与单章节共享同一份
`album.json` / `remote.json`，结构向前兼容，无需额外迁移。

## 环境变量

| 变量                                    | 默认值                  | 说明                                                                               |
| --------------------------------------- | ----------------------- | ---------------------------------------------------------------------------------- |
| `COMIC_SHELF_DATA`                      | `backend/data`          | 数据目录                                                                           |
| `COMIC_SHELF_SECRET`                    | _(留空)_                | 馆长访问口令（留空免密；设置后全站启用门禁保护，输入此口令获得全部读写管理权限）   |
| `COMIC_SHELF_GUEST_SECRET`              | _(留空)_                | 访客阅览口令（可选；设置后允许朋友输入此口令只读看书，未提供有效口令者 100% 拦截） |
| `COMIC_SHELF_ALLOWED_DIRS`              | _(留空)_                | 允许从服务器本地路径扫描导入的额外根目录白名单（多个路径用系统路径分隔符分隔）     |
| `COMIC_SHELF_ENABLE_HOTLINK_PROTECTION` | `true`                  | 是否启用基于 Sec-Fetch-Site 与 Referer 的图片防盗链拦截                            |
| `COMIC_SHELF_ENABLE_DOCS`               | `false`                 | 是否开放 /docs 和 /redoc API 文档                                                  |
| `COMIC_SHELF_IMSEARCH_URL`              | `http://localhost:8765` | 局部特征识图服务地址（可选）                                                       |
| `COMIC_SHELF_PAGE_THUMB_WIDTH`          | `360`                   | 页面索引缩略图宽度                                                                 |
| `COMIC_SHELF_COVER_WIDTH`               | `840`                   | 封面宽度                                                                           |
| `COMIC_SHELF_MAX_PREFETCH`              | `600`                   | 单次全量缓存页数上限                                                               |
| `COMIC_SHELF_MAX_CONCURRENT_DOWNLOADS`  | `3`                     | 下载并发数限制                                                                     |

## 和 Vite+ / vp 的关系

仓库已经执行过 `vp migrate`：

- `package.json` 使用 `vite-plus` 与 `vite` override；
- `pnpm build` 实际调用本地 `node_modules/.bin/vp build`；
- Docker 前端镜像会先安装 `pnpm@11.22.0` 以匹配 `devEngines`，再执行
  `pnpm install --frozen-lockfile && pnpm build`，不需要全局安装 vp。

## 如果以后真要上 Nuxt

建议只在出现以下需求时再迁移：

- 需要公开访问和 SEO；
- 需要服务端渲染首屏；
- 希望把一部分 API 逻辑写成 Nuxt server routes。

迁移方式：

1. 保留 `backend/app` 的 FastAPI 与 provider 层；
2. 把 `src/views`、`src/components` 迁移为 Nuxt `pages/`、`components/`；
3. `api/client.ts` 的 `/api` base 在 Nuxt 下继续指向 FastAPI；
4. Docker 里的 Nuxt node server 替代 nginx 静态托管，`/api` 继续反代或直连 FastAPI。

当前阶段不建议迁移：收益不大，还会增加 SSR 内存和部署复杂度。
