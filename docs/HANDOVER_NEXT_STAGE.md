# 纸间 · 阶段交接与下一步议题（Handover）

> **文档目的**：为新对话会话提供无缝交接索引——当前基线、可复现的台账快照、质量门禁实测状态，以及**真正的待决议题**。
> 本文只写"约束与未决"，能由命令查到的事实一律附复现命令，避免数字腐烂。

---

## 一、已落地基线（不再是议题）

| 能力                                           | 出口                                                                                     | 关键约束与出处                                                                                                                                                                                                                                                                                 |
| :--------------------------------------------- | :--------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 台词全文检索（简繁互通 + 页级聚合 + 气泡坐标） | `GET /api/search/dialogue`；MCP `search_by_dialogue`                                     | FTS5 虚拟表在**独立库** `backend/data/comic_dialogues.db`（`tokenize='trigram'`，含 `kind`/`reading_order` 列）；加列只能整表重建，重建后自动回填；2 字查询产不出 trigram，只能走 `LIKE` + 词频密度近似排序。[ADR 0017](adr/0017-comic-dialogue-fts-and-bubble-overlay.md)                     |
| 排序质量（截断留谁）                           | 同上 + `rank_score` 字段透出                                                             | `rank_score` 语义固定为**候选池内 min-max 归一的纯相关度**，四类业务信号（热度/收藏/完读/最近阅读）只抬升不压低、合计封顶 0.5；**只有顺序随身份变**，`rank_score`/`bubble_count`/`text` 同一页必须逐字一致。错题本 #139                                                                        |
| 剧情取料出口                                   | `GET /api/search/dialogue-context`；MCP `get_story_context`                              | 馆长与 Machine 专属，吐**原始态**文本（无 `<mark>`、无 snippet），按阅读原序截断                                                                                                                                                                                                               |
| 台词 OCR 算力线                                | `bash scripts/ocr.sh {status\|run\|sync\|install\|test\|lines}`                          | **只剩一条线**：`rapidocr` 3.x + PP-OCRv6 **small**（`tiny` 不含日文）；默认 GPU，`--cpu` 显式回落。v3 轨道（`rapidocr-onnxruntime`）已整体删除——它 6623 字字符表里只有 5 个假名。错题本 #137/#143                                                                                             |
| 气泡聚类                                       | `scripts/ocr_worker.py::cluster_blocks`                                                  | 三道否决闸：同向、笔画粗细比 ≤2、**合并后外接框 ≤20% 页面积**（面积必须按分量整体判，成对距离会被 union-find 传递闭包绕过）。验证口径是"字数守恒"。错题本 #142                                                                                                                                 |
| 判据离线迭代                                   | `bash scripts/ocr.sh lines`（dump 原始行 / `--recluster` 重聚类）                        | 侧车**不存**原始行（阅读器每页要解析，体积翻倍不划算），这个 dump 是唯一离线复现入口；只写 `/tmp`，绝不碰 `backend/data`                                                                                                                                                                       |
| 语料分类                                       | `sync_comic_dialogues` 的 `classify_dialogue_kind`                                       | `dialogue` / `paratext`（入库但不进台词检索，为取料与语义召回保留） / `noise`（水印页码，不入库）。只用页位 + 文本特征，**不用几何轮廓判据**（实测误伤 41% 真台词）。ADR 0017 决策 7                                                                                                           |
| 阅读器气泡高亮                                 | URL 参数 `bubble_box` / `bubble_boxes` / `bubble_text`                                   | 归一化百分比坐标 + Aspect-Ratio Lock 贴紧；高亮走坐标，不持久化 bubble id，所以重排 `order` 不影响已分享的直达链接                                                                                                                                                                             |
| MCP Server + 官方 Skill                        | `backend/app/routers/mcp.py`（8 工具 / 3 资源 / 1 提示词）、`skills/paper-room/SKILL.md` | 三条 HTTP 路由均自带 `_require_mcp_auth`，只认馆长口令或 **`COMIC_SHELF_MCP_TOKEN` 子凭据**（配了子凭据后机器密钥不再能开 MCP），访客与匿名进不来；工具内部取数仍是馆长级，但 `create_direct_pass` 硬拒绝为隐藏本签发（见议题 D）。SSE 自带 `no-cache, no-transform` + `X-Accel-Buffering: no` |
| 单本沙箱临时直达凭据                           | MCP `create_direct_pass`、`POST /api/auth/direct-pass`                                   | 中间件按通行证前缀锁作用域，画页 `Token + IP` 复合滑窗 180 页/分钟                                                                                                                                                                                                                             |
| 已过鉴权的 `/api` 响应统一 `no-store`          | `auth_and_security_middleware` 收尾                                                      | 处理器自写的缓存头不被覆盖；链路出口由 `backend/tests/test_dialogue_http_stack.py` 用真 HTTP 请求锁死                                                                                                                                                                                          |

