# syntax=docker/dockerfile:1
# ---- Stage 1: Build Vue 3 Frontend (Official Vite+ Toolchain) ----
# 使用 VoidZero 官方 Vite+ 工具链镜像（预置 vp CLI，自动按 devEngines 调度 pnpm 12 与 Node.js）
FROM ghcr.io/voidzero-dev/vite-plus:latest AS frontend-builder
ENV PUPPETEER_SKIP_DOWNLOAD=true \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

WORKDIR /app

# 优先复制依赖定义与配置，充分利用 Docker 缓存层与 pnpm 依赖缓存
COPY --chown=vp:vp package.json pnpm-lock.yaml pnpm-workspace.yaml .node-version* .npmrc* ./
RUN --mount=type=cache,id=paper-room-pnpm-store,target=/home/vp/.local/share/pnpm/store,uid=1000,gid=1000 \
    vp install --frozen-lockfile

# 仅复制前端构建相关源码，避免后端变动破坏前端构建缓存
COPY --chown=vp:vp src ./src
COPY --chown=vp:vp public ./public
COPY --chown=vp:vp plugins ./plugins
COPY --chown=vp:vp index.html vite.config.ts tsconfig*.json env.d.ts ./
RUN vp build

# ---- Stage 2: Python Backend Runtime with Static SPA ----
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    COMIC_SHELF_DATA=/app/data \
    COMIC_SHELF_HOST=0.0.0.0 \
    COMIC_SHELF_PORT=8000 \
    COMIC_SHELF_STATIC_DIR=/app/dist

WORKDIR /app

RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources; fi \
    && if [ -f /etc/apt/sources.list ]; then sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list; fi \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY backend/app ./app
COPY backend/server.py ./
COPY --from=frontend-builder /app/dist ./dist

VOLUME ["/app/data"]
EXPOSE 8000

CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8000"]
