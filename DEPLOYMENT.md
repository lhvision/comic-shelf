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
│ 3. 其余 20 个环境变量：                                                         │
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

### 方式 A：Docker Compose 双容器启动（含以图搜图，需 CPU 支持 AVX2）

适合主流 x86 电脑、工作站或配备支持 AVX2 指令集处理器的服务器：

```bash
# 1. （可选）若公网部署需设置密码或自定义参数，推荐复制配置模版：
#    方式一（推荐，与 Git 彻底物理隔离）：cp .env.example backend/data/.env
#    方式二（Compose 宿主机根目录注入，由 Compose 运行时读取环境变量，不打入镜像）：cp .env.example .env
#    然后按需编辑 .env（如设置 COMIC_SHELF_SECRET）；纯内网家庭环境无需任何修改！

# 2. 一键构建并启动双容器（包含主服务与识图 Sidecar）
docker compose up -d --build

# 3. 浏览器访问
# 打开 http://<你的NAS或服务器IP>:8000
```

Compose 会同时拉起纸间核心服务（`:8000`）与本地识图引擎 `imsearch`（容器间内部互通，宿主机仅绑定 `127.0.0.1:8765` 防范公网扫描）。

### 方式 B：极简单容器启动（推荐低功耗 NAS / 低配 VPS / 免以图搜图）

> 💡 **低功耗 CPU 避坑指引（AVX2 兼容性）**：
> Intel 赛扬 N5095 / N5105 / N5050 / J4105 / J1900 等低功耗架构在硬件底层**不支持 AVX2 向量指令集**。若拉起 `imsearch` 识图容器会报 `SIGILL (Exit 132)` 核心转储（Core Dump）并陷入无限重启。
> 纸间主服务完美适配全系列低功耗 CPU，且内置全自动优雅降级。只需单独启动 `paper-room`：

```bash
# 单独启动主容器（务必加上 --no-deps 忽略 depends_on 依赖，确保绝不拉起 imsearch）：
docker compose up -d --no-deps --build paper-room
```

### 方式 C：TrueNAS Scale / 群晖 Web 界面 / Docker CLI 单容器运行

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

### 2.1 常用启停与容器运维命令速查

| 场景需求                   | 终端执行命令                                                       | 说明                                                                                      |
| :------------------------- | :----------------------------------------------------------------- | :---------------------------------------------------------------------------------------- |
| **仅启动主容器（免搜图）** | `docker compose up -d --no-deps paper-room`                        | **加 `--no-deps` 忽略依赖**，不拉起 imsearch，防 132 报错                                 |
| **启动全部容器**           | `docker compose up -d`                                             | 适用于带 AVX2 机器，同时拉起主程序与以图搜图                                              |
| **安全停止全部服务**       | `docker compose down`                                              | 停止并移除容器与内部网络，存储卷数据 100% 安全保留                                        |
| **暂停容器运行**           | `docker compose stop`                                              | 仅暂停容器不删除，后续 `docker compose start` 可秒级恢复                                  |
| **单独停掉以图搜图**       | `docker compose stop imsearch`                                     | 解决由于硬件缺少 AVX2 导致容器反复崩溃报错 132 的问题                                     |
| **查看运行状态**           | `docker compose ps`                                                | 查看容器状态（`Up` 为正常运行）                                                           |
| **代码更新后重启（推荐）** | `docker compose up -d --build paper-room && docker image prune -f` | 自动命中缓存秒级重构平滑重启，并顺手修剪失去标签的旧镜像（`<none>:<none>`），杜绝磁盘累积 |
| **释放旧镜像与构建缓存**   | `docker image prune -f && docker builder prune -f`                 | 安全清理悬挂镜像与前端/Python 中间构建缓存（绝不影响运行中的容器与持久化数据）            |

> 💡 **运维避坑：为什么多次构建后 `docker images` 会看到很多 `<none>:<none>` 镜像？**
>
> 每次执行 `docker compose up -d --build` 时，若代码有变更，Docker 会生成全新 Image ID 的镜像并赋予最新标签（`paper-room:latest`）。
> 上一次构建的旧镜像因此失去了 Tag 引用，沦为 **悬挂镜像（Dangling Image）**。Docker 默认不会主动删除它们以备回滚，频繁更新便会逐渐堆积。
>
> - **安全一键清理悬挂镜像**：`docker image prune -f`（只删 `<none>` 孤儿镜像，正在运行的服务与其他带 Tag 镜像 100% 安全）。
> - **释放多阶段编译缓存**：`docker builder prune -f`（清理 BuildKit 中间构建缓存，常可腾出数 GB 空间）。
> - **解除废弃容器占用锁定**：若提示个别 `<none>` 镜像无法删除，说明存在历史调试残留的“已停止容器”正引用着它们，先执行 `docker container prune -f` 移除废弃容器即可解开锁定。
> - **零负担平滑更新**：日常更新代码直接使用 `docker compose up -d --build paper-room && docker image prune -f` 即可一步到位。
> - **版本回滚哲学**：纸间以 Git 为唯一版本真理源。若新版需回滚，只需在仓库执行 `git checkout <旧commit> && docker compose up -d --build paper-room` 即可依靠内置 BuildKit 物理缓存 2~3 秒内极速重构旧版本，无需在 Docker 层常驻陈旧镜像浪费存储。
> - **（进阶可选）NAS / Linux 无人值守月度自动瘦身**：若希望服务器长期运行无需人工干预，可在宿主机 `crontab -e` 或群晖/TrueNAS 任务计划中加入一行月度轻量修剪（每月 1 号凌晨 4 点静默执行）：
>   ```bash
>   0 4 1 * * docker image prune -f >/dev/null 2>&1
>   ```

---

## 3. 环境变量参数配置字典

> **关于环境变量注入与配置持久化**：
>
> 纸间采用**双轨级联配置（Dual-Track Cascade）**，彻底实现「代码拉取升级」与「部署参数」物理隔离：
>
> 1. **持久化数据卷配置（最推荐，升级绝对零冲突）**：直接在挂载的数据目录中放置 `.env`（宿主机为 `./backend/data/.env`，容器内映射为 `/app/data/.env`），后续 `git pull` 升级代码永不冲突；
> 2. **Docker Compose 根目录配置**：在项目根目录复制 `cp .env.example .env`，Compose 启动容器时自动通过 `env_file` 注入环境变量（注意：`.env` 已被 `.dockerignore` 隔离，确保敏感凭据不被打进镜像层，仅作为宿主机运行时注入）；
> 3. **NAS Web 图形界面（TrueNAS / 群晖 / Portainer）**：在应用的“环境变量”设置表单中填入 Key 与 Value；
> 4. **Docker 命令行**：启动时增加 `-e KEY="value"` 参数；
> 5. **覆盖优先级**：系统环境变量（`-e` / Compose `environment:`） > 根目录 `.env` > 数据卷 `/app/data/.env` > 内置开箱默认值。
>    详细参数说明与模板参见根目录 [`.env.example`](.env.example)。

### 3.1 核心权限与安全配置（必看）

| 环境变量                                | 必填等级                     | 默认值                                        | 说明                                                                                                                                                                                                                                                                                                                                                                     |
| :-------------------------------------- | :--------------------------- | :-------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `COMIC_SHELF_SECRET`                    | 🔴 **公网必设** / 内网免密   | _(留空)_                                      | **馆长访问口令**。留空则为局域网免密模式；公网或多用户部署强烈建议设置。输入此口令后获得全站收录、编辑元数据、删除、全量缓存等全部读写管理权限。                                                                                                                                                                                                                         |
| `COMIC_SHELF_MACHINE_TOKEN`             | ⚪ **局域网应用/Bot可选**    | _(留空)_                                      | **内网机器与自动化专用密钥 (Machine API Token)**。供局域网内其他应用（飞书 Bot、Paper Studio、微服务等）通过 `X-Machine-Token` 或 Bearer Token 调用 REST API 建本及上传画页，与网页端馆长密码完全解耦互不干扰。这把密钥**不能开 MCP**（MCP 只认馆长口令与 `COMIC_SHELF_MCP_TOKEN`）。                                                                                    |
| `COMIC_SHELF_MCP_TOKEN`                 | ⚪ **接外部智能体时建议设**  | _(留空)_                                      | **MCP 子凭据**：只解锁 `/api/mcp` 与 MCP 工具，交给 Claude/Cursor/Bot 后可随时换掉，不牵连站长登录与机器密钥的 REST API 调用。不设时 MCP 只认馆长口令。MCP 工具仍是馆长级可见（含对访客隐藏的本），但 `create_direct_pass` 拒绝为隐藏本签发公开链接。                                                                                                                    |
| `COMIC_SHELF_PUBLIC_URL`                | ⚪ **MCP生成分享外链可选**   | _(留空)_                                      | **公网访问基准地址 (Public Base URL)**。供 MCP 外部智能体签发单本直达链接（Direct Pass）时拼接完整绝对 URL（如 `https://comic.example.com`，末尾斜杠自动清洗）。未配置时默认输出相对路径 `/comic/...`。                                                                                                                                                                  |
| `COMIC_SHELF_ALLOWED_DIRS`              | 🔵 **直扫NAS外部目录时必设** | _(留空)_                                      | **允许从服务器本地路径扫描导入的额外根目录白名单**（安全沙箱放行）。用于将 NAS 现有图库目录或挂载盘快速录入纸间。多个路径在 Linux/macOS 使用冒号 `:` 分隔，Windows 使用分号 `;` 分隔（例：`/mnt/tank/comics:/mnt/media/downloads`）。                                                                                                                                    |
| `COMIC_SHELF_ENABLE_HOTLINK_PROTECTION` | ⚪ **默认已开启**            | `true`                                        | **图片防盗链保护**。基于现代浏览器 `Sec-Fetch-Site: cross-site` 与 `Referer` 拦截，彻底杜绝外站把纸间当图床跨站盗图。                                                                                                                                                                                                                                                    |
| `COMIC_SHELF_TRUST_FORWARDED_HEADERS`   | ⚪ **默认已开启**            | `true`                                        | **反向代理 IP 请求头信任**。控制是否解析 `X-Forwarded-For`、`X-Real-IP` 等请求头确定客户端 IP。经由 Nginx/Cloudflare/Caddy 反代部署时保持 `true`，且公网部署必须配好 [HOMELAB 6.8 回源印章](docs/HOMELAB_NETWORKING_GUIDE.md)，否则能直连源站的人可以伪造这些头，绕过登录与 MCP 的失败锁；若直接将 Uvicorn 裸端口暴露于公网且无前端代理，建议设为 `false` 防范 IP 伪造。 |
| `COMIC_SHELF_EMBED_DIR`                 | ⚪ **装语义检索时可选**      | `<COMIC_SHELF_DATA>/models/bge-small-zh-v1.5` | **台词语义检索的模型目录**（放 `model.onnx` 与 `tokenizer.json`，文件名不变）。目录里没有模型时语义出口返回 `encoder_unavailable`，关键词检索不受影响。安装见 §5.1.2。                                                                                                                                                                                                   |
| `COMIC_SHELF_COOKIE_NAME`               | ⚪ **可选自定义**            | `comic_shelf_token`                           | **通行证 Cookie 键名**。支持自定义 Cookie 名称（如 `my_vault_token`），彻底隐匿开源默认键名，配合 Cloudflare WAF 与单本沙箱 `temp_token` 实现高强度私有免检与零裂图秒开（详见 `docs/HOMELAB_NETWORKING_GUIDE.md` §6.6 与 §6.7）。                                                                                                                                        |
| `COMIC_SHELF_DEVICE_COOKIE_NAME`        | ⚪ **可选自定义**            | `comic_shelf_device`                          | **设备认证 Cookie 键名**。支持自定义设备 Cookie 名称（如 `my_vault_device`），配合 Cloudflare WAF 规则实现免检通行。                                                                                                                                                                                                                                                     |

### 3.2 基础服务与持久化配置（Docker 部署请通过 Compose `volumes` 与 `ports` 管理）

