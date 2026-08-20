# 工具链、部署与排错（详细规则）

## 8.5 Vite+ / vp 与 Docker

- 项目**已完成 `vp migrate`**：`vite.config.ts` 从 `vite-plus` 导入，
  `vite` 通过 `pnpm-workspace.yaml` 的 catalog 指向 `@voidzero-dev/vite-plus-core`。
- `package.json` 的 `devEngines` 固定 pnpm 11.22.0；开发机用 `vp` 管理 Node/pnpm。
- 本地 `node_modules/.bin` 有 `vp`，`pnpm run dev/build` 与 `vp dev/build` 等价。
- 日常命令：`vp install / dev / check / test / build / preview`。
- 已提供统一单容器部署：`Dockerfile`、`docker-compose.yml`，说明见 `DEPLOYMENT.md`。
- 不建议迁 Nuxt：私人本地工具无 SEO/SSR 需求，SPA + FastAPI 单容器更简单；
  Python 后端必须保留（jmcomic 是 Python 库）。

## 9. 常用命令

```bash
cd /home/miku/dsh/comic-shelf
./scripts/dev.sh                         # 同时起 API + Web
../.venv/bin/python backend/server.py    # 只起 API
vp dev                                   # 只起 Web（Vite+ dev server）
vp check                                 # fmt + lint + type-check
vp test                                  # Vitest
vp build                                 # 生产构建
```

## 10. 修 bug 时的建议顺序

1. 先检查 `backend/data/library/<source>/<id>/remote.json` 的 `decode_version`；
2. 检查页面文件是否成品图（用 `JmImageTool.get_num_by_url()` 验证 num）；
3. 阅读器问题先确认 `data-mode` 是否同时加在 `.reader-view` 和 `.reader-scroll`；
4. 页面定位问题先确认 `loading=false → await nextTick() → scrollTo` 顺序；
5. UI 改动必须回看 `DESIGN_NOTES.md`，不要引入紫色渐变 / 第三方轮播。
