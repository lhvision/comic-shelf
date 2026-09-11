# 纸间 · 扩展生态与 AI 演进路线图（AI Ecosystem & Evolutionary Roadmap）

> 本文档记录纸间在完成多源收录（JM / Local / PicAcg）与阅读器核心基建后，关于**外部智能连接、AI 漫画创作、私有模型微调与互动游戏化**的探索性设计方案与演进蓝图。
>
> 与确定性架构决策记录（[ADR 0013](docs/adr/0013-picacg-provider-and-architecture-fidelity.md)）解耦，本文档作为前瞻提案库与需求蓄水池，为后续各阶段的落地与重构提供设计参考。

---

## 🗺️ 演进阶段全景图

```text
┌─────────────────────────────────────────────────────────────┐
│ 阶段一：数据沉淀与接口开放 (Data Foundation & Open API)      │
│  - 哔咔 (PicAcg) 数据源已完美落地（确立多源扩展标准蓝图）    │
│  - 纸间 MCP Server 端点开发 (/mcp/sse)                      │
│  - 定向临时直达票据 (One-Time Direct Pass)                   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 阶段二：外部生态连接 (Ecosystem Integration)                │
│  - 飞书以图搜图 Bot (Feishu Visual Search Bridge)           │
│  - 外部 TypeScript Agent (多维推荐 / 自动化巡检)            │
│  - 迁移部署至 Mac mini (Homelab 低功耗全天候私有云)          │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 阶段三：AI 漫画创作工坊 (AI Comic Generation Pipeline)       │
│  - 剧本大模型生成 ➔ 分镜 Prompt 拆解 ➔ 图像扩散批量生成      │
│  - 对接 LocalProvider 标准 API，一键装订入馆上架             │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 阶段四：私有垂直模型微调 (Domain Multimodal Fine-Tuning)     │
│  - 基于纸间沉淀的高清漫画分镜与对白语料                      │
│  - 云端租算力进行 LoRA 微调 ➔ 本地 Mac mini (MLX) 高速推理   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 阶段五：2D 互动分支游戏 / 视觉小说 (Interactive AVG Engine)  │
│  - 分镜气泡智能切片 (Panel Segmentation) + OCR 角色台词提取 │
│  - 剧情决策分支树编译 ➔ 轻量 Web Canvas 互动 AVG 游戏        │
└─────────────────────────────────────────────────────────────┘
```

---

## 一、 纸间 MCP 服务端（Paper Room Model Context Protocol Server）

### 1. 定位与场景

为外部 AI Agent（无论是在本地运行的 Claude Desktop、Cursor、Cline，还是部署在云端的 Agent、飞书 Bot）提供一套标准化的**具身工具操作界面**，无需每次手写脆弱的 HTTP 请求。

### 2. 传输协议选型

- **内置 HTTP-SSE 传输模式（推荐）**：在 FastAPI 中挂载 `/mcp/sse`，遵循标准 MCP over Server-Sent Events 协议。
- **本地 stdio 代理**：通过极轻量的 CLI 包装脚本，供本地桌面 AI 客户端通过管道调用。

### 3. 工具清单（Tools Draft）

- `search_by_image(image_bytes | image_base64)`：
  调用内部 `imsearch` 引擎比对局部特征，输出命中的漫画 `source`、`source_id`、具体页码及置信度。
- `query_shelf(keyword?, tag?, source?, limit?)`：
  多维检索书架藏书，返回符合条件的本子元数据与封面。
- `get_comic_detail(source, source_id)`：
  获取单本漫画的完整目录、章节划分与全局页数。
- `recommend_unread(user_id?, limit=5)`：
  基于当前读者的阅读进度与红心偏好，推荐同标签或同作者的未读藏书。
- `create_direct_pass(source, source_id, page_index=1, ttl_seconds=7200)`：
  签发单本锁定的带时效直达阅读链接。

---

## 二、 外围智能生态与飞书 Bot（Feishu Visual Search Bridge）

### 1. 架构拓扑

- **物理分项目**：飞书 Bot 作为独立的 TypeScript 项目（使用 Node/Bun + 飞书开放平台 SDK），不侵入纸间核心仓库；
- **网络交互**：Bot 接收到群聊或私聊中的图片后，通过 HTTP 或 MCP 工具调用纸间服务。

### 2. 安全防线：定向单本临时凭据（One-Time Direct Pass）

