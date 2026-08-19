# 纸间部署规划（Docker）

当前项目：Vite+（Vite 8 / vite-plus 0.2.9）+ Vue 3 SPA + FastAPI + jmcomic。
项目已完成 `vp migrate`，Docker 前端镜像也按 pnpm 11 + vite-plus 本地 bin 构建。
这个组合可以直接容器化，不需要迁移 Nuxt。

## 推荐部署形态

```text
Browser
  │ :8080
  ▼
nginx (frontend container)
  ├── /            → Vue dist 静态文件
  └── /api/*       → FastAPI backend:8000
                       │
                       ▼
                  ./backend/data volume（本地漫画缓存）
```

- 前端：nginx 提供静态文件 + `/api` 反向代理。
  构建阶段用 `node:24-alpine + libstdc++`，最终镜像用 `nginx:1.27-alpine-slim`；
  构建层不会进入最终镜像，最终只包含 nginx + dist。
- 后端：FastAPI 进程，数据目录挂载到宿主机 `backend/data`，删除容器不丢漫画。
  后端使用 `python:3.12-slim` 而不是 alpine，因为 jmcomic 依赖的
  curl-cffi / Pillow / pycryptodome 在 glibc 下更可靠。
- 为什么不用 Nuxt：这是私人本地工具，没有 SEO/首屏 SSR 需求；SPA + API 更简单，
  出问题也更好排查。后端必须保留 Python/FastAPI，因为 jmcomic 是 Python 库。

## 启动

```bash
cd /home/miku/dsh/comic-shelf

# 构建并启动
docker compose up -d --build

# 查看状态
docker compose ps

# 日志
docker compose logs -f backend
docker compose logs -f frontend
```

打开：

```text
http://127.0.0.1:8080
```

## 持久化

容器重建后仍保留：

```text
backend/data/
├── jm_html_domain.json
└── library/
    ├── jm/523607/
    │   └── pages/<chapter>/…   # 多章节作品页面在章节子目录
    └── ...
```

备份 / 迁移只需复制整个 `backend/data/`。多章节与单章节共享同一份
`album.json` / `remote.json`，结构向前兼容，无需额外迁移。

## 环境变量

| 变量                           | 默认值         | 说明                 |
| ------------------------------ | -------------- | -------------------- |
| `COMIC_SHELF_DATA`             | `backend/data` | 数据目录             |
| `COMIC_SHELF_PAGE_THUMB_WIDTH` | `360`          | 页面索引缩略图宽度   |
| `COMIC_SHELF_COVER_WIDTH`      | `840`          | 封面宽度             |
| `COMIC_SHELF_MAX_PREFETCH`     | `600`          | 单次全量缓存页数上限 |

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
