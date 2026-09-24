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
# 1. （可选）若公网部署需设置密码，可直接编辑 docker-compose.yml 中的 environment：
#    取消注释 COMIC_SHELF_SECRET: '你的管理密码'
#    若为纯内网家庭环境，无需任何修改！

# 2. 一键构建并启动双容器（包含主服务与识图 Sidecar）
docker compose up -d --build

# 3. 浏览器访问
# 打开 http://<你的NAS或服务器IP>:8000
```

Compose 会同时拉起纸间核心服务（`:8000`）与本地识图引擎 `imsearch`（`:8765`）。

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

| 场景需求                   | 终端执行命令                                | 说明                                                                                                     |
| :------------------------- | :------------------------------------------ | :------------------------------------------------------------------------------------------------------- |
| **仅启动主容器（免搜图）** | `docker compose up -d --no-deps paper-room` | **加 `--no-deps` 忽略依赖**，不拉起 imsearch，防 132 报错                                                |
| **启动全部容器**           | `docker compose up -d`                      | 适用于带 AVX2 机器，同时拉起主程序与以图搜图                                                             |
| **安全停止全部服务**       | `docker compose down`                       | 停止并移除容器与内部网络，存储卷数据 100% 安全保留                                                       |
| **暂停容器运行**           | `docker compose stop`                       | 仅暂停容器不删除，后续 `docker compose start` 可秒级恢复                                                 |
| **单独停掉以图搜图**       | `docker compose stop imsearch`              | 解决由于硬件缺少 AVX2 导致容器反复崩溃报错 132 的问题                                                    |
| **查看运行状态**           | `docker compose ps`                         | 查看容器状态（`Up` 为正常运行）                                                                          |
| **代码更新后重启**         | `docker compose up -d --build paper-room`   | 自动命中缓存，仅需 2~3 秒增量编译平滑重启（内置 BuildKit pnpm/pip 宿主机缓存挂载，依赖变更亦免重复下载） |

---

## 3. 环境变量参数配置字典

> **关于环境变量注入**：
>
> - Docker 容器部署**完全不需要** `.env` 文件（`.env` 也不会提交到代码仓库）。
> - 你可以通过以下任一标准方式配置环境变量：
>   1. **Docker Compose**：直接在 `docker-compose.yml` 的 `environment` 节修改或取消注释；
>   2. **NAS Web 图形界面（TrueNAS / 群晖 / Portainer）**：在应用的“环境变量”设置表单中填入 Key 与 Value；
>   3. **Docker 命令行**：启动时增加 `-e KEY="value"` 参数；
>   4. （可选）本地开发或习惯使用 dotenv 的用户，可参考根目录 [`.env.example`](.env.example) 模版查阅参数说明。

### 3.1 核心权限与安全配置（必看）

| 环境变量                                | 必填等级                     | 默认值                                        | 说明                                                                                                                                                                                                                                                                                                                                                                     |
| :-------------------------------------- | :--------------------------- | :-------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `COMIC_SHELF_SECRET`                    | 🔴 **公网必设** / 内网免密   | _(留空)_                                      | **馆长访问口令**。留空则为局域网免密模式；公网或多用户部署强烈建议设置。输入此口令后获得全站收录、编辑元数据、删除、全量缓存等全部读写管理权限。                                                                                                                                                                                                                         |
| `COMIC_SHELF_MACHINE_TOKEN`             | ⚪ **局域网应用/Bot可选**    | _(留空)_                                      | **内网机器与自动化专用密钥 (Machine API Token)**。供局域网内其他应用（飞书 Bot、OCR 流水线、微服务等）通过 `X-Machine-Token` 或 Bearer Token 调用 REST API 与入库同步，与网页端馆长密码完全解耦互不干扰。这把密钥**不能开 MCP**（MCP 只认馆长口令与 `COMIC_SHELF_MCP_TOKEN`）。                                                                                          |
| `COMIC_SHELF_MCP_TOKEN`                 | ⚪ **接外部智能体时建议设**  | _(留空)_                                      | **MCP 子凭据**：只解锁 `/api/mcp` 与 MCP 工具，交给 Claude/Cursor/Bot 后可随时换掉，不牵连站长登录与 OCR 流水线。不设时 MCP 只认馆长口令。MCP 工具仍是馆长级可见（含对访客隐藏的本），但 `create_direct_pass` 拒绝为隐藏本签发公开链接。                                                                                                                                 |
| `COMIC_SHELF_ALLOWED_DIRS`              | 🔵 **直扫NAS外部目录时必设** | _(留空)_                                      | **允许从服务器本地路径扫描导入的额外根目录白名单**（安全沙箱放行）。用于将 NAS 现有图库目录或挂载盘快速录入纸间。多个路径在 Linux/macOS 使用冒号 `:` 分隔，Windows 使用分号 `;` 分隔（例：`/mnt/tank/comics:/mnt/media/downloads`）。                                                                                                                                    |
| `COMIC_SHELF_ENABLE_HOTLINK_PROTECTION` | ⚪ **默认已开启**            | `true`                                        | **图片防盗链保护**。基于现代浏览器 `Sec-Fetch-Site: cross-site` 与 `Referer` 拦截，彻底杜绝外站把纸间当图床跨站盗图。                                                                                                                                                                                                                                                    |
| `COMIC_SHELF_TRUST_FORWARDED_HEADERS`   | ⚪ **默认已开启**            | `true`                                        | **反向代理 IP 请求头信任**。控制是否解析 `X-Forwarded-For`、`X-Real-IP` 等请求头确定客户端 IP。经由 Nginx/Cloudflare/Caddy 反代部署时保持 `true`，且公网部署必须配好 [HOMELAB 6.8 回源印章](docs/HOMELAB_NETWORKING_GUIDE.md)，否则能直连源站的人可以伪造这些头，绕过登录与 MCP 的失败锁；若直接将 Uvicorn 裸端口暴露于公网且无前端代理，建议设为 `false` 防范 IP 伪造。 |
| `COMIC_SHELF_EMBED_DIR`                 | ⚪ **装语义检索时可选**      | `<COMIC_SHELF_DATA>/models/bge-small-zh-v1.5` | **台词语义检索的模型目录**（放 `model.onnx` 与 `tokenizer.json`，文件名不变）。目录里没有模型时语义出口返回 `encoder_unavailable`，关键词检索不受影响。安装见 §5.1.2。                                                                                                                                                                                                   |
| `COMIC_SHELF_COOKIE_NAME`               | ⚪ **可选自定义**            | `comic_shelf_token`                           | **通行证 Cookie 键名**。支持自定义 Cookie 名称（如 `my_vault_token`），彻底隐匿开源默认键名，配合 Cloudflare WAF 与单本沙箱 `temp_token` 实现高强度私有免检与零裂图秒开（详见 `docs/HOMELAB_NETWORKING_GUIDE.md` §6.6 与 §6.7）。                                                                                                                                        |
| `COMIC_SHELF_DEVICE_COOKIE_NAME`        | ⚪ **可选自定义**            | `comic_shelf_device`                          | **设备认证 Cookie 键名**。支持自定义设备 Cookie 名称（如 `my_vault_device`），配合 Cloudflare WAF 规则实现免检通行。                                                                                                                                                                                                                                                     |

### 3.2 基础服务与持久化配置

| 环境变量                   | 默认值                  | 说明                                                                                                                                    |
| :------------------------- | :---------------------- | :-------------------------------------------------------------------------------------------------------------------------------------- |
| `COMIC_SHELF_DATA`         | `backend/data`          | 数据根目录。Docker 容器内固定为 `/app/data`。所有已下载漫画、封面、元数据、访客与进度数据库（`comic_shelf.db`）与索引均保存在此目录下。 |
| `COMIC_SHELF_HOST`         | `127.0.0.1`             | 服务绑定地址。Docker 容器内已配置为 `0.0.0.0`。                                                                                         |
| `COMIC_SHELF_PORT`         | `8000`                  | 服务监听端口。可在 Compose 中将宿主机端口任意映射（如 `8080:8000`）。                                                                   |
| `COMIC_SHELF_IMSEARCH_URL` | `http://localhost:8765` | 局部特征识图 Sidecar 服务地址。Docker Compose 内部网络已配置为 `http://imsearch:8765`。                                                 |
| `COMIC_SHELF_ENABLE_DOCS`  | `false`                 | 是否开放 FastAPI 交互式 API 文档页面（`/docs` 与 `/redoc`）。公网环境建议保持 `false`。                                                 |

