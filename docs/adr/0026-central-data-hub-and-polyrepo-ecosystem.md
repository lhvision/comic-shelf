# ADR 0026 — 纸间核心数据中枢定位、多项目独立仓库架构与伴生资产契约决策

- **日期**：2026-09-19
- **状态**：Accepted
- **关联**：承接 ADR 0013 (哔咔数据源接入与架构定力)、ADR 0017 (台词全文检索与气泡高亮)、扩展 `CONTEXT.md` 纸间数据中枢、多项目独立仓库架构、伴生资产标准命名空间，指导 `docs/AI_ECOSYSTEM_ROADMAP.md`

## 背景

随着纸间（Paper Room）在多源漫画收录（JM / Local / PicAcg）、高性能纯净阅读器、以图搜图特征引擎（ORB + 倒排索引）、台词全文检索（SQLite FTS5 + Trigram）以及端云双轨 MCP（FastAPI `/mcp/sse` + 视口 WebMCP）等核心能力的全面落地，系统面临向**外部智能连接、AI 漫画创作、私有模型微调与互动游戏化**演进的重要战略转折期：

1. **生态扩展需求激增**：需要孵化「飞书以图搜图 Bot」、「AI 生图与矢量分层工坊（Paper Studio）」、「Galgame 中日双语平行语料清洗与微调管线」以及「2D 互动视觉小说引擎」等多个衍生子系统；
2. **异构技术栈与依赖膨胀冲突**：
   - 纸间核心读者端（`comic-shelf`）强调极简、轻量与极致加载速度（单容器 Docker 镜像仅数百 MB，前端 Vite+ 编译秒开）；
   - AI 生图依赖庞大的 Python 深度学习生态（PyTorch、Diffusers、ComfyUI、CUDA 运行时，体积可达 20~50 GB）；
   - 飞书 Bot 依赖 TypeScript / Bun / Node.js 开放平台 SDK；
   - Galgame 解包脚本依赖 C# / Python 专用二次元逆向解析器；
   - 若将所有异构依赖无差别堆砌进当前单体仓库，将引发严重的依赖地狱、构建时间失控与运维灾难；
3. **数据主权与沙箱安全边界**：外部 Bot 和 Agent 需要检索书库内容或签发直达阅读链接，但严禁泄露馆长密钥（`CURATOR_SECRET`）或导致未授权访客通过外链遍历全站私人藏书。

## 决策

### 1. 确立纸间核心为「数据中枢与纯净展馆」（Central Data & Headless Service Hub）

- **单一事实真理源（Single Source of Truth）**：纸间（`comic-shelf`）坚守作为全站漫画数据持久化、重型特征检索与纯净读者端的定位；
- **能力全面下沉收敛**：
  - **存储与元数据层**：接管全站漫画文件（`backend/data/library/`）、增量 WebP 缩略图生成与 SQLite 影子索引；
  - **重型特征与检索层**：内置 `imsearch` 局部视觉特征倒排索引与 SQLite FTS5 对白全文检索；
  - **控制与通信平面**：暴露标准 REST API、Server-Side MCP 端点（`/mcp/sse` 与 stdio）及前端 WebMCP 工具；
  - **沙箱安全防线**：提供单本锁定的带时效临时凭据（`temp_token` via `POST /api/auth/direct-pass`）与机器专用令牌（`MACHINE_API_TOKEN`）。

### 2. 确立多项目独立仓库拓扑（Polyrepo Architecture）

- **坚决否决单仓多包（Monorepo）**：为杜绝 PyTorch / ComfyUI / 游戏引擎等重型依赖侵入核心代码库，确立**物理分仓、独立同级目录、松耦合通信**的 Polyrepo 标准拓扑：
  - `comic-shelf`（本仓库）：核心数据中枢、管理后台与纯净读者端；
  - `paper-feishu-bot`（独立仓库）：飞书以图搜图与台词检索群聊机器人（TypeScript/Bun）；
  - `paper-studio`（独立仓库）：AI 漫画剧本生成、Prompt 编排、ComfyUI 生图与 VTracer 矢量分层工作台（Python/PyTorch）；
  - `paper-corpus`（独立仓库）：Galgame 中日双语脚本解包、平行语料对齐与 SFT 微调管线；
  - `interactive-avg`（独立仓库）：基于分镜切片与决策分支树的 Web 2D 互动游戏引擎；
- **通信边界协议化**：所有子系统与纸间核心之间**仅允许通过标准 HTTP REST API、MCP 协议或文件系统标准伴生资产契约交互**，严禁直接读写纸间内部 SQLite 数据库文件或侵入私有代码模块。

### 3. 伴生资产标准命名空间（Standard Sidecar Asset Protocol）

为支撑下游 AI 生图工坊、微调管线与游戏引擎的数据汇流，纸间后端在 `backend/data/` 固化标准文件命名空间：

1. **单本画页伴生资产**（`backend/data/library/<source>/<source_id>/pages/`）：
   - `{index}.webp`：画页原图；
   - `{index}_360.webp` / `{index}_720.webp`：多级封面与缩略图；
   - `{index}.ocr.json`：分镜对白结构化转录与归一化气泡包围盒（`[ymin, xmin, ymax, xmax]`）；
   - `{index}.layers.json`：VTracer 矢量分层手稿路径（供前端 Making-of Player 流式绘制）；
   - `{index}.panels.json`：单格分镜格子几何切片坐标；
   - `{index}.caption.txt`：多模态模型微调标注提示词；
2. **二次元平行语料专区**（`backend/data/corpus/galgame/<game_id>.jsonl`）：
   - 存储从主流 Galgame 引擎（KiriKiri / Ren'Py / Siglus）解包出的高质量中日双语对照对白行（`{ speaker, text_ja, text_zh, scene_id }`），专供二次元专精翻译模型微调与全局名句索引。

### 4. 纯软件就绪与无硬件过渡策略（Hardware-Agnostic Phased Execution）

- **开发机即是完整数据中心**：纸间数据中枢的核心契约已 100% 具备单机运行能力，无需等待 Mac mini / TrueNAS 等物理硬件到位；
- **下游微服务无缝先发**：下游子项目可在本地 Linux 开发机上完成开发、单测与联调；
- **零成本平滑迁移**：待未来物理硬件到位后，仅需通过 Docker 镜像与数据卷挂载（`/Volumes/ComicStorage/data`）一键打包迁移，网络层直接对齐 `HOMELAB_NETWORKING_GUIDE.md` 即可全线投产。

## 影响与收益

1. **核心架构高内聚低耦合**：纸间读者端保持毫秒级启动与极低资源消耗，完全不受外部重型 AI 生态演进的干扰；
2. **下游扩展极度自由**：各个子项目可自由挑选最适合的技术栈（Bun/Rust/PyTorch），通过纸间标准 API 与 MCP 赋能；
3. **数据资产沉淀标准化**：伴生资产契约确保了未来无论是翻译、搜图、手稿回放还是互动游戏，数据均能井然有序地在数据中心持久化与复用。
