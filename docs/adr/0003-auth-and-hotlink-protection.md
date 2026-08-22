# ADR 0003 — 渐进式单口令访问门禁与现代防盗链安全机制

- **日期**：2026-08-22
- **状态**：Accepted

## 背景

纸间定位于「本地优先的个人漫画收藏夹」。用户常将其部署在家庭 NAS、私有 VPS 或通过 Cloudflare Tunnel / FRP 等内网穿透工具暴露于公网，以便在手机、平板上随时阅览。

在无保护暴露于公网时存在两类核心安全隐患：

1. **未授权 API 与操作风险**：第三方可调用 `/api/library` 泄露元数据，或调用 `/import`、`/cache` 恶意刷流量、调用 `DELETE` 删库。
2. **图片资源被盗链与存储桶滥用**：外部网页可通过 `<img src="https://纸间地址/api/library/.../file">` 将纸间当作免费图床/存储桶直连读取解密成品图，耗尽服务器带宽。

## 决策

1. **渐进式单访问密钥（Zero-Friction Single Secret）**：
   - 采用环境变量 `COMIC_SHELF_SECRET`（或 `COMIC_SHELF_AUTH_TOKEN`）控制门禁开关：
     - **未配置（默认）**：保持 100% 零门槛免密状态，局域网与单机开发即开即用。
     - **配置后**：全站启用访问保护。未授权请求拦截 401 并唤起私人阅览室通行口令输入卡片。
   - 验证链路采用 **双轨凭证（Cookie + Bearer Header）**：
     - 用户输入口令后，后端下发 `SameSite=Lax; HttpOnly` 的 Session Cookie 并返回 Token 写入本地存储。
     - 前端 fetch 自动附带 `Authorization: Bearer` 头；原生 `<img>` 标签自动携带 `SameSite` Cookie，无需额外签名改造。

2. **现代浏览器级防盗链与防滥用（Sec-Fetch-Site + Referer 联动）**：
   - 图片资源端点（`/pages/.../file`、`/thumbnail`、`/covers/.../file`、`/chapters/.../cover`）强制进行跨站防盗链校验：
     - **`Sec-Fetch-Site: cross-site` 拦截**：现代浏览器跨域引用直接返回 403 Forbidden。
     - **`Referer` 白名单校验**：校验来源 Host 是否与当前服务一致或属于本地开发端口，拦截非法外站盗链。

3. **依赖与启动流程自愈优化**：
   - 启动脚本 `scripts/dev.sh` 与 `package.json` 的 Python 探测调整为：优先 `.venv/bin/python`（项目内）→ `../.venv/bin/python`（共享上级）→ 系统 `python3`。
   - 提供 `pnpm setup:py` 一键初始化本地虚拟环境并安装依赖。
   - `scripts/dev.sh` 开发环境默认注入 `--reload`，改动后端代码无需重启服务。

## 后果

- **安全性**：公网部署时可 100% 杜绝未授权访问、恶意调用与第三方图片盗链。
- **用户体验**：内网用户完全无感；公网用户仅需在初次进入时输入一次口令即可长效记忆，UI 风格严格遵从私人阅览室设计语言。
- **无破坏性改动**：不改变现有 URL 结构与已缓存的本地 `album.json` / `pages` 文件布局。

## 备选方案对比

- **OAuth 2.0 / 复杂用户体系**：过度工程化，纸间为个人单用户收藏夹，单密码凭证已足够且轻量。
- **短效 HMAC 签名 URL（`?token=...`）**：每次生成/分发 URL 需引入签名计算，破坏了浏览器 `Cache-Control: immutable` 缓存复用效率并增加前端模板解析负担。
