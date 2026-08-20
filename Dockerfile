# ---- Stage 1: Build Vue 3 Frontend (Vite+) ----
# 使用轻量级 Node 22 Alpine 作为构建环境（编译完成后会被完全丢弃，不进最终镜像）
FROM node:22-alpine AS frontend-builder
RUN apk add --no-cache libstdc++ \
    && npm install -g pnpm@11.22.0

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

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
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/server.py ./
COPY --from=frontend-builder /app/dist ./dist

VOLUME ["/app/data"]
EXPOSE 8000

CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8000"]
