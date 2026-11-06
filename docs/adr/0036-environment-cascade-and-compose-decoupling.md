# ADR 0036 — 部署环境变量双轨级联与 Compose 模板解耦

- **日期**：2026-11-06
- **状态**：Accepted
- **关联**：承接 ADR 0003 (认证与防盗链)、ADR 0026 (数据中枢架构定位)、指导 `DEPLOYMENT.md` 与 `docker-compose.yml`

## 背景与问题

纸间定位于「本地优先的个人漫画收藏馆与私密阅览室」。在此前的 Docker Compose 部署实践中，系统暴露了两处部署运维体验与规范性缺陷：

1. **代码拉取更新（`git pull`）与现场配置合并冲突**：
   过往 `docker-compose.yml` 将所有可调参数（`COMIC_SHELF_SECRET`、网络代理、各图源 Token 与密码）作为带注释的 YAML 键值列在文件内。站长或开发者在拉取仓库后，一旦在 `docker-compose.yml` 中取消注释并填入现场私有凭据，该文件即进入 Git modified 状态。后续执行 `git pull` 升级新版本代码时，极易因 `docker-compose.yml` 发生冲突而中断阻断。
2. **容器内部文件系统视角与持久化挂载脱节**：
   依据 12-Factor 原则与 Dockerfile 构建规范，代码镜像（`paper-room:latest`）构建时已通过 `.dockerignore` 剔除了宿主机 `.env` 文件；容器启动后，容器内唯一由宿主机持久化挂载、且用户能够放置文件的目录有且仅有 `/app/data`。过往代码中仅在项目根目录（`/app/.env`）与 `backend/.env` 寻找 `.env`，导致在纯容器化或 NAS 挂载卷场景下，用户无法直接通过在持久化卷中放置 `.env` 实现配置自闭环。

## 核心决策

### 一、确立部署环境变量双轨级联（Dual-Track Configuration Cascade）

在 `backend/app/config.py` 中重构环境变量探测与加载逻辑（`_load_dotenv`），支持双轨扫描，严格遵循**先读入者不被后续覆盖、系统环境绝对优先**的级联时序：

1. **Tier 1（最高权威）：系统环境变量（`os.environ`）**：
   通过 `docker run -e`、NAS Web 界面表单或 Compose `environment:` 注入的参数始终具备最高优先级，运行时绝不被文件配置冲刷覆盖；
2. **Tier 2（编排层注入）：Compose 根目录 `.env`**：
   在宿主机项目根目录下通过 `env_file: [{ path: .env, required: false }]` 注入。宿主机 Docker Compose 命令行在拉起容器前解析该文件并注入容器内核环境变量；
3. **Tier 3（存储卷兜底）：持久化数据卷 `.env`（`/app/data/.env`）**：
   容器启动后，Python 后端通过 `Path(os.getenv("COMIC_SHELF_DATA", ...)) / ".env"` 动态探测持久化挂载卷。若某配置项在上述高优先级中未被设置，则读取数据卷中的 `.env` 补充注入；
4. **Tier 4（最低兜底）：代码内置开箱默认值**：
   当上述环境均未声明时（如内网免密模式下的空密码、默认 8000 端口等），安全回退至生产级基准默认值。

### 二、Compose 编排文件瘦身与无密模板化

1. **解耦业务参数与收拢基础设施注释**：
   从 `docker-compose.yml` 中整体移除全部带注释的业务、安全与图源凭据键值，仅保留纯净的基础设施核心骨架；关于宿主机存储路径（`volumes`）与对外访问端口（`ports`）的修改说明直接在 `docker-compose.yml` 原位注释声明，彻底从 `.env.example` 中剥离易混淆的 `COMIC_SHELF_DATA` 与端口变量，杜绝概念割裂；
2. **声明容错型 `env_file`**：
   引入 `env_file: [{ path: .env, required: false }]` 规范语法。当用户未创建根目录 `.env` 时，Compose 优雅忽略并不报错中断，保障开箱即用；
3. **参数指引收拢**：
   全量业务参数说明、类型与样例统一收拢沉淀至 `.env.example`。

### 三、概念边界与持久化目录契约（Domain Modeling Alignment）

在领域模型与架构文档中严密区分：

- **数据持久卷（`/app/data`）**：漫画原图、元数据（`album.json`）、核心数据库（`comic_shelf.db`）与会话资产的存储中枢；同时作为 NAS 与容器部署下免 Git 冲突的持久配置注入点；
- **部署环境配置（`.env`）**：运行参数与私有凭据的声明载体，物理独立于 Git 代码仓库。

## 影响与收益

1. **更新升级零摩擦**：用户与开发者执行 `git pull && docker compose up -d --build paper-room` 时，本地 `docker-compose.yml` 永远与远程上游保持一致，绝无合并冲突；
2. **多形态部署无缝兼顾**：
   - 开发者 / VPS：复制 `cp .env.example .env` 走标准 Compose 注入；
   - NAS / 预构建单容器 / 卷持久化：复制 `cp .env.example backend/data/.env`（容器内 `/app/data/.env`），无感知热插拔；
   - 纯内网家庭用户：零配置直接拉起，享受局域网免密极速阅览。
