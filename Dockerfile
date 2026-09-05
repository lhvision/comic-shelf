# syntax=docker/dockerfile:1
# ---- Stage 1: Build Vue 3 Frontend (Vite+) ----
# 使用轻量级 Node 22 Alpine 作为构建环境（编译完成后会被完全丢弃，不进最终镜像）
FROM node:22-alpine AS frontend-builder
ENV PUPPETEER_SKIP_DOWNLOAD=true \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.ustc.edu.cn/g' /etc/apk/repositories \
    && apk add --no-cache libstdc++ \
    && npm install -g pnpm@11.25.0 --registry=https://registry.npmmirror.com \
    && pnpm config set store-dir /root/.pnpm-store

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc* ./
RUN --mount=type=cache,id=paper-room-pnpm,target=/root/.pnpm-store \
    pnpm install --frozen-lockfile --ignore-scripts

COPY src ./src
COPY public ./public
COPY plugins ./plugins
COPY index.html vite.config.ts tsconfig*.json env.d.ts ./
RUN pnpm run build-only

# ---- Stage 2: Python Backend Runtime with Static SPA ----
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    COMIC_SHELF_DATA=/app/data \
    COMIC_SHELF_HOST=0.0.0.0 \
    COMIC_SHELF_PORT=8000 \
    COMIC_SHELF_STATIC_DIR=/app/dist

WORKDIR /app

COPY backend/requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY backend/app ./app
COPY backend/server.py ./
COPY --from=frontend-builder /app/dist ./dist

VOLUME ["/app/data"]
EXPOSE 8000

CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8000"]