### 3.3 性能调优与并发控制（低配 NAS / 进阶调优）

API 工作进程数固定为 1，不属于可调参数；这里的下载与缩略图并发均在同一 API 进程内协调。运行约束见 [并发与故障恢复边界](#11-本地书库的并发与故障恢复边界)。

| 环境变量                               | 默认值 | 说明                                                                                                                                                          |
| :------------------------------------- | :----- | :------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `COMIC_SHELF_MAX_CONCURRENT_DOWNLOADS` | `3`    | **远端图片下载并发数**。JM 官方 CDN 对高并发极为敏感，建议维持在 `2`~`4`，避免触发风控或请求超时。                                                            |
| `COMIC_SHELF_THUMB_CONCURRENCY`        | `4`    | **缩略图处理并发门禁**。限制同时进行 Pillow 转换的 CPU worker 线程数。在单核/双核低配 NAS（如 J1900、ARM 盒子）上建议设为 `1` 或 `2`，防止冷访问时 CPU 跑满。 |
| `COMIC_SHELF_MAX_PREFETCH`             | `600`  | **单批次预缓存画页上限**，保护磁盘与网络。超长漫画每次点击“缓存全部”会自动顺延下载未缓存的前 N 页，直至全部完成。                                             |
| `COMIC_SHELF_PAGE_THUMB_WIDTH`         | `360`  | 详情页与子章节网格缩略图宽度（px）。                                                                                                                          |
| `COMIC_SHELF_PAGE_THUMB_QUALITY`       | `78`   | 缩略图 JPEG 压缩质量（兼顾清晰度与微秒级传输）。                                                                                                              |
| `COMIC_SHELF_COVER_WIDTH`              | `720`  | 书架与详情页大封面宽度（px，默认 720 完美匹配 2x 视网膜高清度）。                                                                                             |
| `COMIC_SHELF_COVER_THUMB_WIDTH`        | `360`  | 书架阶梯封面 1x 缩略图宽度（px，默认 360 配合 HTML5 srcset 降低低密设备内存开销）。                                                                           |
| `COMIC_SHELF_COVER_QUALITY`            | `80`   | 大封面 JPEG 质量（默认 80 兼顾微秒级传输与典藏画质）。                                                                                                        |
| `COMIC_SHELF_COVER_COUNT`              | `4`    | 每本漫画默认生成的封面预览张数。                                                                                                                              |
| `COMIC_SHELF_LOG_LEVEL`                | `info` | 后端运行日志级别（可选 `debug`, `info`, `warning`, `error`）。                                                                                                |
| `COMIC_SHELF_ACCESS_LOG`               | `true` | 是否开启 Uvicorn 请求访问日志。默认已内置高频探针静音过滤（`/api/health` 与搜图状态 200 正常时不输出）；若需彻底关闭访问日志可设为 `false`。                  |

### 3.4 哔咔漫画（PicAcg Provider）配置（可选）

| 环境变量                  | 必填等级                  | 默认值                           | 说明                                                                                                            |
| :------------------------ | :------------------------ | :------------------------------- | :-------------------------------------------------------------------------------------------------------------- |
| `PICA_EMAIL`              | ⚪ **可选（收录哔咔设）** | _(留空)_                         | **哔咔漫画登录账号/邮箱**。后端自动使用官方 HMAC-SHA256 签名算法生成签名并长效保持 JWT 会话，前端 0 手动输入。  |
| `PICA_PASSWORD`           | ⚪ **可选（收录哔咔设）** | _(留空)_                         | **哔咔漫画登录密码**。与账号配合自动登录。                                                                      |
| `PICA_PROXY`              | ⚪ **可选（网络代理）**   | _(留空)_                         | **HTTP / SOCKS5 代理地址**（如 `http://192.168.1.10:7890`）。用于突破大陆网络对哔咔 API 及分流 CDN 的连接阻断。 |
| `PICA_API_URL`            | ⚪ **可选自定义**         | `https://picaapi.picacomic.com/` | 哔咔官方移动端 REST API 入口，支持切换自建或第三方反代镜像。                                                    |
| `PICA_EXTRA_CDN_HOSTS`    | ⚪ **可选自定义**         | _(留空)_                         | **额外分流 CDN 域名白名单**（英文逗号分隔）。用于局域网自建反代缓存或特定网络镜像 CDN 节点放行。                |
| `PICA_DOWNLOAD_PACING_MS` | ⚪ **可选自定义**         | `250`                            | **哔咔画页批量下载平滑微休眠**（毫秒，内置 ±20% 拟人化抖动）。设为 `0` 可完全关闭节流。                         |
| `PICA_API_PACING_MS`      | ⚪ **可选自定义**         | `150`                            | **哔咔多分卷元数据 API 请求间隔**（毫秒）。在解析多章节时防止突发并发请求冲击官方接口。设为 `0` 可关闭。        |

### 3.5 禁漫天堂（JMComic Provider）配置（可选）

| 环境变量              | 必填等级                  | 默认值   | 说明                                                                                                                    |
| :-------------------- | :------------------------ | :------- | :---------------------------------------------------------------------------------------------------------------------- |
| `JM_USERNAME`         | ⚪ **可选（收录禁漫设）** | _(留空)_ | **禁漫天堂登录账号/用户名**。配置后自动登录换取 `AVS` 凭据，用于解析需登录查看的受限漫画车号；留空则以匿名模式抓取。    |
| `JM_PASSWORD`         | ⚪ **可选（收录禁漫设）** | _(留空)_ | **禁漫天堂登录密码**。与账号配合自动登录，会话持久化于 `backend/data/jm_session.json` 并支持自愈重登。                  |
| `JM_PROXY`            | ⚪ **可选（网络代理）**   | _(留空)_ | **控制流代理地址**（支持 HTTP / SOCKS5，如 `http://127.0.0.1:7890`）。用于域名嗅探、动态域名更新、HTML 页面与登录认证。 |
| `JM_IMAGE_PROXY_MODE` | ⚪ **可选分流策略**       | `auto`   | **画页大图下载代理模式**。`auto`（跟随 `JM_PROXY`）、`direct`（强制直连省流量）。                                       |

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

项目内置了专用运维脚本 `scripts/imsearch.sh`（支持 `pnpm imsearch` 触发，自动智能探测 `/mnt/nas_manga` 挂载点）：

| 操作目标         | 推荐执行命令            | 说明                                                      |
| :--------------- | :---------------------- | :-------------------------------------------------------- |
| **启动后台服务** | `pnpm imsearch start`   | 监听 `0.0.0.0:8765` 端口，后台常驻运行并自动健康探测      |
| **停止服务**     | `pnpm imsearch stop`    | 优雅终止运行中的 imsearch 进程                            |
| **重启服务**     | `pnpm imsearch restart` | 平滑重启以加载最新索引                                    |
| **查看运行状态** | `pnpm imsearch status`  | 查看运行状态、PID、端口、内存占用与健康度                 |
| **日常增量更新** | `pnpm imsearch reindex` | 扫描 NAS 新图提取特征、追加倒排索引并自动重启服务（秒级） |
| **全量重置重训** | `pnpm imsearch train`   | 重新训练 512 聚类中心并彻底重建索引库                     |
| **查看实时日志** | `pnpm imsearch logs`    | 跟踪查看实时搜索日志（`Ctrl+C` 退出）                     |

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
├── jm_session.json             # 禁漫 AVS 会话凭据（0o600 私有安全权限，7 天有效）
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

纸间支持 **“高性能算力机提取 OCR + 低功耗 NAS 存储与服务”** 的算存分离架构（Compute-Storage Decoupling）。
高性能电脑（带 GPU/多核 CPU）通过挂载 `/mnt/nas_manga` 跑 OCR 并生成伴生文件 `{index}.ocr.json`，处理完成后通知 NAS 更新 `comic_dialogues.db` 中的 SQLite FTS5 索引：

1. **高性能机一键状态巡检与依赖安装**（**默认即 GPU**，不需要记 `--gpu`）：

   ```bash
   # 巡检：OCR 伴生覆盖率 + 宿主显卡 + 本轮默认算力线 + 两条线各自的"会话级"实际推理设备 + FTS5 条目
   pnpm ocr status              # 等价于 bash scripts/ocr.sh status

   # 装依赖：检测到 NVIDIA 显卡 → 在项目内建 .venv-ocr/（已 gitignore，约 1.7GB）并装 GPU 栈；
   # 没检测到卡 → 只往应用 .venv 里装 CPU 依赖。装完 GPU 环境后，run/test/status 自动优先用它。
   bash scripts/ocr.sh install
   # 明确只要 CPU（无卡机、或与宿主争卡时）：
   bash scripts/ocr.sh install --cpu
   # 环境想放到别处（外置盘/NAS 挂载）：COMIC_SHELF_OCR_VENV=/path/to/env bash scripts/ocr.sh install
   ```

   回落是**显式**的：`.venv-ocr` 不存在时 `run` 会打一行 `⚠️ 检测到宿主有 NVIDIA 显卡，但 GPU 算力环境
未创建，本轮按 CPU 跑` 并给出建环境的命令；`--gpu` 时环境缺失直接拒绝（exit 1）。环境在、但 Det/Cls/Rec 三段会话里有一段没跑在 CUDA 上（CPU 版 `onnxruntime` 覆盖了 GPU 版，或 `LD_LIBRARY_PATH` 没挂上 venv 内的 CUDA 库），`build_engine` 也会当场报错退出，绝不静默降级。

   > ⚠️ **不要**手动把 `onnxruntime-gpu` 与 CPU 版 `onnxruntime` 混装进同一个环境：两个 wheel
   > 共用 `site-packages/onnxruntime/` 目录，覆盖安装会留下混合文件，`get_available_providers()`
   > 照样列出 CUDA 但推理静默退回 CPU。`install` 已按"先删目录再装 GPU 版"的顺序处理，
   > 原理与实测数据见 `docs/PITFALLS.md` #137。

2. **高性能机批量提取 OCR 伴生文件并通知 NAS**：

   ```bash
   # 默认就走 GPU（v6 实测 94 页/分），推荐把线程数给到 4：
   pnpm ocr run --source jm --workers 4

   # 强制回落应用的 CPU 线：
   bash scripts/ocr.sh run --cpu --source jm

   # 批量对指定漫画跑 OCR，并在完成后自动通过 API 通知远程 NAS 入库：
   bash scripts/ocr.sh run --source jm --id 1059521 --api-url http://192.168.1.100:8000 --token "你的MachineToken"

   # 全库扫描处理（自动跳过已有伴生文件的画页，支持 --limit 限定册数）：
   bash scripts/ocr.sh run --limit 10 --api-url http://192.168.1.100:8000 --token "你的MachineToken"
   ```

   > `--workers` 在 CPU 线上**不要超过 2**：单个引擎内部已吃满多核，加线程只是在抢核。v6 的同页对照
   > （`jm/1249304` 全 153 页，两点差法扣掉模型加载，走 `ocr.sh lines` 离线 harness）：
   > CPU 2 线程 **37.3 页/分**、4 线程反而掉到 **32.4 页/分**，GPU 4 线程 **239 页/分**（GPU:CPU ≈ 6:1）。
   > 而全库异构 1764 页走 `ocr.sh run`（含写盘、分辨率更高：全库中位 √面积 1430px vs 这本 1152px）
   > 实测约 94 页/分——**两个口径不许互相冒充**，估算成本按"要跑的那批页长什么样"选。
   > 复测请走 `bash scripts/ocr.sh lines ...`：直接 `.venv-ocr/bin/python scripts/ocr_lines.py --gpu`
   > 会漏掉 `LD_LIBRARY_PATH`，`libcublasLt.so.13` 找不到时会话退回 CPU。以前这一步是静默的，量出来的
   > "GPU"和 CPU 同带（实测踩过，见 `docs/PITFALLS.md` #137）；现在 `build_engine(True)` 会当场报错。

   **引擎只剩一条线：`rapidocr` 3.x + PP-OCRv6 small**（官方列明该单模型覆盖简中/繁中/日文，
   `tiny` 不含日文所以必须用 `small`）。旧的 v3 轨道（`rapidocr-onnxruntime`）已整体删除：它
   6623 字的字符表里**只有 5 个假名**，日文与繁体常被强行写成"形似汉字的乱码"（`這` → `遣`、
   `歡` 直接丢），只要那条路还开着，"忘了带参数"就能把乱码灌进语料且无人察觉。切换的实测收益
   （真库单本 `jm/319445` 全 22 页）：字数 **+24.7%**（1083 → 1351）、假名 2 → 48；GPU 4 线程
   94 页/分（v3 同机 129 页/分），全库 1764 页跑一轮约 19 分钟。历史 v3 侧车仍然合法，
   `engine_track` 字段留着做溯源。

   改气泡聚类判据之前，先用离线实验台（推理只跑一次，之后本地迭代，绝不写 `backend/data`）：

   ```bash
   # 1) dump 指定画页的原始识别行到 /tmp/paper-room-ocr-lines
   bash scripts/ocr.sh lines --source jm --id 319445 --pages 10 --out /tmp/prl
   # 2) 改完 scripts/ocr_worker.py 的 cluster_blocks 后，不跑推理直接量效果：
   #    打印气泡数 / 字数 / 气泡面积分布 / 疑似误并清单
   bash scripts/ocr.sh lines --recluster /tmp/prl
   ```

   判据落地后要覆盖现网侧车就 `bash scripts/ocr.sh run --source jm --id <id> --force`，
   随后 `bash scripts/ocr.sh sync` 重灌索引。侧车里的 `engine: rapidocr` 是
   `is_valid_ocr_sidecar` 的合法性标记，改不得——改了会让新侧车被当成脏缓存无限重提。

3. **宿主机 / NAS 终端一键增量同步已存在的伴生文件**：

   ```bash
   # 全库增量同步（智能感知 /mnt/nas_manga 或 COMIC_SHELF_DATA）：
   pnpm ocr:sync
   # 或指定单本：
   python3 scripts/sync_ocr.py --source jm --id 1059521
   ```

4. **单张画页快速测试与气泡聚类预览**：
   ```bash
   bash scripts/ocr.sh test /path/to/page.webp          # 默认走 GPU 环境
   bash scripts/ocr.sh test --cpu /path/to/page.webp    # 强制用应用 CPU 环境做对照
   ```
   `test` 与 `run` 用同一套引擎构造与聚类，只打印、不写盘。要看"GPU 到底有没有生效"用 `bash scripts/ocr.sh status`
   （真建一次引擎，Det/Cls/Rec 三段会话任一不在 CUDA 上就报出来）；GPU 用不上时 `run` / `test` / `lines` 都会当场报错，而不是静默按 CPU 跑。

#### 5.1.1 PDF 扉页自动分话：按 ADR 0024 保持**可选**，默认不装

上面整套流水线的前提是**算存分离**：NAS 容器不做法向推理，只收 `{index}.ocr.json` 并重建 SQLite FTS5。
`backend/app/storage/pdf.py::_extract_chapters_from_ocr`（导入 PDF 且**没有**电子书签时的第二轨分话探测）
按 ADR 0024 的口径是"该包属可选依赖，未安装时本轨自动跳过"，因此 `rapidocr` **不在** `backend/requirements.txt` 里，
别顺手加进来——它只服务"无书签 PDF 要自动切话"这一件事，代价是镜像多 33MB（PP-OCRv6 的三个 `.onnx` 就在包里，
不需要联网下模型）。

缺它时的行为：该 PDF 平铺成单章，导入照常完成，日志打一行 **WARNING**「跳过 PDF 扉页自动分话」。
（这里必须是 warning：uvicorn 默认不给 root logger 设级别，info 会被整条丢掉，就变成"没人知道为什么没有话目录"。）

经常在 NAS 上导入无书签 PDF、想要自动分话的话，要补两个包：`rapidocr` 3.x 不自带推理后端，得另装 CPU 版 `onnxruntime`（已按 §5.1.2 装过语义腿的，这个包已经在了，只补 `rapidocr`）：

```bash
# backend/requirements.txt 追加：
rapidocr>=3.9.2
onnxruntime>=1.20
```

#### 5.1.2 语义检索「按意思找台词」（可选能力，默认不启用）

台词检索有两条腿：FTS5 关键词（默认就有，简繁字形无关）与向量语义（要自己装两步）。
语义这条腿解决**字面完全不通**的查询——搜「告白」拿到「我喜欢你」、搜「脸红」拿到「满脸通红」。
为什么做成独立出口、不与关键词混排，见 ADR 0028。

它不进 `backend/requirements.txt`：为了一句问题的在线编码（2ms）要每台机器多背约 70MB，
而模型文件本身还得单独放一次。不装就是没有这条腿，其余功能一律不受影响。

| 项目           | 实测值（真库 6254 条向量 / 512 维，CPU）                                                                                                                                                                               |
| :------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 运行时         | `onnxruntime`(CPU，会连带装上 numpy) + `tokenizers` ≈ 70MB                                                                                                                                                             |
| 模型体积       | 23MB（量化 `bge-small-zh-v1.5`，ONNX，**不需要 torch**）                                                                                                                                                               |
| 整库编码一次   | 41 秒（184 行/秒），落库 12.8MB 向量                                                                                                                                                                                   |
| 每次搜索的代价 | 模型侧 2ms（只编码那一句问题）；**整条请求实测 250~300ms**，大头不在模型，在把命中气泡的原文回表（FTS5 的 UNINDEXED 列没有索引，候选池 50 页 = 264ms）。向量矩阵已进程内缓存，剩下这笔是已知待办，见 HANDOVER 议题 B。 |
| 不装时的行为   | 关键词检索与 `*/ocr/sync` 入库完全不受影响（向量那一步只记一行日志）；`/api/search/dialogue-semantic` 返回 `available=false` + `reason=encoder_unavailable`                                                            |

```bash
# 0) 装运行时（必须是 CPU 版 onnxruntime，别与 GPU 版混装：错题本 #140）
pip install "onnxruntime>=1.20" "tokenizers>=0.21" -i https://pypi.tuna.tsinghua.edu.cn/simple
# Debian slim 基座还要系统库 libstdc++6（libonnxruntime.so 直链它，缺了 import 就失败）；
# 自建镜像时在 Dockerfile 的 pip 层后补一层：
#   RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 \
#       && rm -rf /var/lib/apt/lists/* && pip install "onnxruntime>=1.20" "tokenizers>=0.21"

# 1) 放模型（DATA_DIR/models 会随 backend/data/ 一起被备份与挂载卷带走，容器重建不丢）
mkdir -p backend/data/models/bge-small-zh-v1.5
# 国内直连 huggingface.co 不通，走镜像：
curl -L https://hf-mirror.com/Xenova/bge-small-zh-v1.5/resolve/main/onnx/model_quantized.onnx \
     -o backend/data/models/bge-small-zh-v1.5/model.onnx
curl -L https://hf-mirror.com/Xenova/bge-small-zh-v1.5/resolve/main/tokenizer.json \
     -o backend/data/models/bge-small-zh-v1.5/tokenizer.json
# 想放别处：COMIC_SHELF_EMBED_DIR=/mnt/nas_manga/models/bge-small-zh-v1.5（两个文件名保持不变）

# 2) 建一次全库向量（装完必须跑一次，否则状态一直是 vectors_missing；只认馆长口令，Machine Token 会被 403）
curl -X POST http://127.0.0.1:8000/api/search/dialogue-vectors/rebuild \
     -H "Authorization: Bearer $COMIC_SHELF_SECRET"

# 3) 验证：这句与库里任何台词都没有共同字，能返回内容就是通了
curl "http://127.0.0.1:8000/api/search/dialogue-semantic?q=告白&limit=3" \
     -H "Authorization: Bearer $COMIC_SHELF_SECRET"
```

日常**不用再手动重建**：`*/ocr/sync` 每同步一本就顺手重编那一本。只有两种情况需要手动跑第 2 步——
第一次装模型，以及换模型（状态会报 `dim_mismatch`，新旧向量维度不同不能混着算余弦）。

> ⚠️ 语义出口的 `similarity` 是余弦相似度（-1..1），**只在同一次查询的结果之间比高低**：真命中与噪声的分数区间重叠，
> 跨查询比较和绝对阈值都不成立，「没找到」只看 `reason`。关键词出口的 `rank_score` 是**本次候选池内**归一，
> 且排序掺了本人的收藏与阅读进度。两个数不是一回事，**不要混排、不要互当阈值用**（ADR 0028 决策一）。

---

## 6. 镜像构建与发布指南（Docker Hub / 镜像仓库）

纸间采用 **多阶段构建（Multi-stage Build）** 严格控制生产镜像体积：

- **Node.js 编译阶段（打包后完全丢弃）**：使用轻量 `node:22-alpine` 仅执行前端构建（`pnpm build`），**Node.js、pnpm 及庞大的 `node_modules` 均不会打包进最终镜像**；已内置 BuildKit 物理缓存挂载（`--mount=type=cache,id=paper-room-pnpm`），即使代码更新拉取了新的依赖包，已有依赖 100% 从宿主机磁盘复用，秒级极速装配；
- **最终生产镜像**：仅基于官方精简镜像 `python:3.12-slim`，安装纯 Python 运行时依赖（同样内置 pip cache 挂载），附带约 2MB 的前端静态成品，镜像极小、拉取速度极快。台词 OCR 与语义检索的推理依赖**都不在这张基础依赖表里**（前者在算力机、后者见 §5.1.2），要就在自己的构建里加一层。

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
       `(http.request.uri.path contains "/api/library/" and (http.request.uri.path.extension in {"webp" "jpg" "jpeg" "png"} or ends_with(http.request.uri.path, "/file") or ends_with(http.request.uri.path, "/thumbnail")))`
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
      "args": ["/absolute/path/to/comic-shelf/backend/app/mcp_server.py"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/comic-shelf"
      }
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
| **`COMIC_SHELF_MACHINE_TOKEN`** | `machine`（外部机器 / 微服务） | OCR 算力机、Paper Studio、NAS 定时同步脚本           | **受限最小特权沙箱**：本地导入与建本（`POST /api/library/local/*`）、伴生同步（`*/ocr/sync`）；**严格禁止访问通行证名册、禁止彻底删除漫画、禁止越权修改系统密钥**。**不能开 MCP**：MCP 工具按馆长视角取料（含隐藏本台词），这把钥匙只给写库流水线用。                                                                         |

#### 1. 选型速查：谁该拿哪把

| 调用方                                               | 发哪把                            | 备注                                                 |
| :--------------------------------------------------- | :-------------------------------- | :--------------------------------------------------- |
| OCR 算力机（`ocr.sh run --api-url … --token …`）     | `COMIC_SHELF_MACHINE_TOKEN`       | 这条流水线只调 `*/ocr/sync`，**根本不经过 MCP**      |
| Paper Studio、NAS 定时同步脚本等内网自动写库任务     | `COMIC_SHELF_MACHINE_TOKEN`       | 建本与上传画页走 `POST /api/library/local/*`         |
| 外部智能体（Claude / Cursor / 飞书 Bot 的 MCP 配置） | `COMIC_SHELF_MCP_TOKEN`           | 只需 MCP；它拿不到任何 REST 写端点                   |
| 馆长自己的浏览器                                     | `COMIC_SHELF_SECRET`              | 登录后由 HttpOnly Cookie 承载，不必手填 token        |
| 朋友与群友阅读                                       | 访客通行证 / `create_direct_pass` | **不是这三把里的任何一把**：限时、限单本、可单独注销 |

#### 2. MCP 那道门的准入名单

| `COMIC_SHELF_MCP_TOKEN` | 站长口令 | 机器密钥  | 子凭据 |
| :---------------------- | :------- | :-------- | :----- |
| 留空（默认）            | ✅       | ❌（401） | —      |
| 已设置                  | ✅       | ❌（401） | ✅     |

一句话规则：**机器密钥永远进不了 MCP**（被拒同样记一次 `mcp:<ip>` 失败）；机器密钥的其他三条路（`*/ocr/sync`、`/api/library/local/*`、`/api/search/dialogue-context`）不受任何影响；取料这条和访客一样看不到对访客隐藏的书。

三条运维红线：

1. **两把不许填同一个值**——代码不校验，同值等于两把钥匙没分家，撤销收益归零；
2. 原先拿机器密钥调 MCP 的客户端一律 401，必须换成子凭据（这是刻意的，不是 bug）；
3. **子凭据离不开站长口令**：没配 `COMIC_SHELF_SECRET` 时所有请求都按馆长放行，上表不适用。

#### 3. 泄露时换谁（撤销半径）

| 泄露的钥匙                  | 攻击面                                                     | 要动什么                                                                                |
| :-------------------------- | :--------------------------------------------------------- | :-------------------------------------------------------------------------------------- |
| `COMIC_SHELF_MCP_TOKEN`     | 全库可见性（含隐藏本）+ 签发达本直达链接（隐藏本已被否决） | 改一行 env + 重启 API：所有智能体一起断开、换新值重连；NAS 流水线与站长登录**毫无感觉** |
| `COMIC_SHELF_MACHINE_TOKEN` | 往库里写东西 + 读（进不了 MCP）                            | 换它要连所有挂载该值的脚本、Bot、定时任务一起改，并逐个重启                             |
| `COMIC_SHELF_SECRET`        | 全站：删本、通行证名册、系统配置                           | 全站重登。这就是外部智能体绝不该拿到它的原因                                            |

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
- `Dockerfile` 构建阶段直接使用 `pnpm build` 调用本地打包器；
- Docker 部署环境无需额外安装 `vp` CLI。

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

针对性验证：`pnpm test:py storage_metadata server_workers replace_pages` 覆盖刷新权限保留、旧下载失效、保存失败回退、回退失败备份保留、启动恢复可重试、恢复失败阻止启动、重新装订还原、第二次追加页表、删除残留清理、首次保存中断清目录、`.work` 临时目录清理、固定单 worker。它不替代真实 NAS/SMB 断电测试，也不覆盖追加未引用文件、封面/缩略图/decode 中途崩溃。