---

## 二、台账快照（截至本次交接）

复现：`bash scripts/ocr.sh status`。

- 藏书 **48 本 / 3033 页**；有 OCR 伴生 **43 本 / 1764 页**（页覆盖率 58.2%）。
- 侧车来源：`engine_track=v6` **201 页 / 5 本**；legacy（v3 时代产物，无 `engine_track` 字段）**1563 页 / 38 本**。
- FTS 索引 **8095 行**：`dialogue` 7544 / `paratext` 551，覆盖 43 本 1658 页。
- 两批侧车的缺陷签名对照（同一判据扫盘）：
  - `>35%` 页面积的气泡：legacy **29 个（20 本）**、v6 **0 个**；
  - 每百页含日文假名的气泡数：legacy **13.4**、v6 **57.7**（两批书目不同，只作量级参考）；
  - 平均每页字数：legacy **65.6**、v6 **104.9**（差值里含聚类拆分的贡献，不是引擎单因素）。
- 吞吐（同机 RTX 4070 Ti / 8 核，**两个口径分开看，别互相冒充**，详见 `DEPLOYMENT.md` §5.1）：
  - 全库异构 1764 页走 `ocr.sh run`（含写盘）：v6 GPU 4 线程 **94 页/分**（v3 同机同口径 129 页/分）；
  - 同页 marginal（`jm/1249304` 153 页，离线 dump harness 扣掉模型加载）：GPU 4 线程 **239 页/分**、CPU 2 线程 **37.3**、CPU 4 线程反而 **32.4** → GPU:CPU ≈ 6:1，CPU 加线程无收益的定性结论在 v6 依然成立。
  - 复测踩坑：绕开 `ocr.sh` 直接 `.venv-ocr/bin/python scripts/ocr_lines.py --gpu` 会漏挂 `LD_LIBRARY_PATH`，`libcublasLt.so.13` 缺失即静默退回 CPU——本轮第一组"GPU 34 页/分"就是这么来的，与 #137 同一条坑。
- 本机环境：`.venv-ocr` 已就绪，`status` 报 🟢 CUDA 生效（Det,Cls,Rec）；应用 `.venv` **没有** rapidocr 3.x，故 `run --cpu` 与 PDF 扉页分话在本机停用（预检会清晰报错，不静默降级）。

---

## 三、质量门禁（本次实测全绿）

- **Python 后端**：`bash scripts/test_py.sh`（等价 `pnpm test:py`）全绿——24 个 `backend/tests/test_*.py` 套件 + `backend/check_backend.py` 动态 AST 巡检。本轮新增两份：
  - `backend/tests/test_dialogue_http_stack.py`：真 HTTP 穿中间件栈，锁 `rank_score` 活着走出响应模型、`no-store` 落地、未授权 401；lifespan 写锁落在临时书库（不抢开发实例的锁）。
  - `backend/tests/test_ocr_lines.py`：离线实验台——`_images` 的 `--source`/`--pages` 作用域、dump 只写 `--out` 且按 `DEFAULT_MIN_SCORE` 过滤、`--recluster` **不构造任何推理引擎**且字数守恒。