- **痛点**：纸间全站实施严格的门禁（Curator 密钥 / 访客通行证与 PIN 码）。若直接返回书库链接，未登录的读者会被阻断在门禁；但若为了方便开放访客权限，又容易导致群友顺藤摸瓜窥探全站藏书。
- **单本沙箱（Single-Book Sandbox）机制**：
  1. 机器人识图成功后，调用 `POST /api/auth/direct-pass` 签发专属 `temp_token`；
  2. 生成阅读链接：`https://shelf.example.com/book/jm/523607?page=42&temp_token=...`；
  3. 后端在 SQLite 记录 `(token, source, source_id, expires_at)`（默认 2 小时有效）；
  4. 访客点击链接打开后，前端与后端仅放行该本漫画的正文画页与缩略图请求；若尝试返回书架首页（`/`）或请求其他作品，系统自动重定向至门禁纸室并拦截。

---

## 三、 AI 漫画生成工坊与手稿回放（AI Comic Generation & Making-of Pipeline）

### 1. 双平台架构边界（Paper Studio 独立创作台 vs Paper Room 纯净展馆）

为防止将庞大的生图库（PyTorch、Diffusers、OpenCV、ComfyUI 依赖）与复杂创作交互侵入纸间核心读者端，系统确立 **“创作与消费松耦合”** 双平台架构：

- **纸间展馆（Paper Room / comic-shelf 本仓库）**：
  - **角色**：**读者端与轻量展览馆**。
  - **边界**：坚守纯净的本地优先阅读、书架管理与以图搜图；仅提供一个极轻量（≤150 行代码）的「手稿分层回放台（Making-of Player）」模态窗，通过原生 `new Path2D(d)` 零 DOM 消耗播放外部传入的矢量层；
  - **接口契约**：复用成熟的 `LocalProvider`（`POST /api/library/local/create`）一键收录已装订好的成品与伴生手稿资产（`.layers.json`）。
- **外部创作工坊（Paper Studio 独立平台 / Agent）**：
  - **角色**：**重型生产力工作台**（独立仓库或微服务）。
  - **边界**：承载剧本大模型生成、分镜 Prompt 编排、ComfyUI 图像批量去噪、修脸修手、以及 **VTracer 矢量化分层压制**；生成完毕后通过 API 向纸间一键推送入库。

### 2. VTracer 智能矢量化分层管线（Raster-to-Vector Pipeline）