| 环境变量                   | 默认值                  | 说明                                                                                                                                 |
| :------------------------- | :---------------------- | :----------------------------------------------------------------------------------------------------------------------------------- |
| `COMIC_SHELF_DATA`         | `backend/data`          | 数据根目录。Docker 容器内固定为 `/app/data`；Docker 部署时直接在 Compose 的 `volumes` 节映射宿主机路径，无需且切勿在 `.env` 中设置。 |
| `COMIC_SHELF_HOST`         | `127.0.0.1`             | 服务绑定地址。Docker 容器内已固定为 `0.0.0.0`，无需在 `.env` 中设置。                                                                |
| `COMIC_SHELF_PORT`         | `8000`                  | 服务监听端口。Docker 部署时直接在 Compose 的 `ports` 节映射宿主机端口（如 `8080:8000`），无需在 `.env` 中设置。                      |
| `COMIC_SHELF_IMSEARCH_URL` | `http://localhost:8765` | 局部特征识图 Sidecar 服务地址。Docker Compose 内部网络已预配置为 `http://imsearch:8765`。                                            |
| `COMIC_SHELF_ENABLE_DOCS`  | `false`                 | 是否开放 FastAPI 交互式 API 文档页面（`/docs` 与 `/redoc`）。公网环境建议保持 `false`。                                              |

### 3.3 性能调优与并发控制（低配 NAS / 进阶调优）

