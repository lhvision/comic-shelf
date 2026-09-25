# 纸间 · 未决事项（Handover）

> 只记还没解决、有意延后的事项。已落地的能力看 `docs/adr/`、`docs/agents/` 与 `DEPLOYMENT.md`；踩过的坑看 `docs/PITFALLS.md`。

---

## 议题 A：38 本 legacy 侧车切 v6 —— ✅ 已结案（2026-09-25）

- 43 本 1764 页侧车全部是 `engine_track=v6`；`sync` 后 FTS 10889 行（`dialogue` 10189 / `paratext` 700），语义向量 7426 条。
- 日文（按 JM 标签分，4 本）：气泡置信度中位数 0.64 → **0.97**，低于 0.7 的占比 71.7% → 12.4%，台词里假名占 78.2%；固定种子抽 10 条台词，7 条通顺（重跑前只有 2 条能读）。中文 v6 中位数 0.97，抽 10 条全部通顺。
- 结论：日文差是旧引擎造成的（v3 字符表只有 5 个假名），v6 已经补上，**不上 manga-ocr**。

## 语义检索的性能待办（不是 bug）

整条语义查询实测 250~300ms，模型只占 2ms，其余是把命中气泡的原文回表（FTS5 的 UNINDEXED 列没有索引，候选池 50 页 = 264ms）。要压到 ~50ms，可以把回表并入已缓存的向量加载（一次全表扫，随矩阵一起缓存），或给向量表存 FTS `rowid` 走主键 seek。语料翻倍前不急。

## 凭据与暴露面（原议题 D 还没关的项）

已关的各项及理由见 `DEPLOYMENT.md` §9.5。

- ⏳ **入站 `?token=` 仍然接受**（`extract_token` 第 4 档，为不支持自定义 Headers 的客户端保留）：uvicorn 日志已打码，但 NPM 等反代的日志照记。要彻底堵掉，得让 MCP 只从请求头取子凭据，代价是只能在 URL 里填凭据的客户端（`DEPLOYMENT.md` §9.2 方式 B）会失效。等确认自用客户端都支持自定义 Headers 再做。
- ⏳ **MCP 工具无独立频控**：线程池只解决"一次慢调用卡住全站"，不限次数；`/api/mcp/rpc` 也没有会话与队列上限。外部 agent 疯狂检索仍会与书架请求抢同一份 SQLite 连接。现成的最小方案是在 `execute_tool` 入口调 `abuse.check_guest_rate_limit("mcp")`，代价是与访客翻页共用限流参数。
- ⏳ **失败锁记下的 IP 可不可信取决于部署**：`COMIC_SHELF_TRUST_FORWARDED_HEADERS` 默认开，`get_client_ip` 直接信任 `CF-Connecting-IP` / XFF 第一段。经 Cloudflare 且源站不能直连时没问题；源站能直连，这两个头就能伪造，可以每次换 IP 永不触发锁，也可以冒用馆长 IP 把馆长锁在门外。目前只把 `docs/HOMELAB_NETWORKING_GUIDE.md` §6.8 回源印章列为公网部署必配项，默认值不改：改成 false 会让所有走 Cloudflare 的部署都得手动再打开。
- ⏳ **前端把馆长口令存在 localStorage**：`src/api/core/http.ts` 把口令存进 `localStorage`，每个请求都带 `Authorization: Bearer`（后端 `backend/app/auth.py` 的 `extract_token` 第 1 档）。这是一直以来的做法；改口令后前端会反复重放旧值，同一个错误凭据在计数窗口内只计一次，所以不会锁 IP。
- ⏳ **有意延后的小项**（都不构成绕过，按需再做）：
  - 关键词检索里，对访客隐藏的书仍会占 200 行候选池的名额，高频句下访客拿到的结果可能少于可见命中总数（只透露"变少了"，错题本 #139）。语义检索已经先过滤再取前 K，没有这个问题；
  - 事件流对访客仍推带书号的事件（含隐藏本），要过滤得改好几处广播点。payload 保留 `source` / `source_id` 是刻意的：前端任务态（`beginTask` / `endTask` 的缓存与导入自旋）靠它对齐，不能简单粗化，只能按身份过滤；
  - 凭据含非 ASCII 字符时 `secrets.compare_digest` 抛 TypeError，接口 500（不能绕过，但馆长口令设成中文会让鉴权整体坏掉）；
  - 撤销 `MCP_TOKEN` 不会撤销它已签发的直达票据（最长 7 天，票据不记签发来源）；
  - `ocr_lines.py` 的 dump 目录按 umask 创建（通常 0755），多用户机器上可被预建劫持；dump 跨数据源可能重名，且不是原子写入；
  - `ocr.sh run --token` 让机器密钥出现在 `ps` 与 shell 历史里，宜支持环境变量传入；
  - 中间件用前缀 `startswith("/api/mcp")` 放行，将来以此开头的新路由会免中间件鉴权；
  - `/docs`、`/openapi.json` 对公网公开（`COMIC_SHELF_ENABLE_DOCS` 控制）；
  - `mcp.py` 里原有的两处类型警告。

## 其他

- OCR 侧车的 `lang` 写死成 `zh`（`scripts/ocr_worker.py` 写侧车的地方），日文书也标成 zh。等需要按语言分流时再修。
- 界面和代码里与术语表（`CONTEXT.md`）不一致的地方，这次只改了文档：
  - 心形标记应叫"喜欢"：`FavoriteButton.vue` 的"更新收藏状态失败"，`src/api/client.ts` 与 `src/api/modules/library.ts` 注释里的"收藏状态"，`useShelfWebMCP.ts`、`useComicDetailWebMCP.ts` 里的"红心收藏""已收藏 / 未收藏"。筛选里的"只看喜欢"已经是对的。
  - 下载到服务器应叫"缓存"：`ChapterCard.vue`、`ChapterView.vue` 的"离线缓存本话"，`src/api/modules/cache.ts` 的文件注释。`ComicPageImage.vue` 的"画页未离线缓存"指的是 PWA 本地，这个用法是对的。
  - 访客凭证应叫"访客通行证"：`GateView.vue` 的"读者借书证验证"、`GatePinForm.vue` 的"读者借书证"。
  - 车号：`useDiscoveryWebMCP.ts` 把 `source_id` 叫车号；哔咔在 `src/utils/source.ts` 叫"哔咔 ID"，收录面板里又叫"车号"。
  - 单本直达链接在代码里有两个名字：`direct_passes`（`backend/app/db.py` 建表）和 `temp_token`（`backend/app/routers/auth.py` 拼直达 URL）。
  - 馆长：`backend/app/auth.py` 里 role 是 `admin`，属于代码标识符，可以不改。