在 Paper Studio 后端利用 [visioncortex/vtracer](https://github.com/visioncortex/vtracer) 原生引擎对生图成品进行拓扑矢量化提取：

1. **色彩指纹探测与双预设路由**：
   - **黑白线稿（Manga Line Art）**：启用 `--preset bw --adaptive`，自适应二值化过滤网点噪点，生成极简锐利的单色骨架与墨线层（呈现“草稿 ➔ 勾线 ➔ 涂黑”）；
   - **全彩插画（Color Illustration）**：启用 `--clustering color-cluster --hierarchical stacked --filter-speckle 4`，多层次区域聚类堆叠（呈现“大块铺底色 ➔ 明暗阴影 ➔ 细节高光”）。
2. **伴生资产打包（`00001.layers.json`）**：
   - 将 VTracer 产出的分层贝塞尔曲线提炼为紧凑 JSON 格式（`[{ id: 1, type: "base", fill: "#f5f5f5", path: "M..." }, ...]`）；
   - 与原图 `00001.webp` 平级存放于 `backend/data/library/local/{id}/` 目录，体积比原始 XML SVG 减少 40%，且前端 0 解析损耗。

### 3. 纸间手稿回放台（Making-of Player）流式呈现

- **零 DOM 压力硬件加速**：前端直接利用 Canvas 2D 原生 `new Path2D(layer.path)` 与 WebGL 流式绘制，全过程跳过 DOM 树与 CSS 重排，稳定维持 120 FPS 丝滑动画；
- **沉浸式花絮交互**：作为详情页与阅读器的“制作过程 / 手稿生长”独立模态窗，提供时间轴进度条、分层独立显隐控制与运笔速度调节，完全不干扰主阅读心流。

### 4. 训练原料清洗：分镜裁切与对白脱敏（Panel & Dialogue Inpainting）

整页漫画直接喂入 LoRA 训练会导致模型强行记忆多格边框与破碎文字。在外部 Studio 洗料管线中引入自动化脱敏：

- **分镜切割（Panel Segmentation）**：利用轻量目标检测（YOLO/SAM）将整页自动裁切为单格独立分镜画面；
- **对白气泡抹除（Bubble Inpainting）**：检测气泡位置，以 LaMa / SD Inpaint 自动消除文字与气泡，生成纯净无字的原始角色/场景训练对。

### 5. 多模态伴生资产契约（Sidecar Asset Protocol）

`backend/data/library/local/{id}/pages/` 目录下统一收敛标准伴生文件命名空间：

- `{index}.layers.json`：VTracer 矢量分层生长路径；
- `{index}.panels.json`：分镜格子几何坐标 `[{ id, x, y, w, h }]`；
- `{index}.ocr.json`：分镜台词对白结构化转录；
- `{index}.caption.txt`：用于模型微调的 Booru / 自然语言标注提示词。

### 6. 服务间认证凭据与推送 Webhook（Machine-to-Machine Auth）

外部 Paper Studio 完成整本编排后，携带专用 `Machine API Token` 调用 `POST /api/library/local/create` 推送画页与伴生资产；纸间后端完成校验后自动触发缩略图预热并广播 `library_changed` 事件，前台书架即时无缝呈现。

---

## 四、 领域多模态模型微调（Domain Multimodal Fine-Tuning）

### 1. 数据资产价值

漫画具备极其紧凑的多模态叙事属性。随着纸间收录的高清本子增多，沉淀出的图文资产是极佳的私有训练语料：

- **对话与叙事语料**：提取台词与情境描述，微调出专攻二次元漫画剧本与分镜 Prompt 的垂直大模型；
- **画风与角色样本**：收集统一画风的高清图，微调专有 Style LoRA 与 Character LoRA。

### 2. 算力拓扑：训练与推理分离

- **训练在云端（低成本按需）**：利用 AutoDL、RunPod 等廉价算力平台，按小时租赁单张 RTX 4090 或 A100，跑 LoRA 微调（仅需几元人民币），生成数百兆的轻量权重文件；
- **本地常驻推理**：训练完成后将 LoRA 权重拉回本地。

---

## 五、 Mac mini（Apple Silicon）Homelab 私有云演进

### 1. 为什么是 Mac mini？

- **统一内存（Unified Memory）优势**：CPU 与 GPU 共享内存（如 32GB/64GB/128GB）。结合苹果 **MLX** 框架或 **llama.cpp**，可以在内存中高效加载运行 14B~32B 参数的开源大模型，完全打破传统显卡显存瓶颈；
- **全天候静音与低功耗**：整机待机仅数瓦，满负荷 30~50 瓦，无刺耳风扇噪音，适合作为 24 小时开机的家庭书房核心；
- **一体化架构**：单台设备同时跑 Docker（FastAPI 后端 + Vue 前端 + imsearch 搜图）与本地大模型推理端点。

### 2. 外接大容量硬盘柜（DAS）冷热分层存储拓扑

Mac mini 内置 SSD 加装成本高昂（通常为 512GB/1TB），面对海量漫画库与多模态模型文件需建立物理分层：

- **外接雷电 4 / USB-C 多盘位硬盘柜（DAS / RAID 阵列）**：格式化为 APFS 挂载至 `/Volumes/ComicStorage/data`，专供 `library/` 原图海量仓库、离线画页与训练冷数据，彻底解放内置容量；
- **内置极速 SSD**：专供 macOS 系统、Docker 运行时、SQLite 数据库、以图搜图向量索引与 MLX 大模型热权重。

### 3. 端侧 100% 离线隐私 VLM（Apple Silicon MLX）

利用 Mac mini 的统一内存，在本地常驻运行开源视觉多模态大模型（如 `Qwen2.5-VL-7B/14B`）：

- **全天候自动打标**：对入库本子自动执行打标（Captioning）与剧情分镜理解，0 API 调用成本；
- **100% 隐私闭环**：私密漫画资产全生命周期不流出家庭局域网，彻底免除第三方云端 API 审查与封号风险。

---

## 六、 长远 2D 互动游戏 / 视觉小说演化（Interactive Narrative & AVG）

### 1. 技术路线抉择：为什么坚持 2D 路线？

- **3D WebGL / Blender MCP 的局限**：漫画本质是高度风格化的手绘 2D 艺术。当前 Image-to-3D 模型生成的 3D 资产拓扑杂乱、骨骼动作绑定困难，极易造成画风严重失真，投入产出比极低；
- **2D 互动视觉小说（AVG）的优势**：完美契合漫画资产特性，100% 保留原作细腻作画。

### 2. 演化管线

1. **分镜切片与对白抽取**：利用轻量模型分割漫画分镜格子（Panel），OCR 抽取气泡对白；
2. **分支剧本编译**：LLM 解析分镜故事线，生成玩家可参与的选择支（Choice Points）与好感度逻辑；
3. **Web 端轻量引擎**：利用 Web Canvas / Pixi.js 编译为可在浏览器即点即玩的分支互动视觉小说。

---

## 📌 下一步决策建议

当完成第一步（哔咔 PicAcg 来源收录）后，下一阶段的启动优先级建议：

1. 优先实施 **“纸间 MCP 服务端”** 与 **“定向临时直达票据”**，为你的外部 TS Agent 和飞书搜图 Bot 打通标准通道；
2. 随后搭建外部 TS 生态项目，接入飞书群聊实战验证；
3. 待资源丰富后，开启 AI 本子生成与 Mac mini 迁移演化。
