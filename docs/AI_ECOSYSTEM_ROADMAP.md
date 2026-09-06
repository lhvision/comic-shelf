# 纸间 · 扩展生态与 AI 演进路线图（AI Ecosystem & Evolutionary Roadmap）

> 本文档记录纸间在完成多源收录（JM / Local / PicAcg）与阅读器核心基建后，关于**外部智能连接、AI 漫画创作、私有模型微调与互动游戏化**的探索性设计方案与演进蓝图。
>
> 与确定性架构决策记录（[ADR 0013](docs/adr/0013-picacg-provider-and-architecture-fidelity.md)）解耦，本文档作为前瞻提案库与需求蓄水池，为后续各阶段的落地与重构提供设计参考。

---

## 🗺️ 演进阶段全景图

```text
┌─────────────────────────────────────────────────────────────┐
│ 阶段一：数据沉淀与接口开放 (Data Foundation & Open API)      │
│  - 哔咔 (PicAcg) 数据源落地 (当前正在实施)                   │
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

## 三、 AI 漫画生成工坊（AI Comic Generation Pipeline）

### 1. 契约复用原则

纸间现有的 `LocalProvider`（`source = "local"`）已高度成熟，原生支持多章节、拆帧导入、封面重新装订与双模 WebP 缩略图预热。
**AI 生成的作品天然属于本地自建漫画，无需新建专有 Provider。**

### 2. 外部 Agent 自动化流程

1. **剧本与分镜编排**：由外部大模型（如 Claude / GPT-4o / Qwen）构思故事情节，输出包含页数、场景描述、分镜构图与提示词（Prompts）的结构化 JSON；
2. **画页图像生成**：Agent 批量调用生图 API（Flux / Midjourney / 本地 ComfyUI），生成 `00001.webp` ~ `0000N.webp`；
3. **一键收录上架**：Agent 调用纸间标准 API（`POST /api/library/local/create`）推送画页与元数据；
4. **元数据归档**：将生图使用的 Prompt、种子、底模等信息直接存入 `album.json` 的 `extra.ai_generation` 字段中，实现资产全生命周期可溯源。

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