- **前端**：`bash -lc 'vp check'`（格式化 + lint + type-check）与 `bash -lc 'pnpm type-check'`（`vue-tsc --build` 增量，验 Vue 模板绑定）均 0 错误。
- **Shell**：`bash -n scripts/ocr.sh`（本仓库踩过的坑：往 shell 里嵌 python heredoc 时把终止符吞掉，会让整个子命令 `command not found`）。
- **UI 评审快照**：`.impeccable/critique/` 最新三份对应页级聚合、两字近似排序、同页其余格描边。
- 文档同步：`DEPLOYMENT.md` §5.1（算力线与离线实验台）、`CONTEXT.md`（气泡聚类词条）、`docs/PITFALLS.md` #137/#142/#143。

---

## 四、待决议题（按性价比排序）

### 议题 A：剩余 38 本 legacy 侧车是否切 v6 —— **需要拍板**

- 成本：1563 页 ÷ 94 页/分 ≈ **17 分钟 GPU**（`bash scripts/ocr.sh run --source jm --force`，随后 `sync`）。
- 收益：清掉账上 29 处整页糊、补齐日文假名与繁体字形（v3 常把 `歡` 直接丢、`這` 认成 `遣`）。
- 现状：**用户已决定暂不重提**（当前语料量够用）。触发条件建议：语料要对外取料、或要做训练原料清洗时，先重提再动检索侧。

### 议题 B：语义召回（路线图第 5 步）—— ✅ 独立出口已落地（2026-09-23），混合排序**故意没做**

三条 decided：模型与算力放本机（量化 `bge-small-zh-v1.5` 23MB，CPU 编码 184 行/秒、查询 2ms，
不必挪到算力机）、向量存台词专库新表 `comic_dialogue_vectors`（不与识图 sidecar 混库）、
**不与 `rank_score` 融合**（语义出口独立返回 `similarity`，见 ADR 0028）。
出口：`GET /api/search/dialogue-semantic` + MCP `search_by_meaning`；向量随 `*/ocr/sync` 每本顺带重编，
全量重建走 `POST /api/search/dialogue-vectors/rebuild`。真库 6254 条向量、12.8MB、`paratext` 与 <4 字短句不建向量。

实测质量（要诚实看）：`脸红`→`满脸通红`(0.63)、`今天天气不错`→`真是好天气！雨过天晴了呢！`(0.67)、
`久别重逢`→`与老师相见交换着信语`(0.51) 这类**字面零重合**的查询都能落对；但 `告白`、`分手` 这类
抽象动词仍返回噪声（0.48~0.49），原因是语料本身是脏 OCR 短句，不是模型不行——**分数分布很窄，
不要拿绝对阈值当"命中/没命中"判据**。

**已知待办（不是 bug）**：整条语义查询实测 250~300ms，模型只占 2ms，其余是把命中气泡的原文回表
（FTS5 的 UNINDEXED 列无索引，候选池 50 页 = 264ms）。要压到 ~50ms 的做法是把回表并入已缓存的
向量加载（一次全表扫，随矩阵一起缓存），或给向量表存 FTS `rowid` 走主键 seek。语料翻倍前不急。

### 议题 C：简繁**混排**字形的索引侧规范化 —— ✅ 已结案（2026-09-23 本轮落地）

原来的判断（"检索侧靠 `zh_conv` 双向展开兜住"、"语料再大一倍才值得动"）**是错的**，实测把它推翻了：`zh_conv` 的映射逐字符一对一，一次查询最多产出「原样 / 全简 / 全繁」三个**整串**写法，而汉化组语料大量是**同一行内繁简混排**（嵌字只换一半、字体缺字），整串展开对这类行天生无解。

真库 7544 条台词里 1238 行含繁体字形，其中 **735 行（59%）用简体照着页面打出来搜不到**（例：语料「縮紧」，查询「缩紧」→「缩紧 / 縮緊」两个都不是）。落地做法与代价：

