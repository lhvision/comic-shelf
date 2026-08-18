# ---- build frontend (Vite+ toolchain) ---------------------------------
# node:24-alpine keeps the build stage small. vite-plus provides musl builds;
# it only needs libstdc++ on Alpine (per Vite+ install docs).
FROM node:24-alpine AS build
RUN apk add --no-cache libstdc++ \
    && npm install -g pnpm@11.22.0

WORKDIR /app

# package.json devEngines pins pnpm 11.22.0; install that before `pnpm install`.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

# ---- serve SPA ---------------------------------------------------------
# alpine-slim keeps the FINAL image small. dist is only ~2 MB.
FROM nginx:1.27-alpine-slim
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