API 工作进程数固定为 1，不属于可调参数；这里的下载与缩略图并发均在同一 API 进程内协调。运行约束见 [并发与故障恢复边界](#11-本地书库的并发与故障恢复边界)。

| 环境变量                                   | 默认值          | 说明                                                                                                                                                          |
| :----------------------------------------- | :-------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `COMIC_SHELF_MAX_CONCURRENT_DOWNLOADS`     | `3`             | **远端图片下载并发数**。JM 官方 CDN 对高并发极为敏感，建议维持在 `2`~`4`，避免触发风控或请求超时。                                                            |
| `COMIC_SHELF_THUMB_CONCURRENCY`            | `4`             | **缩略图处理并发门禁**。限制同时进行 Pillow 转换的 CPU worker 线程数。在单核/双核低配 NAS（如 J1900、ARM 盒子）上建议设为 `1` 或 `2`，防止冷访问时 CPU 跑满。 |
| `COMIC_SHELF_MAX_PREFETCH`                 | `600`           | **单批次预缓存画页上限**，保护磁盘与网络。超长漫画每次点击“缓存全部”会自动顺延下载未缓存的前 N 页，直至全部完成。                                             |
| `COMIC_SHELF_PAGE_THUMB_WIDTH`             | `360`           | 详情页与子章节网格缩略图宽度（px）。                                                                                                                          |
| `COMIC_SHELF_PAGE_THUMB_QUALITY`           | `78`            | 缩略图 JPEG 压缩质量（兼顾清晰度与微秒级传输）。                                                                                                              |
| `COMIC_SHELF_COVER_WIDTH`                  | `720`           | 书架与详情页大封面宽度（px，默认 720 完美匹配 2x 视网膜高清度）。                                                                                             |
| `COMIC_SHELF_COVER_THUMB_WIDTH`            | `360`           | 书架阶梯封面 1x 缩略图宽度（px，默认 360 配合 HTML5 srcset 降低低密设备内存开销）。                                                                           |
| `COMIC_SHELF_COVER_QUALITY`                | `80`            | 大封面 JPEG 质量（默认 80 兼顾微秒级传输与典藏画质）。                                                                                                        |
| `COMIC_SHELF_COVER_COUNT`                  | `4`             | 每本漫画默认生成的封面预览张数。                                                                                                                              |
| `COMIC_SHELF_COVER_WEBP_QUALITY`           | `80`            | WebP 封面与 WebP 页缩略图的压缩质量。浏览器支持 WebP 时走这一档，`COMIC_SHELF_COVER_QUALITY` 与 `COMIC_SHELF_PAGE_THUMB_QUALITY` 只管 JPEG 回退格式。         |
| `COMIC_SHELF_COVER_CONCURRENCY`            | `2`             | **后台补生成封面的线程数**。收录后第 2 张起的预览封面与各话封面在这里排队生成，低配 NAS 可降为 `1`。                                                          |
| `COMIC_SHELF_LOG_LEVEL`                    | `info`          | 后端运行日志级别（可选 `debug`, `info`, `warning`, `error`）。                                                                                                |
| `COMIC_SHELF_ENABLE_AUTO_UPDATE`           | `true`          | 是否开启多章节连载后台自动追更巡检。设为 `false` 可完全关闭后台自动探测。每本漫画的更新周期可在元数据面板单独设置或设为 `0` 禁用。                            |
| `COMIC_SHELF_AUTO_UPDATE_INTERVAL_SECONDS` | `172800`        | 后台自动追更巡检轮询周期（秒）。默认 `172800`（2 天），防止对远端接口过于频繁唤醒。                                                                           |
| `COMIC_SHELF_ACCESS_LOG`                   | `true`          | 是否开启 Uvicorn 请求访问日志。默认已内置高频探针静音过滤（`/api/health` 与搜图状态 200 正常时不输出）；若需彻底关闭访问日志可设为 `false`。                  |
| `TZ`                                       | `Asia/Shanghai` | **容器系统时区**。设置容器内部运行时间与控制台日志时区，保持与本地直观体验一致。                                                                              |

### 3.4 哔咔漫画（PicAcg Provider）配置（可选）

| 环境变量                  | 必填等级                  | 默认值                           | 说明                                                                                                            |
| :------------------------ | :------------------------ | :------------------------------- | :-------------------------------------------------------------------------------------------------------------- |
| `PICA_EMAIL`              | ⚪ **可选（收录哔咔设）** | _(留空)_                         | **哔咔漫画登录账号/邮箱**。后端自动使用官方 HMAC-SHA256 签名算法生成签名并长效保持 JWT 会话，前端 0 手动输入。  |
| `PICA_PASSWORD`           | ⚪ **可选（收录哔咔设）** | _(留空)_                         | **哔咔漫画登录密码**。与账号配合自动登录。                                                                      |
| `PICA_PROXY`              | ⚪ **可选（网络代理）**   | _(留空)_                         | **HTTP / SOCKS5 代理地址**（如 `http://192.168.1.10:7890`）。用于突破大陆网络对哔咔 API 及分流 CDN 的连接阻断。 |
| `PICA_API_URL`            | ⚪ **可选自定义**         | `https://picaapi.picacomic.com/` | 哔咔官方移动端 REST API 入口，支持切换自建或第三方反代镜像。                                                    |
| `PICA_CHANNEL`            | ⚪ **可选自定义**         | `2`                              | **哔咔分流线路编号**。随请求头 `app-channel` 发给官方接口，通常无需修改。                                       |
| `PICA_EXTRA_CDN_HOSTS`    | ⚪ **可选自定义**         | _(留空)_                         | **额外分流 CDN 域名白名单**（英文逗号分隔）。用于局域网自建反代缓存或特定网络镜像 CDN 节点放行。                |
| `PICA_DOWNLOAD_PACING_MS` | ⚪ **可选自定义**         | `250`                            | **哔咔画页批量下载平滑微休眠**（毫秒，内置 ±20% 拟人化抖动）。设为 `0` 可完全关闭节流。                         |
| `PICA_API_PACING_MS`      | ⚪ **可选自定义**         | `150`                            | **哔咔多分卷元数据 API 请求间隔**（毫秒）。在解析多章节时防止突发并发请求冲击官方接口。设为 `0` 可关闭。        |

### 3.5 禁漫天堂（JMComic Provider）配置（可选）

| 环境变量              | 必填等级                  | 默认值   | 说明                                                                                                                                                                                                                              |
| :-------------------- | :------------------------ | :------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `JM_USERNAME`         | ⚪ **可选（收录禁漫设）** | _(留空)_ | **禁漫天堂登录账号/用户名**。配置后自动登录换取 `AVS` 凭据，用于解析需登录查看的受限漫画车号；若容器未配置环境变量但数据卷挂载了已有 `jm_session.json`，系统将自动接管已有会话（Zero-Env 凭据接管）；若两者皆无则以匿名模式抓取。 |
| `JM_PASSWORD`         | ⚪ **可选（收录禁漫设）** | _(留空)_ | **禁漫天堂登录密码**。与账号配合自动登录，会话持久化于 `backend/data/jm_session.json`，支持乐观长效复用与鉴权异常时的非破坏性原子自愈重登。                                                                                       |
| `JM_PROXY`            | ⚪ **可选（网络代理）**   | _(留空)_ | **控制流代理地址**（支持 HTTP / SOCKS5，如 `http://127.0.0.1:7890`）。用于域名嗅探、动态域名更新、HTML 页面与登录认证。                                                                                                           |
| `JM_IMAGE_PROXY_MODE` | ⚪ **可选分流策略**       | `auto`   | **画页大图下载代理模式**。`auto`（跟随 `JM_PROXY`）、`direct`（强制直连省流量）。                                                                                                                                                 |

### 3.6 全局统一网络代理配置（可选，推荐）

| 环境变量            | 必填等级                | 默认值   | 说明                                                                                                                                                                                      |
| :------------------ | :---------------------- | :------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `COMIC_SHELF_PROXY` | ⚪ **可选（全局代理）** | _(留空)_ | **全局统一网络代理地址**（支持 HTTP / SOCKS5，如 `http://127.0.0.1:7890`）。一站式为禁漫、哔咔、拷贝漫画所有远端图源提供基础代理。优先级：各源独立代理 > 全局代理 > 系统环境变量 > 直连。 |

### 3.7 拷贝漫画（CopyManga Provider）配置（可选）

| 环境变量               | 必填等级                  | 默认值                      | 说明                                                                                                            |
| :--------------------- | :------------------------ | :-------------------------- | :-------------------------------------------------------------------------------------------------------------- |
| `COPY_BASE_URL`        | ⚪ **可选自定义**         | `https://www.mangacopy.com` | **拷贝漫画主站网域**。若默认镜像发生地域阻断，可随时切换为官方其它可用镜像。                                    |
| `COPY_TOKEN`           | ⚪ **可选（收录受限本）** | _(留空)_                    | **拷贝漫画会员会话 Token**。直接从网页端 Cookie 或 `Authorization` 头中提取，100% 穿透任何强风控与图形验证码。  |
| `COPY_USERNAME`        | ⚪ **可选（自动登录）**   | _(留空)_                    | **拷贝漫画登录用户名**。与密码配合自动登录获取会话 Token。                                                      |
| `COPY_PASSWORD`        | ⚪ **可选（自动登录）**   | _(留空)_                    | **拷贝漫画登录密码**。会话以 `0600` 权限持久化于 `backend/data/copymanga_session.json`。                        |
| `COPY_PROXY`           | ⚪ **可选独立代理**       | _(留空，跟随全局统一代理)_  | **拷贝漫画独立网络代理**。如未配置则自动继承 `COMIC_SHELF_PROXY`。                                              |
| `COPY_EXTRA_CDN_HOSTS` | ⚪ **可选自定义**         | _(留空)_                    | **额外画页 CDN 域名白名单**（逗号分隔）。默认已放行官方 `*.mangafunb.fun`、`*.mangacopy.com` 等，通常无需配置。 |

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
vpr reindex:image
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

### 4.5 方式四：分布式运行（低功耗 NAS + WSL2 / 独立 PC 运维全指南）

> **适用场景**：
> 当 TrueNAS 采用 Intel 赛扬 N5095 / N5105 / J4105 等缺少 AVX2 指令集的低功耗处理器时，可将 `imsearch` 部署在拥有强劲 CPU（支持 AVX2）的独立 Windows / Mac / Linux / **WSL2** 电脑上。
> 运算由电脑处理，图片与特征库依然保存在 NAS，零冗余拷贝。

#### 1. 挂载 NAS 共享目录到本地（WSL2 示例）

在 WSL2 终端将 NAS 的 SMB 共享挂载为本地目录：

```bash
# 创建挂载点并挂载 NAS 共享路径（将 <NAS-IP> 和 <SHARE-NAME> 替换为你的实际共享路径）
sudo mkdir -p /mnt/nas_manga
sudo mount -t drvfs '\\<NAS-IP>\<SHARE-NAME>' /mnt/nas_manga
# 示例：sudo mount -t drvfs '\\192.168.1.100\comics' /mnt/nas_manga
```

#### 2. 一键脚本运维速查表（推荐）

项目内置了专用运维脚本 `scripts/imsearch.sh`（支持 `vpr imsearch` 触发，自动智能探测 `/mnt/nas_manga` 挂载点）：

| 操作目标         | 推荐执行命令           | 说明                                                      |
| :--------------- | :--------------------- | :-------------------------------------------------------- |
| **启动后台服务** | `vpr imsearch start`   | 监听 `0.0.0.0:8765` 端口，后台常驻运行并自动健康探测      |
| **停止服务**     | `vpr imsearch stop`    | 优雅终止运行中的 imsearch 进程                            |
| **重启服务**     | `vpr imsearch restart` | 平滑重启以加载最新索引                                    |
| **查看运行状态** | `vpr imsearch status`  | 查看运行状态、PID、端口、内存占用与健康度                 |
| **日常增量更新** | `vpr imsearch reindex` | 扫描 NAS 新图提取特征、追加倒排索引并自动重启服务（秒级） |
| **全量重置重训** | `vpr imsearch train`   | 重新训练 512 聚类中心并彻底重建索引库                     |
| **查看实时日志** | `vpr imsearch logs`    | 跟踪查看实时搜索日志（`Ctrl+C` 退出）                     |

_(也可以直接运行 `bash scripts/imsearch.sh <action>`)_

#### 3. 在 NAS 端配置连通

在 NAS 的 `docker-compose.yml` 中填入这台 WSL2 / PC 的局域网 IP：

```yaml
environment:
  # 指向运行 imsearch 的电脑局域网 IP（例如 http://192.168.1.50:8765）：
  COMIC_SHELF_IMSEARCH_URL: http://<WSL2_OR_PC_IP>:8765
```

然后在 NAS 终端执行平滑重启：

```bash
docker compose up -d paper-room
```

---

## 5. 数据持久化与备份迁移

所有漫画元数据、图片和搜图特征库统一存放在数据目录（`COMIC_SHELF_DATA`，容器内为 `/app/data`）：

```text
backend/data/
├── comic_shelf.db              # SQLite 核心状态库（访客通行证、阅读进度、藏书影子索引，~5MB）
├── comic_dialogues.db          # 台词全文检索专库（FTS5 Trigram 倒排索引、OCR 增量元数据，独立物理隔离，~500MB+）
├── jm_html_domain.json          # 禁漫可用域名缓存
├── jm_session.json             # 禁漫 AVS/Web 会话凭据（0o600 私有安全权限，长效乐观复用，支持挂载已有凭据 Zero-Env 接管）
├── picacg_session.json         # 哔咔会话凭据与 JWT 缓存（0o600 私有安全权限）
├── corpus/                     # 领域语料库
│   └── galgame/                # Galgame 双语剧本资产 (*.jsonl)
├── imsearch/                   # 以图搜图特征库与倒排索引
│   ├── centroids.bin           # 聚类量化器模型
│   ├── invlists.bin            # 倒排索引
│   └── imsearch.db             # 向量数据库
└── library/                    # 漫画资源库
    ├── jm/523607/              # 禁漫作品目录
    │   ├── album.json          # 元数据与全局页码映射
    │   ├── remote.json         # 远端分块与解密状态
    │   ├── covers/             # 封面 JPEG / WebP
    │   ├── pages/              # 已解密的高清成品页面 (WebP) 与伴生资产 (*.ocr.json)
    │   └── thumbs/             # 360px 索引缩略图
    └── local/                  # 本地自建图集 / 视频拆帧
```

- **零依赖单点备份**：备份或迁移时，**只需复制整个 `backend/data/` 目录**（在 NAS 环境下对应挂载卷 `/mnt/nas_manga`）；核心用户状态库 `comic_shelf.db` 仅几兆字节，极速快照。
- **专库垂直解耦（Zero Lock Contention）**：台词全文检索与 OCR 写入独立收敛于 `comic_dialogues.db`，万级与十万级规模下数百万行台词的批量插入完全不占用主库写锁，彻底避免访客翻页或收藏时的锁冲突。
- **跨平台兼容**：元数据采用向前兼容的 JSON 与单文件 SQLite WAL 架构，直接复制粘贴或 NAS 快照即可在其他设备完美还原。

### 5.1 漫画台词全文索引与 OCR 提取流水线（`scripts/ocr.sh` & `scripts/sync_ocr.py`）

高性能机器直接处理本地或局域网映射路径中的画页，生成图片旁的 `{index}.ocr.json`。
OCR 提取与台词索引同步各自增量：提取按页跳过新鲜合法结果；同步按本检查伴生文件清单、文件状态和 `album.json`，
只有发生变化的书才重新入库及尝试编码语义向量。台词索引独立存于 `comic_dialogues.db`，正常本机同步无需停服务或重启。

文件扫描、保守分类和同步入口集中在 `backend/app/ocr/`；容器命令为 `python -m app.ocr.sync`。
旧的 `python -m app.sync_ocr` 已随模块整理移除，已有 NAS 任务计划应更新命令。
分类不再仅凭前两页、长独白、重复台词或“邮箱／赞助／二维码”等普通词排除正文。
平台与下载引导、网址或二维码形成组合证据，有坐标时还检查广告信息的面积，整页广告保存为副文本。
制作说明与后记同样作为副文本保存；关键词、语义召回和故事上下文只使用正文，原 `.ocr.json` 不被清洗改写。
`jm/625761` 第 32 页已作为固定广告回归样本；分类版本参与增量签名，升级后下次同步自动重新分类一次。

本机 `data` 可以一条命令完成提取及索引同步。映射盘用于读画页、写伴生文件；若服务在 NAS 上，
就在 NAS 本机或服务容器中执行同步。SQLite WAL 要求访问数据库的进程在同一主机，
不能让算力机通过 NFS/SMB/SSHFS 打开 NAS 的数据库（见 [SQLite WAL 限制](https://sqlite.org/wal.html)）。
OCR 专用 HTTP 同步接口及其 URL、令牌参数已移除；文件提取和本机同步均不需要机器令牌。

**同步触发方式**：当前没有监听 `.ocr.json` 的服务，也没有内置定时 OCR 同步任务。
日常新增或复制伴生文件后，需要显式执行同步；`run --sync-local` 会在用户启动提取后自动衔接本机入库。
部分画页更新、章节删除或分组调整会同步该本；启动时旧索引结构迁移及半截迁移修复也可能回填。
这些是数据修改或修复触发，普通重启不保证扫入新伴生文件。自动追更巡检不负责 OCR 同步。
如需定时运行，可在 NAS 任务计划器中配置下述同步命令，项目默认未配置调度；同一书库一次只运行一个同步任务。

| 场景                           | 提取与同步顺序                                                                                            |
| :----------------------------- | :-------------------------------------------------------------------------------------------------------- |
| 算力与书库同机，数据在本地磁盘 | `vpr ocr run --data-dir /path/to/data --sync-local`，或提取后执行 `vpr ocr:sync --data-dir /path/to/data` |
| 算力机经共享目录处理 NAS 书库  | 算力机只执行提取，随后在 NAS 主机或应用容器执行同步                                                       |
| 已有伴生文件，补入索引         | 在索引所属主机执行 `sync`；未变化的本跳过解析与编码                                                       |

**NAS 两步操作示例**（按单本同步，适合先观察小机器耗时）：

```bash
# 1) 算力机：共享目录映射为 /mnt/nas_manga，提取结果直接写回原图旁；不加 --sync-local。
vpr ocr run --data-dir /mnt/nas_manga --source jm --id 1059521 --workers 4

# 2) NAS：在 Compose 项目目录执行，由应用容器读取 /app/data 并更新本地台词数据库。
docker compose exec -T paper-room python -m app.ocr.sync --source jm --id 1059521
```

共享目录必须对应 NAS 容器实际使用的 `/app/data`。若先在算力机的独立副本里提取，
将 `.ocr.json` 复制到 NAS 对应画页目录后，再执行第 2 步；日常同步不复制或替换整个数据库。
同步范围和大库资源限制见 §5.1.3。

1. **高性能机一键状态巡检与依赖安装**（**默认即 GPU**，不需要记 `--gpu`）：

   ```bash
   # 巡检：OCR 伴生覆盖率 + 宿主显卡 + 本轮默认算力线 + 两条线各自的"会话级"实际推理设备
   vpr ocr status              # 等价于 bash scripts/ocr.sh status

   # 装依赖（需要 uv）：版本全部来自 uv.lock，依赖声明在 pyproject.toml 的 ocr / ocr-gpu 两个依赖组里。
   # 检测到 NVIDIA 显卡 → 在项目内建 .venv-ocr/（已 gitignore），里面只有 ocr-gpu 组；
   # 没检测到卡 → 往应用 .venv 里追加 ocr 组。装完 GPU 环境后，run/test/status 自动优先用它。
   bash scripts/ocr.sh install
   # 明确只要 CPU（无卡机、或与宿主争卡时）：
   bash scripts/ocr.sh install --cpu
   # 环境想放到别处（外置盘/NAS 挂载）：COMIC_SHELF_OCR_VENV=/path/to/env bash scripts/ocr.sh install
   ```

   > **Python 版本**：后端以 **Python 3.14 为硬下限**（源码使用了 3.14 才有的语法，旧解释器一 import 就 `SyntaxError`）。
   > `ocr.sh run --sync-local` 的识别步骤用 OCR 环境，预检与入库步骤另用应用 `.venv`；
   > `.venv-ocr` 不需要安装后端依赖。本机同步入口 `scripts/sync_ocr.py` / `python -m app.ocr.sync`
   > 需要应用环境（Python 3.14），会在识别前校验目标并初始化独立台词库；失败时不开始提取。
   > `.venv-ocr` 由 uv 按仓库的 `.python-version` 选解释器，同样是 3.14。

   > **这些依赖与运行时无关**：两个 OCR 依赖组都不是默认组，Dockerfile 的 `uv sync --no-dev` 与 `vpr setup:py`
   > 都不会装它们，生产依赖包清单不变，不增加 OCR 推理包或模型（`backend/tests/test_ocr_worker.py` 有用例钉住）；本轮仅增加轻量本机同步入口的 Python 源码。
   > 用旧版脚本（pip + `requirements-ocr*.txt`）建过 `.venv-ocr` 的机器，请先删掉该目录再 `install`：
   > 旧脚本在里面留了一份 uv 卸不掉的 CPU 版 `onnxruntime` 安装记录。

   回落是**显式**的：`.venv-ocr` 不存在时 `run` 会打一行 `⚠️ 检测到宿主有 NVIDIA 显卡，但 GPU 算力环境
   未创建，本轮按 CPU 跑` 并给出建环境的命令；`--gpu` 时环境缺失直接拒绝（exit 1）。环境在、但 Det/Cls/Rec 三段会话里有一段没跑在 CUDA 上（CPU 版 `onnxruntime` 覆盖了 GPU 版，或 `LD_LIBRARY_PATH` 没挂上 venv 内的 CUDA 库），`build_engine` 也会当场报错退出，绝不静默降级。

   > ⚠️ **不要**手动把 `onnxruntime-gpu` 与 CPU 版 `onnxruntime` 混装进同一个环境：两个 wheel
   > 共用 `site-packages/onnxruntime/` 目录，覆盖安装会留下混合文件，`get_available_providers()`
   > 照样列出 CUDA 但推理静默退回 CPU。两个依赖组已在 `pyproject.toml` 里声明互斥，
   > uv 会拒绝同时安装；原理与实测数据见 `docs/PITFALLS.md` #137。

2. **高性能机批量提取，按需在本机同步索引**：

   ```bash
   # GPU 环境就绪时默认使用 GPU，可从 4 个线程开始评估：
   vpr ocr run --source jm --workers 4

   # 强制回落应用的 CPU 线：
   bash scripts/ocr.sh run --cpu --source jm

   # 本机书库：同一条命令完成提取与增量入库（GPU 环境也可用）：
   vpr ocr run --data-dir /path/to/data --source jm --id 1059521 --workers 4 --sync-local

   # 提取和同步分别限制册数；小机器可先只建关键词，后续普通 sync 会补向量：
   vpr ocr run --data-dir /path/to/data --limit 10 --sync-local --sync-limit 10 --skip-vectors

   # 普通图片目录：可为本地或映射盘路径，递归提取，不要求纸间书库结构：
   vpr ocr run --directory /path/to/images --workers 4
   ```

   > **跑批结果看退出码**：画页提取或本机索引同步任一失败均返回非零；已生成的有效伴生文件保留。
   > 直接重跑会补失败页；指定 `--sync-local` 时，即使全部画页增量跳过也仍会同步索引，
   > 无需 `--force` 重提。部分坏页不妨碍入库已生成的结果，但整条命令仍返回失败。
   > `--sync-local` 只由 `ocr.sh run` 编排，直接调用 worker 只做文件提取。
   > `--limit` 只限制有新页产出的书库册数，每本每轮最多尝试一次；失败较多时尝试册数可能更多。
   > 同步只按 `--source` / `--id` 或 `--image` 所属漫画确定范围；`--limit` 和 `--page` 不传给同步入口。
   > 因此 `--limit 10 --sync-local` 仍会同步所选范围内所有漫画，不能当作“每次只同步 10 本”的限制。
   > 如需限制同步，另加 `--sync-limit 10`；仅用于 `run --sync-local`，单独 `sync` 则使用 `--limit 10`。
   > 普通目录 `--directory` 与单页 `--image` 不能混用，也不接受 `--source` / `--id` / `--page` / `--limit`；
   > 普通目录不自动收录或猜测作品身份，不支持 `--sync-local`。书库内单页可用 `--image` + `--sync-local`，
   > 相对所选 `--data-dir` 确定所属漫画；书库外的单页只提取。
   > 递归扫描跳过隐藏项与内部符号链接；同目录的 `page.jpg` / `page.png` 会共用伴生目标，因此提前拒绝。
   > 临时文件独占创建、沿用宿主 umask，刷盘后原子替换；写入或推理失败清理临时文件，并保留旧有效结果。
   > 读取和发布使用限定根目录的描述符，不跟随文件或中间目录链接。识别前后检查源图身份，新结果记录源图
   > 的大小和修改时间；推理期间换图不发布旧结果，临界发布后的新图也不会被旧结果标为新鲜。
   > 伴生文件新增提取配置：RapidOCR 版本、模型轨道、置信度与聚类修订共同决定增量命中。
   > 历史没有此配置的文件仍可直接同步，但下一次提取会更新一次；调置信度或升级聚类后无需手动 `--force`。
   > 图片后缀来自现有 Pillow 的读取注册表，实际解码时也校验格式：包括 JPEG、PNG、WebP、GIF、AVIF、BMP、
   > TIFF、ICO 等可读光栅格式；GIF 和多页 TIFF 只识别首帧 / 首页。EPS、WMF、PDF、SVG 等文档不直接交给 OCR，
   > 需要先转换为画页；不会为扩展格式额外安装解码包，不可解码的候选图片明确报错。
   > `--source` / `--id` 必须是后端不会改写的规范目录名，未知图源或书号报错；显式 `--data-dir` 和非空
   > `COMIC_SHELF_DATA` 写错不会换库。普通目录及单页提取不依赖默认数据目录。
   > `--page` 写错在提取前拒绝；多章节本各话有同名页，使用 `--image <画页路径>` 定位。

   > `--workers` 在 CPU 模式下建议先使用默认值 2：单个引擎内部也使用多核，加线程可能争抢资源。
   > CPU 与 GPU 的合适并发数应在目标环境用同一批画页复测；分别记录模型加载、稳态推理和含写盘的
   > 端到端耗时。画页分辨率与内容会影响吞吐，不同输入和计时口径不能直接比较。
   > 复测请走 `bash scripts/ocr.sh lines ...`：直接 `.venv-ocr/bin/python scripts/ocr_lines.py --gpu`
   > 会漏掉 `LD_LIBRARY_PATH`，`libcublasLt.so.13` 找不到时会话退回 CPU。以前这一步是静默的，量出来的
   > "GPU"和 CPU 同带（实测踩过，见 `docs/PITFALLS.md` #137）；现在 `build_engine(True)` 会当场报错。

   **引擎只剩一条线：`rapidocr` 3.x + PP-OCRv6 small**（官方列明该单模型覆盖简中/繁中/日文，
   `tiny` 不含日文所以必须用 `small`）。旧的 v3 轨道（`rapidocr-onnxruntime`）已整体删除：它
   6623 字的字符表里**只有 5 个假名**，日文与繁体常被强行写成"形似汉字的乱码"（`這` → `遣`、
   `歡` 直接丢），只要那条路还开着，"忘了带参数"就能把乱码灌进语料且无人察觉。
   模型切换的质量核验应逐串检查完整对白、假名与繁体字；吞吐应在目标环境另行测量。历史 v3 侧车仍然合法，
   `engine_track` 字段留着做溯源。

   改气泡聚类判据之前，先用离线实验台（推理只跑一次，之后本地迭代，绝不写 `backend/data`）：

   ```bash
   # 1) dump 指定画页的原始识别行到本人拥有的实验目录（省略 --out 则打印随机私有临时目录）
   bash scripts/ocr.sh lines --source jm --id 319445 --pages 10 --out /tmp/prl
   # 2) 改完 scripts/ocr_worker.py 的 cluster_blocks 后，不跑推理直接量效果：
   #    打印气泡数 / 字数 / 气泡面积分布 / 疑似误并清单
   bash scripts/ocr.sh lines --recluster /tmp/prl
   ```

   dump 按图源、书号和章节路径存放，避免扁平文件名碰撞；只复用对应同一张画页、结构合法且新鲜的结果。
   默认输出目录随机创建且权限为 0700；显式 `--out` 要求当前用户拥有，路径不能由其他用户修改。
   发布采用原子且不覆盖已有文件的方式；损坏、错配或链接目标直接报错。`--recluster` 支持递归读取此目录结构。

   判据落地后要覆盖现网侧车就 `bash scripts/ocr.sh run --source jm --id <id> --force`，
   随后 `bash scripts/ocr.sh sync` 重灌索引。侧车里的 `engine: rapidocr` 是
   `is_valid_ocr_sidecar` 的合法性标记，改不得——改了会让新侧车被当成脏缓存无限重提。

3. **宿主机 / NAS 终端一键增量同步已存在的伴生文件**：

   ```bash
   # 在索引所在机器执行全库增量同步（建议明确指定本机 data）：
   vpr ocr:sync --data-dir /path/to/data
   # 或指定单本（经 ocr.sh 走应用 .venv 的解释器，目录探测与 worker 共用 app.ocr.files）：
   bash scripts/ocr.sh sync --source jm --id 1059521
   ```

   `sync` 点名 `--source` 与 `--id` 时允许漫画目录已被删除，用于清理该本残留索引；
   只有 `--id` 时也会按书号筛选。点名同步不清理其他本的孤儿索引；全库同步保留孤儿清理。
   提取命令 `run` 指定不存在的书号则直接报错。

   增量元数据新增文件状态签名，能感知删页、删章节、保留旧 mtime 的复制和页码映射变化。
   旧数据库自动追加这一列；旧记录在下次同步对应漫画时更新一次，无需停服务或整库替换。

   默认 Docker 镜像内可直接执行轻量同步入口，不需要 `scripts/` 或 OCR 推理包：

   ```bash
   # 单本增量同步：
   docker compose exec -T paper-room python -m app.ocr.sync --source jm --id 1059521
   # 全库增量同步：
   docker compose exec -T paper-room python -m app.ocr.sync
   # 小机器分批：本轮最多更新 10 本，已完成的本不占名额；先只建关键词。
   docker compose exec -T paper-room python -m app.ocr.sync --limit 10 --skip-vectors
   # 后续补向量或继续同步：普通重跑会只处理未完成的本。
   docker compose exec -T paper-room python -m app.ocr.sync --limit 10
   ```

   该入口使用容器已有的 `COMIC_SHELF_DATA`、应用依赖与语义模型；未变化的本跳过解析和编码。
   启用语义检索时应使用与服务一致的模型环境；模型不可用时仍可入库关键词，既有逻辑会清除该本旧向量。
   损坏 JSON、气泡文字或页码映射会让该本失败，保留旧关键词索引，其余本仍继续处理。
   关键词和向量分别记录源签名及完成状态；实际编码失败时 CLI 返回非零，关键词保留，普通重跑补向量。

4. **单张画页快速测试与气泡聚类预览**：
   ```bash
   bash scripts/ocr.sh test /path/to/page.webp          # 默认走 GPU 环境
   bash scripts/ocr.sh test --cpu /path/to/page.webp    # 强制用应用 CPU 环境做对照
   ```
   `test` 与 `run` 用同一套引擎构造与聚类，只打印、不写盘。要看"GPU 到底有没有生效"用 `bash scripts/ocr.sh status`
   （真建一次引擎，Det/Cls/Rec 三段会话任一不在 CUDA 上就报出来）；GPU 用不上时 `run` / `test` / `lines` 都会当场报错，而不是静默按 CPU 跑。

#### 5.1.1 PDF 扉页自动分话：按 ADR 0024 保持**可选**，默认不装

默认服务镜像不执行画页 OCR 推理；台词同步只读取 `{index}.ocr.json`，增量更新独立索引。
`backend/app/storage/pdf.py::_extract_chapters_from_ocr`（导入 PDF 且**没有**电子书签时的第二轨分话探测）
按 ADR 0024 的口径是"该包属可选依赖，未安装时本轨自动跳过"，因此 `rapidocr` **不在** `pyproject.toml` 的运行时依赖表
（`[project].dependencies`）里，只在点名才装的 `ocr` 依赖组里，别顺手挪进运行时依赖——它只服务"无书签 PDF 要自动切话"
这一件事。代价要按整条依赖链估算：Linux x86-64 下 OCR 组额外安装的包解包后约 450 MiB，
大头是 `opencv-python`、`onnxruntime`、`numpy`，`rapidocr` 自身约 33 MB（含模型）。
约 277 MiB 的基础镜像因此可能超过 700 MiB，还要计入系统库；这是解包体积估算，
不是 Docker 实测，不适用于所有平台。该可选定制会超出默认镜像 300 MiB 的预算。

缺它时的行为：该 PDF 平铺成单章，导入照常完成，日志打一行 **WARNING**「跳过 PDF 扉页自动分话」。
（这里必须是 warning：uvicorn 默认不给 root logger 设级别，info 会被整条丢掉，就变成"没人知道为什么没有话目录"。）

经常在 NAS 上导入无书签 PDF、想要自动分话的话，在**你自己的** Dockerfile 里同时补系统库和 `ocr` 依赖组。
只加 Python 包不够：`opencv-python` 链接 `libGL.so.1`、`libglib-2.0.so.0` 和 `libX11.so.6`，
精简 Python 镜像缺这些库时，导入仍会失败、分话仍会跳过。仓库默认 Dockerfile 不包含以下可选修改。

先在 uv 安装层之前添加系统依赖（Debian trixie 使用 `libglib2.0-0t64`，较旧 Debian 对应 `libglib2.0-0`）：

```dockerfile
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends libgl1 libglib2.0-0t64 libx11-6 \
    && rm -rf /var/lib/apt/lists/*
```

再把原有、带 uv 挂载的安装层末行改为下面这一行，保留原有挂载与环境变量配置
（与算力机 CPU 线是同一组包，版本由 `uv.lock` 锁定）：

```dockerfile
# Dockerfile 安装层的最后一行改为：
    uv sync --locked --no-dev --inexact --group ocr
```

最后在依赖安装层后加入真正的引擎自检，缺库或推理后端不可用时让构建失败：

```dockerfile
RUN python -c "from rapidocr import RapidOCR; RapidOCR()"
```

构建后用 `docker image inspect <你的镜像> --format '{{.Size}}'` 读取实际镜像字节数。
这些安装说明不改变仓库默认镜像的依赖清单与体积。

#### 5.1.2 语义检索「按意思找台词」（可选能力，默认不启用）

台词检索有两条腿：FTS5 关键词（默认就有，简繁字形无关）与向量语义（按下面三步启用）。
语义这条腿解决**字面完全不通**的查询——搜「告白」拿到「我喜欢你」、搜「脸红」拿到「满脸通红」。
为什么做成独立出口、不与关键词混排，见 ADR 0028。

推理依赖不进 `pyproject.toml` 的默认运行时依赖表，模型文件也需单独放置。
不安装时语义召回不可用，其余功能不受影响。

| 项目         | 运行边界                                                                                                                |
| :----------- | :---------------------------------------------------------------------------------------------------------------------- |
| 运行时       | `onnxruntime`（CPU）+ `numpy` + `tokenizers`，按需安装                                                                  |
| 模型         | 量化 `bge-small-zh-v1.5`，ONNX，**不需要 torch**                                                                        |
| 语料编码     | 与台词索引同步衔接，按书增量补建；全量重建显式触发                                                                      |
| 每次搜索     | 问题编码、向量检索与命中原文回表；性能在目标环境按真实库大小验证                                                        |
| 不装时的行为 | 关键词检索与台词索引同步不受影响；`/api/search/dialogue-semantic` 返回 `available=false` + `reason=encoder_unavailable` |

估算首次建库成本时，页数需先换算成筛选后参与编码的台词条数；大库同步与语义搜索的内存边界见 §5.1.3。

### 🛠️ 如何在 NAS 或本地服务上启用语义检索（按需启用指南）

#### 第一步：放置模型文件（随数据卷持久化，仅 24MB）

模型文件放在数据持久化挂载目录的 `models/` 下，容器重建或升级**绝不丢失**：

> 💡 **宿主机路径对应规则**：
> 如果你的 Docker 映射为 `-v /volume1/docker/comic-shelf:/app/data`（或 Compose 默认的 `./backend/data:/app/data`），
> 那么模型目录即为宿主机上的 `/volume1/docker/comic-shelf/models/bge-small-zh-v1.5/`。

```bash
# 1) 进入数据持久化目录（开发机为 backend/data/，NAS 为对应的宿主机真实挂载路径）
mkdir -p backend/data/models/bge-small-zh-v1.5
cd backend/data/models/bge-small-zh-v1.5

# 2) 下载模型权重与分词配置（二选一：curl 或 wget，国内直连 HuggingFace 镜像）：
# 选项 A: curl
curl -L https://hf-mirror.com/Xenova/bge-small-zh-v1.5/resolve/main/onnx/model_quantized.onnx -o model.onnx
curl -L https://hf-mirror.com/Xenova/bge-small-zh-v1.5/resolve/main/tokenizer.json -o tokenizer.json

# 选项 B: wget（若 NAS 终端没有 curl）
wget -O model.onnx https://hf-mirror.com/Xenova/bge-small-zh-v1.5/resolve/main/onnx/model_quantized.onnx
wget -O tokenizer.json https://hf-mirror.com/Xenova/bge-small-zh-v1.5/resolve/main/tokenizer.json
# 想放别处可配置环境变量：COMIC_SHELF_EMBED_DIR=/mnt/nas_manga/models/bge-small-zh-v1.5
```

#### 第二步：安装轻量 CPU 推理运行时（约 70MB）

根据你的部署形态，选择以下**任一方式**即可（必须是 CPU 版 onnxruntime，严禁与 GPU 版混装：错题本 #140）：

- **方式 A（已运行 Docker 容器，最快捷）**：
  通过宿主机终端（或群晖 Container Manager / Portainer 等 Web 界面的「终端机」中打开 bash）执行一条命令在线补装，即刻生效：
  ```bash
  docker exec -it paper-room bash -c "apt-get update && apt-get install -y --no-install-recommends libstdc++6 && pip install 'onnxruntime>=1.20' 'tokenizers>=0.21' -i https://pypi.tuna.tsinghua.edu.cn/simple"
  ```
  _(注：Debian slim 基座需底层 `libstdc++6` 支持，故命令中一并包含系统库安装)_
- **方式 B（自建 Docker 镜像，永久固化）**：
  若在本地或 NAS 编译镜像，在 `Dockerfile` 的 uv sync 安装层后追加系统底层库与推理包：
  ```dockerfile
  RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 \
      && rm -rf /var/lib/apt/lists/* \
      && pip install "onnxruntime>=1.20" "tokenizers>=0.21" -i https://pypi.tuna.tsinghua.edu.cn/simple
  ```
- **方式 C（纯 Python 本地/开发机/宿主机环境）**：
  激活虚拟环境直接执行：
  ```bash
  pip install "onnxruntime>=1.20" "tokenizers>=0.21" -i https://pypi.tuna.tsinghua.edu.cn/simple
  ```

#### 第三步：建立/同步向量与验证

首次启用或更换模型后，普通同步会按向量完成状态与模型内容指纹补建，不需要强制重写关键词索引。
小机器可先按本运行，在同一应用环境中编码向量，再验证检索：

```bash
# NAS 容器：按本处理，观察耗时与内存后再处理下一本。
docker compose exec -T paper-room python -m app.ocr.sync --source jm --id 1059521
# 本机源码部署的对应命令：
vpr ocr:sync --data-dir /path/to/data --source jm --id 1059521
```

确认全库规模和可用内存后，也可使用馆长接口仅重建全库向量。该接口在当前请求内执行，
没有后台队列、限速或断点进度；大库不要把它当作轻量初始化操作。

```bash
# 1) 可选：全库向量重建，只在首次启用或换模型时需要；建议在低负载时执行。
# 若未设置 COMIC_SHELF_SECRET（局域网免密），可去掉 -H 头：
curl -X POST http://127.0.0.1:8000/api/search/dialogue-vectors/rebuild \
     -H "Authorization: Bearer $COMIC_SHELF_SECRET"

# 2) 验证检索（输入无字面共同字的语义短语，能返回结果即代表全链路通畅）：
curl "http://127.0.0.1:8000/api/search/dialogue-semantic?q=告白&limit=3" \
     -H "Authorization: Bearer $COMIC_SHELF_SECRET"
```

日常使用画页旁的 `.ocr.json` 作为同步来源，在数据库所属主机执行本机增量同步，
不直接覆盖运行中的 `comic_dialogues.db`。该库使用 SQLite WAL，复制单个 `.db` 文件可能遗漏 WAL 中已提交的内容，
替换运行中数据库也不是索引更新协议；整库迁移应按一致性备份或停写迁移处理。

日常仍需要触发台词索引同步；对发生变化的本，同步会在关键词提交后自动重编该本向量，
无需再单独执行全库向量重建。首次安装模型、更换模型或编码失败时，普通同步可按本补建；
模型维度改变时状态会报 `dim_mismatch`，同维度但模型指纹不同会报 `model_mismatch`，重新同步完成后恢复语义出口。

旧库升级后，存量向量若缺少源签名、模型签名或同步元数据，同样返回 `model_mismatch`，等待本机同步补建；
旧向量保留，关键词检索继续可用。只更新了关键词、尚未产生向量的漫画不会因此阻断已有语义索引。
模型会话、维度与签名按完整状态发布，每次编码固定使用同一状态；查询与每批建库编码核对预期模型签名，
避免在线换模型时混用向量空间。初始化期间观察到模型文件变化会拒绝发布，后续请求可重试。

> ⚠️ 语义出口的 `similarity` 是余弦相似度（-1..1），**只在同一次查询的结果之间比高低**：真命中与噪声的分数区间重叠，
> 跨查询比较和绝对阈值都不成立，「没找到」只看 `reason`。关键词出口的 `rank_score` 是**本次候选池内**归一，
> 且排序掺了本人的收藏与阅读进度。两个数不是一回事，**不要混排、不要互当阈值用**（ADR 0028 决策一）。

#### 5.1.3 小机器同步与大库资源限制

**单页输入预算**（集中在 `app/ocr/assets.py`）：OCR JSON 最多 2 MiB、每页最多 1024 个气泡／识别行、
每条文字最多 8192 字符；提取图片最多 50 MiB、4000 万像素。JSON 先有界读取再解析，图片在解码和推理前检查。
超过预算会明确失败，不裁剪原文、不替换旧结果。它们是输入限制，不是模型推理的硬超时；
当前线程推理没有可强制终止的单页期限，异常慢图仍需停止任务后排查。

**原图核验与提交**：同步签名包含画页文件状态；新伴生文件的 `source_image` 必须匹配当前原图大小与修改时间，
原图缺失或已变化会拒绝该本更新。历史没有 `source_image` 的资产继续兼容入库，并明确计为“原图对应关系未核验”，
下次重新提取后补齐；不会把历史资产当作已核验，也不在升级时清空旧索引。
关键词发布和存储画页修改共用本机书籍文件锁，提交事务内再次检查源文件与预期索引版本。
其他任务已发布新版本时旧任务失败，普通重跑即可恢复；该乐观版本目前是台词库全局版本，
无关漫画的并发提交也可能要求重试。`.ocr-locks/` 是书库内部锁目录，运行时不要删改。
程序自动创建并保留锁文件，负责获取与释放锁，无需手动部署；缺失漫画的普通读取不会创建锁文件。
服务和本机同步进程应使用同一 UID，锁文件权限为 `0600`；Docker 部署优先使用上面的
`docker compose exec -T paper-room python -m app.ocr.sync`，让同步与服务在同一容器账号下运行。
这些锁适用于同主机应用操作；共享盘上的外部编辑者应在提取完成后同步，不能视作分布式锁协议。

同步 10 万页不会同时读取全库所有画页：`app.ocr.sync` 按本串行处理，未变化的本只检查文件状态。
但首次同步或本次有大量变化时，每一本都要解析伴生文件、整理语料并写入 FTS；启用语义模型后，
还会同步编码该本的有效台词。独立台词数据库隔离了主库写锁，不隔离 CPU、内存和磁盘 I/O，
大批量任务仍可能占满小机器资源并拖慢在线请求。

当前实现的内存边界：

- **关键词逐页暂存**：每次解析一页并写入 SQLite 磁盘临时表，全部成功后事务替换该本索引；不保留整本气泡和模板统计。
  文件清单与 `album.json` 页码映射仍按本读取，超大单页 JSON 也有自身解析成本。
- **向量每批 64 条暂存**：从索引游标读取、编码并写入磁盘临时表，全部成功后短事务发布；不用整本输出矩阵。
- **语义搜索按规模选择**：估算矩阵与键映射在 32 MiB 预算内时缓存小库；超预算则每块读取 1024 条做精确余弦计算，
  只保留有界候选页。模型、Python 对象和 SQLite 缓存另有内存开销，大库搜索以额外磁盘 I/O 换取较低内存。

以当前 512 维、float32 向量为例，**仅矩阵数据**占用为 `有效向量条数 × 512 × 4` 字节。
若 10 万页平均有 4 条筛选后可编码的台词，即 40 万条向量，矩阵约 **781 MiB**；
当前实现对此规模走分块搜索，每块 1024 条的矩阵约 **2 MiB**，不会加载完整 781 MiB 矩阵。
这些是容量估算，不是目标 NAS 实测；实际耗时仍受 CPU、磁盘与在线请求影响。

小机器的操作建议：

1. 默认镜像不启用语义模型，只做关键词索引时，先选一本有代表性的漫画同步，观察耗时、内存和磁盘空间。
2. 使用 `--source` 与 `--id` 按本同步，并在低负载时段执行；日常不用 `--force`，避免重复整理与编码未变化的本。
   可用 `sync --limit 10` 分批；`run --limit` 只限制 OCR 提取，串联同步另用 `--sync-limit`。
3. 初次建库可用 `--skip-vectors` 先同步关键词，随后普通同步补向量，留出应用和系统所需内存。
   同步与服务必须使用一致的模型环境；编码器不可用时，变化的本仍入库关键词，但会清除该本旧向量。
4. 当前没有后台向量任务队列或批处理限速参数。分块处理降低内存峰值，不能保证大库 CPU 与 I/O 对在线请求零影响。
   初次全库建库仍应在低负载时段分批进行，不承诺 10 万页在任意小机器上的完成时间。

**HTTP 搜索保护**：鉴权后按客户端 IP 分开计算关键词与语义预算；关键词突发 10 次、每秒补充 5 次，
最多并发 4 个查询；语义突发 3 次、每秒补充 1 次，最多并发 1 个查询。繁忙或超频时立即返回
`429` 与 `Retry-After: 1`，不无限排队。闲置五分钟的限流记录清理，记录总数不超过 4096。
规则覆盖所有 HTTP 调用身份；MCP 保留已有工具限频，本机 CLI 不受 HTTP 预算限制。
反向代理部署须遵循现有转发头信任配置，避免所有用户共用代理 IP 或接受伪造来源地址。

**编码进度与可用性分开**：馆长可读取 `GET /api/search/dialogue-vectors/status`，本机可运行：

```bash
vpr ocr:sync --data-dir /path/to/data --status
docker compose exec -T paper-room python -m app.ocr.sync --status
```

状态包括语义 `available`、向量 `complete`、可编码的漫画数、待建／失败／模型不匹配册数，
以及历史未核验原图的页数。`available=true` 表示已有向量可以查询，不代表 `complete=true`。
失败状态存入 SQLite，普通同步成功后清除；副文本及不足 4 字的对白不列入待编码册数。
这些全库统计仅向馆长和本机 CLI 开放，访客、机器密钥及普通搜索响应不暴露隐藏书库数量。
项目固定单 API worker，限流与并发使用本机内存，完成状态与冲突检查使用 SQLite，当前不需要 Redis。

---

## 6. 镜像构建与发布指南（Docker Hub / 镜像仓库）

纸间采用 **多阶段构建（Multi-stage Build）** 控制生产镜像体积（**生产镜像体积预算 SLO ≤ 300 MiB**；历史构建约 276 MiB，当前大小以实际构建结果为准）：

- **前端编译阶段（构建后完全丢弃）**：使用 VoidZero 官方 Vite+ 工具链镜像 `ghcr.io/voidzero-dev/vite-plus:latest` 执行前端编译（`vp install` + `vp build`），预置 `vp` 统一调度 pnpm 与 Node.js，**工具链与庞大的 `node_modules` 均不会打包进最终镜像**；
- **最终生产镜像**：基于 `python:3.14-slim`，按 `uv.lock` 安装默认运行时依赖（uv 以构建期挂载方式借用，不进镜像；装入系统解释器），并复制后端源码和前端静态成品。台词 OCR 与语义召回的推理依赖按需安装（§5.1、§5.1.2）；
- **依赖防膨胀锁顶原则**：为防范底层 C/二进制包升级突变（如 `pymupdf 2.0` 默认绑入 `onnxruntime` 与 `numpy` 导致镜像暴涨 200MB+），`pyproject.toml` 的直接依赖实施精准版本锁定（`==`），传递依赖由 `uv.lock` 全量锁死、构建以 `uv sync --locked` 复现；并通过 BuildKit 宿主机独立缓存挂载（`--mount=type=cache,target=/root/.cache/uv`）实现 wheel 缓存物理隔离，既杜绝 wheel 归档固化进最终镜像，又保障改动依赖时的极速装配（见 `docs/PITFALLS.md` #168）。

**OCR 可靠性加固对镜像的影响**：文件锁、模型状态和签名校验使用 Python 标准库，未新增默认运行时依赖。
Dockerfile 的 `uv sync --locked --no-dev --inexact` 不安装测试依赖或 `ocr` / `ocr-gpu` 组，
因此这些修改只改变后端源码层，不自动安装 `onnxruntime`、`tokenizers`、RapidOCR 或 torch。
`.dockerignore` 排除了测试、文档、虚拟环境和 `backend/data/`；模型、台词伴生资产、索引与锁文件保存于
`/app/data` 持久化卷，不计入默认镜像。主动在 Dockerfile 中安装推理依赖会增加镜像体积；
在运行中容器安装依赖会增加容器可写层占用，模型放入数据卷则增加数据卷占用。
源码字节变化不等于压缩镜像层的实际增量，发布前可用 `docker image inspect <镜像> --format '{{.Size}}'` 测量。

### 6.1 本地打包构建与测试

在包含源码的项目根目录下执行：

```bash
# 1. 本地构建生产镜像（默认打上 paper-room:latest 标签）
docker build -t paper-room:latest .

# 2. （可选）在本地快速测试运行
docker run -d \
  --name paper-room-test \
  -p 8000:8000 \
  -v ./backend/data:/app/data \
  paper-room:latest
```

### 6.2 离线导出镜像包（传输给 TrueNAS / 群晖 NAS）

若 NAS 无法直接联网拉取外部镜像，可通过 tar 包离线导入：

```bash
# 1. 在开发机将已构建的镜像导出并压缩
docker save paper-room:latest | gzip > paper-room.tar.gz

# 2. 将 paper-room.tar.gz 上传至 NAS 存储目录后，在 NAS 终端导入：
docker load -i /path/to/paper-room.tar.gz

# 3. 验证 NAS 本地镜像列表已存在
docker images | grep paper-room
```

### 6.3 推送发布至 Docker Hub / 阿里云 / GHCR 镜像仓库

后续若希望直接公开镜像让其他用户一键拉取部署，可推送到 Docker 镜像仓库：

```bash
# 1. 登录 Docker 仓库
docker login

# 2. 为镜像打上你的仓库命名空间标签（将 yourname 替换为你的 Docker Hub 用户名）
docker tag paper-room:latest yourname/paper-room:latest
docker tag paper-room:latest yourname/paper-room:v1.0.0

# 3. 推送镜像到仓库
docker push yourname/paper-room:latest
docker push yourname/paper-room:v1.0.0
```

### 6.4 他人使用公开镜像部署的方式

当镜像推送到 Docker Hub 后，其他用户无需下载源码即可一键部署：

- **TrueNAS Scale / 群晖 Web 界面**：在镜像仓库直接填 `yourname/paper-room:latest`，NAS 会全自动从云端拉取；
- **Docker CLI**：
  ```bash
  docker run -d \
    --name paper-room \
    -p 8000:8000 \
    -v /mnt/tank/comics:/app/data \
    -e COMIC_SHELF_SECRET="your_curator_password" \
    --restart unless-stopped \
    yourname/paper-room:latest
  ```
- **Docker Compose**：将 `docker-compose.yml` 中的 `build: .` 替换为 `image: yourname/paper-room:latest` 即可直接拉起。

> 💡 **私有仓库拉取提示**：若将镜像推送至个人私有镜像仓库（Private Registry）而非公开镜像，在 NAS 端拉取前需先配置认证凭据（TrueNAS 在“Apps $\rightarrow$ Manage Container Images”中添加 Docker Credentials；群晖在 Container Manager 注册表设置中勾选登录；服务器终端执行 `docker login`）。

---

## 7. 网络性能与反向代理调优（Cloudflare、HTTP/2 与缓存）

### 7.1 Cloudflare 穿透与边缘强缓存优化（解决 100KB 图片 20~30s 延迟）

如果使用 Cloudflare（含 Cloudflare Tunnel）将处于家庭宽带或国内 NAS 的纸间映射到公网：

1. **为什么直连会慢？**
   - 国内连接 Cloudflare 免费节点常被路由至美国西海岸 Anycast 节点；
   - 若 Cloudflare 判定为动态请求，每次加载都会触发跨太平洋往返回源（家庭宽带上行 + 跨洋晚高峰丢包导致 TCP 重传卡顿）。
2. **静态扩展名别名与 WebP 收敛（代码层已内置）**：
   - 纸间衍生图片与缩略图已全面显式收敛为 WebP（缩略图 `/thumbnail.webp`、封面 `/covers/{index}/file.webp` 与章节封面 `/cover.webp`；正文内页采用格式无关的 `/pages/{index}/file` 100% 保真原始源文件，同时兼容历史 `.{ext}` 静态别名）；
   - Cloudflare 及主流 CDN 看到 `.jpg` / `.webp` 会开箱自动识别为静态资源进行边缘缓存。
3. **Cloudflare Cache Rule 推荐配置（彻底杜绝跨洋穿透）**：
   - 进入 Cloudflare Dashboard → **Caching** → **Cache Rules** → 点击 **Create rule**：
     - **Rule name**: `Paper Room Media Cache`
     - **When incoming requests match...**:
       `(http.request.uri.path contains "/api/library/" and (http.request.uri.path.extension in {"webp" "jpg" "jpeg" "png" "avif" "gif"} or ends_with(http.request.uri.path, "/file") or ends_with(http.request.uri.path, "/thumbnail")))`
     - **Cache eligibility**: `Eligible for cache`
     - **Edge TTL**: `Override origin` → `1 month`（1 个月）
     - **Browser TTL**: `Respect origin headers`（遵循纸间返回的 30 天 immutable 强缓存）
   - **效果**：首位读者翻阅或后台预热完成后，所有页面原图与缩略图直接由距离读者最近的 Cloudflare 边缘节点以 **HTTP/2 或 HTTP/3 (QUIC)** 多路复用毫秒级下发，源站回源流量降至 0。

> 🛡️ **进阶零信任防护（防公网 IP 嗅探直连源站）**：
> 公网部署**必须**按 [《家庭网络部署指南》第 6.8 节](docs/HOMELAB_NETWORKING_GUIDE.md) 配置 Cloudflare Transform Rules 注入隐秘通信印章，并在 NPM 中校验，拦截绕过 Cloudflare 的直连。这不只是防扫描：失败锁按 `CF-Connecting-IP` / `X-Forwarded-For` 记账，源站能被直连，这两个头就能伪造。

### 7.2 HTTP/2 与 HTTP/3 架构分工（为什么 Uvicorn 内部打印 HTTP/1.1？）

在生产日志中若看到形如 `<网关或反代IP> - "GET ... HTTP/1.1" 200 OK`：

1. **外部与内部的分层职责**：
   - **客户端 ⇄ Cloudflare / 反代网关（外网高延迟段）**：
     - 现代浏览器访问 HTTPS 域名时，与 Cloudflare 之间**默认已自动启用 HTTP/2 或 HTTP/3 (QUIC)**；可在浏览器控制台 Network 选项卡勾选 `Protocol` 查看确认（显示 `h2` 或 `h3`）；
   - **反代网关 ⇄ 纸间容器（内网零延迟段）**：
     - Cloudflare Tunnel (`cloudflared`)、Nginx、Traefik 等反代在向上游 Python ASGI（Uvicorn）转发时，**行业标准一律走 HTTP/1.1**；
     - Uvicorn 官方不支持也不推荐在内部直接运行 HTTP/2（内网 <0.1ms 下 HTTP/1.1 Keep-Alive 连接池足以支撑极高吞吐，HTTP/2 流控在单线程 Python 运行时反而会增加 CPU framing 开销）。
2. **局域网直接访问 TrueNAS 如何开启 HTTP/2？**
   - **浏览器安全限制**：所有现代浏览器（Chrome / Firefox / Safari / Edge）**强制要求 HTTP/2 必须建立在 TLS（HTTPS）加密之上**，不支持明文 HTTP/2（h2c）；
   - 若直接通过 `http://<NAS_IP>:8000` 访问，浏览器必然协商为 HTTP/1.1；
   - **开启方法**：在 TrueNAS 上通过 Nginx Proxy Manager、Traefik 或 Caddy 前置并配置 SSL 证书，由反代开启 HTTP/2/3 对外监听 `https://...` 并转发至纸间端口。例如 Caddy 极简配置：
     ```Caddyfile
     comic.lan {
         reverse_proxy paper-room:8000
     }
     ```

### 7.3 局域网与公网分流访问（Split-Horizon DNS，内网千兆直连零延迟）

在家庭网络中，最理想的阅览体验是：**同一套域名、同一套书签，在家里自动跑千兆局域网直连（0 延迟），出门在外自动走 Cloudflare 边缘缓存**。

#### 1. 为什么推荐 Split-Horizon DNS（本地 DNS 重写）？

- **公网回流痛点**：若在家里依然通过公网 DNS 解析域名，数据包将走跨洋 Cloudflare Anycast 回流，白白浪费宽带且增加数百毫秒网络开销；
- **双域名痛点**：若在书签中保存 `http://<NAS_IP>:8000` 和公网域名两个地址，PWA 离线缓存、阅读进度（`localStorage`）与登录态无法跨源共享；
- **分流效果**：通过本地 DNS 重写，局域网内将公网域名强制解析为 TrueNAS 内网 IP（如 `<NAS_IP>`），实现局域网 0 跨洋直连秒开。

#### 2. 三种主流分流配置方式

- **方式一：AdGuard Home / Pi-hole / 路由器 DNS 重写（推荐，全家无感生效）**
  - 在家庭路由或 DNS 服务（AdGuard Home / OpenWrt / iKuai）中进入 **过滤器** → **DNS 重写**（或 Hosts 规则）：
    - **域名**: `comic.yourdomain.com`
    - **IP 地址**: `<TrueNAS 内网 IP>`
  - 全屋设备连接家庭 WiFi 时自动享受内网千兆带宽直连。

- **方式二：单机 Hosts 文件指定（极简单机测试）**
  - 在电脑 hosts 文件（Linux `/etc/hosts` 或 Windows `C:\Windows\System32\drivers\etc\hosts`）追加：
    ```text
    <NAS_IP>  comic.yourdomain.com
    ```

- **方式三：Tailscale / 私网 VPN 组网（免公网暴露，出门如在家）**
  - 在 TrueNAS 与手机/笔记本上运行 Tailscale 并启用 MagicDNS，直接通过内网私有地址通信，免去公网端口暴露。

#### 3. 内网直接解析的 SSL 证书与端口建议

- 若在外网使用标准 HTTPS（443 端口），局域网内 TrueNAS 前置的反代（Nginx / Caddy）也建议监听 443 端口并配置相同的域名证书（可通过 ACME DNS-01 验证自动申请通配符证书）；
- 这样内网直连时浏览器不会产生任何证书警告，同时直接激活 HTTP/2 多路复用。

---

## 8. PWA 与生产静态缓存防线（重要）

纸间已原生集成 PWA（渐进式 Web 应用）与 Service Worker 离线运行能力：

1. **安全上下文（HTTPS 要求）**：
   - 现代浏览器（Chrome / Safari / Edge / Firefox）规范强制要求：**Service Worker 与 PWA 安装必须在安全上下文（HTTPS 或 `localhost`）下运行**；
   - 本机开发（`localhost:8000` / `localhost:5173`）浏览器默认视为安全上下文，可直接测试安装；
   - 若部署于内网 NAS（如 `http://<NAS_IP>:8000`）或公网 VPS，建议前置反向代理（Nginx / Caddy / NPM / Cloudflare Tunnel）并配置 SSL 证书（HTTPS），方可开启独立应用安装与离线运行能力。
2. **反向代理 Cache-Control 防死锁与 SPA 路由兜底准则（PITFALLS #54, #107）**：
   - 纸间后端的 `SPAStaticFiles` 中间件已对关键入口下发了严格的防死锁标头与 SPA 路由兜底：
     - `/`、`/index.html`、`/sw.js`、`/registerSW.js`、`/manifest.webmanifest`：强制 `Cache-Control: no-cache, no-store, must-revalidate`；
     - `/assets/*`（带内容指纹静态资源）：下发 `Cache-Control: public, max-age=31536000, immutable`；
     - **前端路由 404 回退**：对客户端路由（如 `/comic/:source/:id`、`/discovery`）刷新请求在 404 时自动回退返回 `index.html`，缺失的静态文件请求（带扩展名）保持 404；
   - **反代配置致命警告（NPM 避坑）**：若使用 Nginx Proxy Manager (NPM)，在 Proxy Host 设置中**切勿勾选 `Cache Assets`**！勾选该项会无差别向所有 `.js`（包括 `/sw.js`）注入长效 `expires 7d` 强缓存头，覆盖后端的防线，导致 Cloudflare 强缓存旧 Service Worker 达数十小时，引发预缓存 404 与换届死锁；
   - **Cloudflare 边缘防护要求**：在 Cloudflare WAF 中需为 `/manifest.webmanifest`、`/sw.js` 配置 Skip 规则跳过人机质询，避免底层无界面 fetch 因触发 403 挑战而导致 PWA 清单加载失败。
3. **MIME 类型保障**：
   - 后端已在 Python 层面显式注册 `.webmanifest` 映射为 `application/manifest+json`，保障无论在何种精简 Docker 镜像或宿主机下，浏览器都能正确识别应用清单。

---

## 9. MCP（Model Context Protocol）智能体配置与连接指南

纸间原生支持 **Anthropic MCP（Model Context Protocol）** 标准规范，允许各类 AI 智能体（如 Claude Desktop、Cursor、Antigravity、飞书 Bot、本地 Agent 脚本）直接与你的个人漫画书架交互（支持检索书架藏书、全库台词全文检索、以图搜图、详情查询、跨卷章节缓存与签发单本沙箱直达链接）。

### 9.1 三种连接模式说明

| 模式                | 传输协议                | 适用部署场景                                                 | 客户端形态                                               |
| :------------------ | :---------------------- | :----------------------------------------------------------- | :------------------------------------------------------- |
| **SSE 模式**        | HTTP Server-Sent Events | **局域网 NAS（TrueNAS / 群晖 / Unraid / Docker）或远程 VPS** | 远程客户端填入 HTTP URL 链接直连                         |
| **Stdio 模式**      | 本地标准输入输出管道    | **本机开发或与 Agent 运行在同一台宿主机**                    | 客户端直接拉起 Python 脚本子进程，零网络端口暴露，最安全 |
| **Direct RPC 模式** | HTTP POST JSON-RPC 2.0  | **外部无状态自动化脚本、飞书 Bot Webhook、微服务**           | 单次 HTTP POST 立即返回，无需保持长连接                  |

---

### 9.2 局域网 NAS 部署（SSE 模式配置）

当纸间作为 Docker 容器运行在 NAS 上时，局域网内的其它电脑、客户端可通过 **SSE 链接** 连接。

#### 1. 端点地址与鉴权规则

- **免密部署**（家庭纯内网未配置 `COMIC_SHELF_SECRET`）：
  - SSE 握手链接：`http://<NAS_IP>:8000/api/mcp/sse`
- **带密码部署**（已配置 `COMIC_SHELF_SECRET`；交给智能体的是专用的 `COMIC_SHELF_MCP_TOKEN`，它只在配了 SECRET 时才生效）：
  - **方式 A（标准 Headers 鉴权，推荐）**：
    - 链接：`http://<NAS_IP>:8000/api/mcp/sse`
    - 标头：`Authorization: Bearer <COMIC_SHELF_MCP_TOKEN>`
  - **方式 B（Query 参数鉴权，适合不支持自定义 Headers 的客户端）**：
    - 链接：`http://<NAS_IP>:8000/api/mcp/sse?token=<COMIC_SHELF_MCP_TOKEN>`
    - 服务端返回的消息回传端点**只携带 `session_id`**（`/api/mcp/messages?session_id=...`），不再把凭据抄回 URL；活会话凭 `session_id` 即可续话，同样零断流。
    - uvicorn 自己的访问日志会把 `token` / `temp_token` / `session_id` 的值打码，但反代（NPM、Cloudflare 等）照记完整查询串，所以这条路**只放子凭据，绝不要放站长口令**。

#### 2. Claude Desktop 客户端配置

在你的电脑上编辑 Claude Desktop 配置文件（MacOS: `~/Library/Application Support/Claude/claude_desktop_config.json`，Windows: `%APPDATA%\Claude\claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "paper-room": {
      "url": "http://192.168.1.100:8000/api/mcp/sse",
      "headers": {
        "Authorization": "Bearer 你的COMIC_SHELF_MCP_TOKEN"
      }
    }
  }
}
```

> 💡 **提示**：若你的客户端版本暂未开放 `headers` 配置项，可直接改用带有 Query 参数的链接：
> `"url": "http://192.168.1.100:8000/api/mcp/sse?token=你的COMIC_SHELF_MCP_TOKEN"`（查询串会进反代的访问日志，务必只放子凭据）

#### 3. Cursor / 其它 MCP 客户端配置

在项目根目录创建或编辑 `.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "paper-room": {
      "url": "http://192.168.1.100:8000/api/mcp/sse",
      "headers": {
        "Authorization": "Bearer 你的COMIC_SHELF_MCP_TOKEN"
      }
    }
  }
}
```

---

### 9.3 本地开发与本机运行（Stdio 模式配置）

若你直接在本地工作站或开发机上运行 Agent，**推荐直接走 Stdio 管道通信**（无需依赖 Web Server 运行，直接读写本地 SQLite 数据库与缓存目录）：

在 `claude_desktop_config.json` 或 Agent 的配置文件中配置：

```json
{
  "mcpServers": {
    "paper-room": {
      "command": "/absolute/path/to/comic-shelf/.venv/bin/python",
      "args": ["/absolute/path/to/comic-shelf/backend/app/mcp_server.py"]
    }
  }
}
```

---

### 9.4 外部脚本与微服务（Direct HTTP RPC 模式）

若通过外部脚本或飞书机器人进行无状态调用，可直接向 `/api/mcp/rpc`（或 `/mcp`）发送标准 JSON-RPC 2.0 请求：

```bash
curl -X POST "http://<NAS_IP>:8000/api/mcp/rpc" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <COMIC_SHELF_MCP_TOKEN>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "query_shelf",
      "arguments": { "keyword": "电锯人", "limit": 5 }
    }
  }'
```

---

### 9.5 安全防护、角色分工与权限矩阵（三轨 Token 体系）

纸间在认证层实现了基于**最小特权原则（Principle of Least Privilege）**的分层三轨鉴权体系，各司其职，互不借道：

| 鉴权凭证                        | 授予角色                       | 适用场景                                             | 权限边界与安全约束                                                                                                                                                                                                                                                                                                            |
| :------------------------------ | :----------------------------- | :--------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`COMIC_SHELF_SECRET`**        | `curator`（馆长 / 超级管理员） | 馆长个人管理、本地/远程 Claude Desktop 调试          | **全站最高绝对特权**：支持全量 MCP 工具、管理后台登入、访客通行证派发/禁用、彻底删除藏书、全站配置修改。                                                                                                                                                                                                                      |
| **`COMIC_SHELF_MCP_TOKEN`**     | 仅 MCP 面通行                  | 交给外部智能体（Claude / Cursor / Bot 配置里的这把） | **只解锁 `/api/mcp` 与 MCP 工具**，碰不到任何 REST 管理端点。MCP 工具内部按馆长级取数（含对访客隐藏的本），但 `create_direct_pass` 硬拒绝为隐藏本签发公开链接。换掉这一行即可撤销已外发的钥匙（所有智能体共用这一把，换它就是全部断开）。**只在配了 `COMIC_SHELF_SECRET` 时生效**：没配 SECRET 时全站按馆长放行，它形同虚设。 |
| **`COMIC_SHELF_MACHINE_TOKEN`** | `machine`（外部机器 / 微服务） | Paper Studio 等受限创作端                            | **受限最小特权沙箱**：本地建本（`POST /api/library/local/create`）、画页上传与替换（`/upload-pages`、`/replace-pages`）；**严格禁止访问通行证名册、禁止彻底删除漫画、禁止越权修改系统密钥**。**不能开 MCP**：MCP 工具按馆长视角取料（含隐藏本台词），这把钥匙只给写库流水线用。                                               |

#### 1. 选型速查：谁该拿哪把

| 调用方                                               | 发哪把                            | 备注                                                                                          |
| :--------------------------------------------------- | :-------------------------------- | :-------------------------------------------------------------------------------------------- |
| OCR 文件提取与本机台词同步                           | 无需令牌                          | 直接读取画页 / 伴生文件及本机数据库，不经过 HTTP 或 MCP                                       |
| Paper Studio 等内网创作任务                          | `COMIC_SHELF_MACHINE_TOKEN`       | 建本与上传画页走 `POST /api/library/local/*`                                                  |
| 外部智能体（Claude / Cursor / 飞书 Bot 的 MCP 配置） | `COMIC_SHELF_MCP_TOKEN`           | 只需 MCP；它拿不到任何 REST 写端点                                                            |
| 馆长自己的浏览器                                     | `COMIC_SHELF_SECRET`              | 登录校验后签发高熵随机会话令牌（`cs_curator_<hex>`）由 HttpOnly Cookie 承载，根口令不落地存储 |
| 朋友与群友阅读                                       | 访客通行证 / `create_direct_pass` | **不是这三把里的任何一把**：限时、限单本、可单独注销                                          |

#### 2. MCP 那道门的准入名单

| `COMIC_SHELF_MCP_TOKEN` | 站长口令 | 机器密钥  | 子凭据 |
| :---------------------- | :------- | :-------- | :----- |
| 留空（默认）            | ✅       | ❌（401） | —      |
| 已设置                  | ✅       | ❌（401） | ✅     |

一句话规则：**机器密钥永远进不了 MCP**（被拒同样记一次 `mcp:<ip>` 失败）；建本、画页上传 / 替换与 `/api/search/dialogue-context` 的机器令牌权限保留；取料这条和访客一样看不到对访客隐藏的书。

三条运维红线：

1. **两把不许填同一个值**——代码不校验，同值等于两把钥匙没分家，撤销收益归零；
2. 原先拿机器密钥调 MCP 的客户端一律 401，必须换成子凭据（这是刻意的，不是 bug）；
3. **子凭据离不开站长口令**：没配 `COMIC_SHELF_SECRET` 时所有请求都按馆长放行，上表不适用。

#### 3. 泄露时换谁（撤销半径）

| 泄露的钥匙                  | 攻击面                                                     | 要动什么                                                                                       |
| :-------------------------- | :--------------------------------------------------------- | :--------------------------------------------------------------------------------------------- |
| `COMIC_SHELF_MCP_TOKEN`     | 全库可见性（含隐藏本）+ 签发达本直达链接（隐藏本已被否决） | 改一行 env + 重启 API：所有智能体一起断开、换新值重连；NAS 流水线与站长登录**毫无感觉**        |
| `COMIC_SHELF_MACHINE_TOKEN` | 往库里写东西 + 读（进不了 MCP）                            | 换它要连所有挂载该值的脚本、Bot、定时任务一起改，并逐个重启                                    |
| `COMIC_SHELF_SECRET`        | 全站：删本、通行证名册、系统配置                           | 全站重登。改密后运行态基于口令摘要指纹瞬时阻断并物理抹除所有旧会话令牌，外部智能体绝不该拿到它 |

- **为什么 MCP 不能算"最小特权"通道？** MCP 工具的取数视角天生是馆长级（要能命中隐藏本、要读个人收藏与阅读进度来排序），所以只能靠"另发一把可单独撤销的钥匙"来缩小泄露后果，而不是靠削减工具能力——后者会让智能体连本该查的东西都查不到。
- **连接池过载防护**：SSE 活跃会话设上限 `_MAX_MCP_SESSIONS = 50`，超限自动返回 429，防止客户端异常断连泄漏连接池。`/api/mcp/rpc` 是无状态的单次调用，不占会话，也不受这条上限约束。
- **已收口的几条**：
  - SSE 握手不再把调用方凭据抄进 `/api/mcp/messages` 的 URL，活会话凭 `session_id` 续话。认不出的 `session_id` 直接 404，不验凭据也不计失败：服务一重启旧会话号全部作废，客户端重连即可。
  - MCP 鉴权失败与 `/api/auth/login` 同一套规则（60 秒窗口内 10 次失败锁 5 分钟），但单独记在 `mcp:<ip>` 键下，配错凭据的智能体不会连带锁死同 IP 的馆长网页登录。任何登录成功（包括 MCP 鉴权成功）都不再清零计数，免得有人用自己手里的直达票据或 MCP 凭据反复清零、对口令无限试下去。
  - 普通 `/api/*` 接口同样计数：带了凭据却对不上任何身份就记一次失败，与 `/api/auth/login` 共用同一个 IP 计数；锁住的 IP 带任何凭据都回 429，连正确口令也不例外。**同一个错误凭据在 60 秒窗口内只计一次**（登录、`/api/*`、MCP 三处同一规则），所以改了馆长口令后，旧 Cookie 或前端存着的旧口令随每个请求重放也不会锁 IP，旧浏览器只会被要求重新登录；换着值猜仍逐个计数。401 还会顺手清掉失效的登录 Cookie。
  - uvicorn 访问日志里 `token` / `temp_token` / `session_id` 的值一律打码。
  - 工具与资源的处理器丢进线程池执行：一次慢调用（识图 10 秒超时、SQLite、向量运算）不会卡住事件循环和所有 SSE。
- **仍然存在的敞口**：
  - 入站请求仍接受 `?token=`（`extract_token` 第 4 档，为不支持自定义 Headers 的客户端保留）。uvicorn 日志已打码，反代日志照记，所以只放子凭据；要彻底堵掉，得让 MCP 只从请求头取凭据，等确认自用客户端都支持自定义 Headers 再做。
  - stdio 通道（`python3 backend/app/mcp_server.py`）零鉴权，属"能 spawn 即馆长"的本机设计。
  - MCP 工具调用没有独立频控：线程池只解决"一次慢调用卡住全站"，不限次数，大量并发检索仍会与书架请求抢同一份 SQLite 连接。
  - 失败锁按客户端 IP 记账，公网部署必须配 HOMELAB 6.8 回源印章，否则来源 IP 可以伪造（见 §3.1 `COMIC_SHELF_TRUST_FORWARDED_HEADERS`）。

---

### 9.6 浏览器端 WebMCP（Chrome 原生视口控制）与局域网安全上下文（Secure Context）配置

纸间前端基于 VueUse 15 `useWebMCP` 规范接入 Chrome 浏览器级 `document.modelContext`。由于 Model Context API 属于 Chromium 体系中的 **高权限特性（Powerful Feature）**，W3C 规范强制要求其必须在**安全上下文（`window.isSecureContext === true`）**下运行：

#### 1. 为什么 `localhost` 正常而局域网 IP 不显示？

- `http://localhost:*` 与 `http://127.0.0.1:*` 被浏览器判定为本地回环（Loopback），天然满足 `isSecureContext = true`，因此在开发本机打开时 WebMCP 工具正常生效；
- `http://192.168.x.x:*` 等局域网纯 HTTP 地址会被 Chromium 强制判定为非安全上下文（`isSecureContext = false`），在此状态下浏览器会**主动隐藏或将 `document.modelContext` 置为 `undefined`**，导致工具无法注册。

#### 2. 局域网调试临时放行方案（Chrome Flag）

若在局域网其它电脑或手机上通过 IP 访问并调试 WebMCP，可使用 Chrome 内置白名单机制：

1. 在访问端 Chrome 浏览器地址栏输入并回车：
   `chrome://flags/#unsafely-treat-insecure-origin-as-secure`
2. 在 **Insecure origins treated as secure** 输入框中填入你的局域网地址（例如 `http://192.168.1.100:5173` 或 `http://192.168.1.100:8000`，多个地址用英文逗号分隔）；
3. 将右侧下拉框切换为 **`Enabled`**；
4. 点击右下角 **`Relaunch`** 重启 Chrome。
5. 重启后刷新纸间页面，`window.isSecureContext` 即变为 `true`，WebMCP 工具将正常注册并在浏览器 AI 扩展中就绪可用。

#### 3. 生产终极方案（泛域名 HTTPS）

在家庭私有云部署中，建议参考 [`docs/HOMELAB_NETWORKING_GUIDE.md`](docs/HOMELAB_NETWORKING_GUIDE.md)，通过 Nginx Proxy Manager 或 Cloudflare 配置泛域名 SSL 证书并使用 HTTPS（如 `https://comic.yourdomain.com`）访问，局域网与公网设备均天然满足安全上下文，无需任何客户端配置。

#### 4. WebMCP 角色与功能权限（馆长 vs 访客）

纸间对浏览器端 WebMCP 工具同样进行了安全分层：

- **馆长与普通访客可用**：阅读器视口控制（跳页、步进翻页、排版/分屏/日漫方向切换、画面自适应、自动翻页、对白气泡呼吸高亮、跨话切章）与只读检索（书架多维筛选、台词全文检索、以图搜图、随机淘书、榜单浏览）。单本直达会话关闭全部 WebMCP 工具注册，仅通过受限阅读界面操作。
- **馆长专属（Curator Only）**：远端/本地漫画收录（`shelf_import_comic` / `discovery_ingest_comic`）、全本/单话离线预缓存下载（`detail_cache_all_pages` / `detail_cache_chapter`）。对于访客会话，前端在注册层直接掐断（`undefined` 不注册进 `document.modelContext`，浏览器 AI Agent 零感知零污染）；若直接向后端 API 发起未授权写入，后端安全中间件将严格执行 403 权限阻断。

---

## 10. 和 Vite+ / vp 的关系说明

仓库已全面迁移至 Vite+：

- `package.json` 使用 `vite-plus` 与 `vite` override；
- `Dockerfile` 前端构建阶段使用官方 `ghcr.io/voidzero-dev/vite-plus` 镜像并直接调用 `vp build`；
- Docker 运行时环境（Stage 2）仅含 Python 3.14 纯后端与静态前端产物，无需额外安装 `vp` CLI。

## 11. 本地书库的并发与故障恢复边界

API 启动器 `backend/server.py` 固定使用一个工作进程，不提供进程数配置。应用启动时还会对书库目录加排他文件锁（`library/.writer.lock`），直接运行多个 Uvicorn worker 或多个容器挂载同一书库会在启动阶段失败。请求线程、下载并发和 OCR 工作线程仍可并发执行。

旧配置 `COMIC_SHELF_WORKERS` 已移除，残留值不影响启动；`WEB_CONCURRENCY` 也不会覆盖固定值。旧启动命令中的 `--workers` 会报未知参数，需要删除。开发热重载仍可使用，它的监控进程不等于多个 API worker 同时写库。

| 场景                                           | 当前保障                                                                                                                                                       |
| :--------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 远端刷新                                       | 保留本地 `hidden_from_guest` 隐藏设置。已重新装订的画卷不会被远端页表覆盖。                                                                                    |
| 下载期间刷新、重新装订或删除                   | 提交原图前在漫画锁内复核画卷状态；过期下载取消，不覆盖现有画页，不重建已删除漫画。                                                                             |
| 读取计数、缓存校验、从 `raw.chapters` 重建目录 | 只修正内存结果，不因这些修正要求磁盘写权限；需要实际解密或移动图片的旧数据迁移仍涉及写入。                                                                     |
| `save_fetched` 保存两份 JSON、升级平铺目录     | 保存旧元数据副本；可捕获的异常触发 JSON 与本次移动文件的回退。回退也可能因存储故障失败。                                                                       |
| 重新装订、暂存 PDF 建卷                        | 旧画页目录先放进 `library/.work/.save-*`，再切到新目录；进程内失败和启动恢复都会连 JSON 一起还原。                                                             |
| 追加画页 / PDF 加话                            | `save_fetched(refresh=False)` 写入新页表。崩溃可能多几个未引用文件，不扫整库去清。                                                                             |
| 删除整本                                       | 先改名进 `library/.work/.deleted-*` 再删除；启动时清掉改名残留。                                                                                               |
| 多实例、断电、强杀进程                         | 启动时对 `library/.writer.lock` 加排他锁。中断的保存若留在 `library/.work/.save-*` 且带 `.in-progress`，启动时恢复上一份 JSON 和装订前画页。不是完整崩溃事务。 |

工作残留统一放在 `library/.work/`，漫画目录只留正片。`.save-<随机编号>/` 默认只备份该次保存前存在的 `album.json` 与 `remote.json`，并用 `comic.rel` 指向所属漫画。重新装订和暂存 PDF 建卷还会把被替换的画页目录放进备份里的 `replaced/`。这不是 SQLite、封面或缩略图的完整备份。进行中的保存带 `.in-progress` 标记：启动时据此把上一份 JSON **复制**回去（不搬走备份）；若有 `replaced.rel`，连旧画页一起还原，否则只把误迁入章节目录的平铺文件搬回去。复制完成后再删除备份。标记已去掉的残留目录视为保存完成，启动时删除。回退或恢复失败会留下带标记的目录，并让启动失败，下次再试。首次保存原本没有 JSON 时，启动会清掉半成品目录。

发现残留备份时，先停止 API，保留漫画目录和 `library/.work` 的副本，再对照日志、当前 JSON 与实际画页路径核对。不要直接批量覆盖或删除。涉及画页内容缺失时优先使用整库快照恢复。

删除章节在写元数据阶段与刷新共用这套备份。路径 PDF 首次导入把画页直接写入目标目录后再 `save_fetched`，中途崩溃按首次保存处理（半成品会被清掉），不把半套图片装成一本。启动只 `iterdir` `library/.work`，不遍历漫画目录或 `pages/`。追加产生的未引用画页、封面/缩略图、原子写留下的 `.*.tmp.*` 不扫。单机 Docker 或日后单台 Mac mini 都适用这套边界；不引入 WAL 或跨文件事务，重要书库以 Time Machine 或 NAS 快照为耐久底线。

针对性验证：`vpr test:py storage_metadata server_workers replace_pages` 覆盖刷新权限保留、旧下载失效、保存失败回退、回退失败备份保留、启动恢复可重试、恢复失败阻止启动、重新装订还原、第二次追加页表、删除残留清理、首次保存中断清目录、`.work` 临时目录清理、固定单 worker。它不替代真实 NAS/SMB 断电测试，也不覆盖追加未引用文件、封面/缩略图/decode 中途崩溃。