- `comic_dialogues_fts` 追加 `text_norm` 列（写入侧 `to_simplified(text)`），**倒排只建这一列**，`text` 退为 `UNINDEXED` 的原文副本；查询侧单次归一，MATCH 从"三条 OR 词元"降成一条，2 字 LIKE 兜底同样只数一个 needle；
- 展示不失真：`to_simplified` 是 1:1 逐字符映射，长度与偏移不变，`_make_snippet` 在归一列定位、把 `<mark>` 切在原文上；`snippet()` 那个按位置写死的列号一并删掉了（命中的是归一列，SQL 摘要永远标不到原文上）；
- 迁移零人工：缺列触发既有"整表重建 + 回填"，真库 8095 行重灌 **0.8s**；
- 回归核对：735 条简体输入 100% 命中自己那行；繁体原文照抄、日文行照抄（108/108）、日文汉字换简体（28/28）均不受损；6 条查询合计 51ms。
- ⚠️ 本轮踩到一条新坑并已入错题本 **#145**：常驻 `--reload` 的 dev server 会在"先加列、后改 INSERT"的中间态自动重启，把新列全 NULL 灌进真库，且 `comic_ocr_sync_meta` 被写成已同步——迁移后必须验新列非空，不能只看行数。

### 议题 D：MCP 与匿名面的凭据暴露面（2026-09-23 安全审计）—— 八项已收口，两项待拍

审计口径：`_require_mcp_auth` 本身没有漏（`mcp.py:993/1047/1073` 三条路由全覆盖，访客挡得住），问题在**授权粒度与旁路**：

**已收口（2026-09-23 本轮，用例见 `test_mcp.py::test_mcp_scoped_credential_and_hidden_book_refusal`、`test_mcp.py::test_mcp_handshake_url_is_credential_free_and_failures_get_locked`、`test_events.py` 第 8 步、`test_auth.py` 2f'）**：

1. ✅ **MCP 子凭据 `COMIC_SHELF_MCP_TOKEN`**：`_require_mcp_auth` 现在只认馆长口令 + 这把子凭据；**一旦配置，机器密钥在 MCP 面立即失效**（撤销半径缩到单个 agent，不用换站长口令也不用重启 NAS 流水线）。未配置时行为与老版本逐字一致。
2. ✅ **`create_direct_pass` 查 `hidden_from_guest`**（`mcp.py:611-624`）：MCP 通道拒绝为"对访客隐藏"的本子签发公开直达链接，工具描述里也写死了"请勿重试"，人真要分享走 Web 端。
3. ✅ **`/api/health` 不再报宿主机路径**（`system.py`），只留 `ok`/`providers`/`auth_required`。
4. ✅ **`/api/events/stream` 自带 `can_read` 门禁**：全站中间件对该前缀提前放行，长连接不能被拦截器打断，所以门禁落在处理器里。payload **故意保留** `source`/`source_id` —— 前端任务态（`beginTask`/`endTask` 的缓存与导入自旋）就靠它对齐，粗化会打断 UI。
5. ✅ **stdio 通道零鉴权已在 `DEPLOYMENT.md` §9.5 写死**："能 spawn 这个进程 = 馆长权限"。
6. ✅ **Skill 侧补了凭据最小化规则**（`skills/paper-room/SKILL.md` IRON LAW 5 与 Red Flag 末条），并明确"本节不是安全边界"。

7. ✅ **握手 URL 不再携带凭据**：SSE 返回的 `/api/mcp/messages?session_id=...` 只带 `session_id`（服务端每连接新发的 128bit 随机值，断连即回收），活会话凭它续话；只有认不出会话时才要求出示凭据，顺带堵掉"用 401/404 差别探测会话是否存在"。
8. ✅ **MCP 鉴权失败计数**：与 `/api/auth/login` 共用 `abuse.py` 的 IP 锁（60 秒内 10 次失败 → 锁 5 分钟，锁定期连站长口令也返回 429 + `Retry-After: 300`）。

**仍敞着的（下轮再拍）**：

- ⏳ **入站 `?token=` 仍然接受**（`extract_token` 第 4 档）：为不支持自定义 Headers 的客户端与画页 `<img>` 保留，走这条路时凭据本身仍会进访问日志——口径是"只放子凭据"。要彻底堵掉，得给 MCP 单独做只认 header 的凭据提取器，或在 uvicorn 访问日志里剥掉查询串，两者都会动到既有客户端。
- ⏳ **MCP 工具无独立频控**：只有 50 会话与队列上限兜底，外部 agent 疯狂检索会与书架请求抢同一份 SQLite 连接。

### 议题 E：CPU 算力线 —— ✅ 已结案（2026-09-23 决定**不装**）

`.venv` 里没有 rapidocr 3.x（GPU 环境独立在 `.venv-ocr`）。当初提"装 CPU 线"只为一件事：在 v6 下复现旧文档那组 CPU 吞吐数。这件事已经用**不碰应用环境**的办法做完了——用 `.venv-ocr` 的解释器**不带** `--gpu` 跑，得 CPU 2 线程 37.3 页/分、4 线程 32.4 页/分（见 §二），装 `install --cpu` 的理由随之消失。

部署侧本来也不需要它：OCR 引擎只活在 `scripts/`（`ocr_worker.py` / `ocr_lines.py`），Docker 镜像只 `pip install backend/requirements.txt`，**NAS 容器从不做法向推理**；算力机把 `{index}.ocr.json` 写进挂载卷再调 `*/ocr/sync`，NAS 只重建 SQLite FTS5。

服务进程这边**不装任何图像/文本推理的必需依赖**：PDF 扉页自动分话要的 `rapidocr` 按 ADR 0024 是可选依赖（未装则该轨自动跳过，日志一行 WARNING，该书平铺成单章）；语义检索要的 `onnxruntime`+`tokenizers` 也不进 `backend/requirements.txt`（为一句查询的 2ms 让每台部署背 70MB 不值）。两者都不装时功能照常，只是少两条腿，加装方法见 `DEPLOYMENT.md` §5.1.1 / §5.1.2。

### 已结案、别再提的三条

1. **"大图降采样提速"**：前提不成立——rapidocr 3.x 的 `Global.use_preprocess_img` + `max_side_len=2000` 已在进检测前压过一次，且 rec 裁剪图来自这张已压过的图；实测放开反而 0 增 0 减，改小到 1600/1280 会**丢台词**。错题本 #143。
2. **换 Rust OCR（`oar-ocr` 等）**：九成时间花在 ONNXRuntime 的 GPU kernel 内，换语言不动热点；聚类缺陷与引擎语言无关。结案记录同见 #143。
3. **侧车加 `lines` 数组**：已由 `ocr.sh lines` 离线实验台替代（议题"判据改动要重跑推理"的根因解决，且不牺牲阅读器每页解析体积）。

---

## 五、新会话快速启航指南（Prompt Template）

```markdown
请先读 docs/HANDOVER_NEXT_STAGE.md、CONTEXT.md、docs/adr/0017-comic-dialogue-fts-and-bubble-overlay.md
与 docs/PITFALLS.md 的 #137 / #142 / #143。
纸间的台词链路（FTS5 检索 + 气泡高亮 + MCP + 官方 Skill + 单本沙箱直达）与 OCR 算力线
（rapidocr 3.x / PP-OCRv6 small 单轨，GPU 默认）均已完工，`pnpm test:py` 与 `vp check` 全绿。
本轮要讨论的是 HANDOVER 第四节里的待决议题：<在这里点名议题，例如"议题 A：38 本 legacy 侧车切 v6">。
约束：只做该议题必要的改动；`backend/data/` 不得删除；改聚类判据先用 `bash scripts/ocr.sh lines` 离线量，
不要直接重跑全库推理。
```

---

## 六、工作区与备份状态

- 分支 `main`，工作区应当只有本次交接涉及的改动；未 push 的提交以 `git log origin/main..HEAD --oneline` 为准（**push 需要用户明确授权**）。
- 临时备份（`/tmp`，重启即失，长期留存需挪盘）：
  - `/tmp/ocr-sidecar-v6-presplit`——聚类治理前的 201 页 v6 侧车，用于"字数守恒"对照；
  - `/tmp/ocr_raw`——那 201 页的原始识别行 dump，可离线重聚类；
  - `/tmp/cpu-throughput`——吞吐复测的 dump 产物与逐页日志。
- 回退点：`backup/pre-squash-20260923`（19 个修补提交合并前的原始链）。
