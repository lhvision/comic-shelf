# 纸间 · Paper Room

一个本地优先的个人漫画书架。
支持 JMComic 禁漫收录与反混淆解密、哔咔漫画（PicAcg）原生集成与容灾分流，同时提供本地图集与视频拆帧自建工坊。第一次收录后元数据和高清图片全部落在本机；之后浏览、重读、封面都走本地持久化缓存，**0 外部网络冗余请求**。

- **前端**：Vite+（`vp` 工具链 / Vite 8 / Rolldown / Vitest 4 / Oxlint / Oxfmt）+ Vue 3 + TypeScript + Vue Router + Pinia + VueUse
- **样式**：现代原生 CSS（`@layer`、Nesting、`color-mix()`、`oklch()`、`clamp()`）
- **后端**：FastAPI + Pillow + jmcomic + curl_cffi（基于 Provider 抽象，内置禁漫、哔咔与本地图集多源支持）
- **搜图**：`imsearch`（独立 Docker Sidecar，基于 OpenCV ORB 局部特征点 + Faiss 倒排索引）

---

## 已实现功能

- **禁漫天堂（JMComic）收录与图片反混淆解密**：
  - 支持输入 `JM523607`（或纯数字 `523607`）秒级收录；
  - 完整映射禁漫车号、作品标题、登场人物、分类标签、作者、叙述、页数、上传者、上架日期、更新日期、观看数与站内喜欢数；
  - 采用独家 Scramble 向量切片还原算法进行本地无损解码与缓存。
- **哔咔漫画（PicAcg）原生集成与容灾分流**：
  - 官方移动端 HMAC-SHA256 动态签名算法，免手动提取 Token，账号密码配置后全自动登录与 JWT 续期保活；
  - 宽容 ID/链接解析：支持输入 24 位 16 进制 ID，或直接粘贴各种分享镜像站链接（如 `https://picawang.com/comic/5ebe89bf...`）；
  - 完整支持多章节分卷映射，与禁漫、本地漫画全书拍平与阅读器体系 100% 格式对齐；
  - `waka / waifu / heaven` 3-CDN 分流容灾与故障自动轮换降级。
- **来源导航单一真理源与收录工作台解耦架构（Source SSOT）**：
  - 彻底解耦顶栏来源导航（`全部 | 01 禁漫 | 02 本地 | 03 哔咔`）与 Hero 收录表单，废除“嵌套 Tab”反模式与认知冗余；
  - **「全部」视图**：Hero 回归单栏典藏大片版式（`hero--single`），不常驻录入卡片，聚焦书房总揽、诗意导语与藏书统计，配备轻巧的「录入新卷」动态药丸直达对应源；
  - **「单源」专属视图**：Hero 右侧专精呈现对应站点的收录/自建面板（`.is-source-locked` 紧凑单列），消除 961~1180px 视口轨道溢出；
  - **完备逃生通道与无障碍防护**：Hero 左上方常驻 `〔 ← 返回全部藏书 〕` 面包屑锚点，移动端折叠抽屉严格挂载 `:inert` 与 `visibility: hidden` 杜绝幽灵焦点，快捷药丸严格保底 `min-height: 44px;` 触控物理判定区。
- **本地自建图集与拆帧工坊（`/create`）**：
  - 支持收录本地图片合集与视频拆帧（如 `public/tiya-frames`）作为自建漫画，与禁漫元数据、阅读器、以图搜图 100% 格式对齐；
  - 网页端多图上传采用 3 路受限并发队列（`useUploadQueue`），平稳保护服务器 IO；
  - 支持服务器本地路径秒级直扫导入（0 网络带宽开销，需通过 `COMIC_SHELF_ALLOWED_DIRS` 白名单放行）；
  - **本地标识双轨（ADR 0027）**：未填车号时，路径导入用文件夹名或 PDF 文件名（如 `2899054` → `LOC_2899054`），网页上传 / 暂存 PDF 用收录时刻；自填撞车 409，推断名撞车加 `_1`。成功提示带出车号；工坊路径说明写明规则；
  - 路径导入时封面页码按实际画页填写（页数未知不封顶），读取封面时仍夹到 `1..page_count`；
  - 支持单话/多章节增量追加新页面。
- **典藏资料与封面编排（`EditMetadataModal`）**：
  - 馆长可就地修改作品标题、作者、叙述，全站标签自由增删；
  - **自定义 4 张封面展示页码（`cover_indices`）**：允许指定任意全局页号（如 `[1, 12, 35, 78]`）作为书架叠牌与详情页展示封面，修改后即时击穿缓存热更新。
- **多章节体系（合集/系列平滑支持）**：
  - 详情页按「章节目录」摆放（展示章节封面 + 话标题 + 页数 + 本话缓存进度 %），**不铺开几千页**；
  - 点击某话进入「章节子路由（`/comic/:source/:id/chapter/:chapterId`）」只查看该话页面索引，支持上一话/下一话快速切换、修改章节标题与单话删除；
  - 单章节漫画追加新话时，**系统自动平滑升阶为多章节体系**（自动将旧单章封包为「第 1 话」并迁移目录，无缝衔接「第 2 话」）；
  - 目录封面走服务端章节封面端点（池化缓存，失败优雅回落书脊占位）；
  - 阅读器顶栏实时显示“第 X 話 · 标题”；读到末页浮现「本话完 · 下一话」横幅直达；键盘 `N/P` 跨话翻页；
  - 全局页码拍平设计：全书页面统一为 1..N 全局页号，阅读器、封面、继续阅读心智零割裂。
- **全源画卷重新装订与复合章节智能分话（ADR 0020）**：
  - **全源画卷重新装订（Re-binding Protection）**：不仅支持自建漫画，还支持禁漫、哔咔等远端停更漫画的高清画页手动替换与补全，自动打上 `custom_pages: true` 徽标；建立「前端隐藏刷新按钮 + 后端拦截 400 + 底层写入强行保留」三层纵深防御，彻底杜绝远端同步冲垮本地画卷；
  - **单话靶向替换与缩略图局部失效**：支持针对特定章节重新装订或整本替换；单话替换时仅清理本话及后续话的缩略图缓存，保留其他历史章节秒开体验；
  - **平铺复合文件名自然排序与自动聚类分话**：支持长篇平铺单目录复合文件名（如 `1-1.avif`, `1-2.avif`, `2-1.avif` ...），后端内置自适应聚类正则与自然排序，无需手工建立子文件夹，一次性拖入即可智能拆分并聚类为「第 1 话」、「第 2 话」... 并平滑升阶；
  - **前置二进制魔数防伪**：服务端上传流经严格 `PIL.Image.open().verify()` 魔数与完整性校验，杜绝伪装文件或损坏损坏字节污染本地藏书。
- **PDF 画卷无损解包、多卷合集导入与双轨智能分话（ADR 0024）**：
  - **原生内嵌流 1:1 无损提取**：优先无损导出 PDF 底层 Image XObject 原始图片流（JPG/PNG/WebP），0 重编码、0 像素失真，百页秒级落盘；遇复合矢量版面自动降级至 300 DPI 高保真光栅化渲染；
  - **双轨智能分话探测（Dual-Track Chapter Detector）**：内置大纲书签优先解析（轨 1）；无书签扫描版自动调用本地轻量 OCR 嗅探纸质目录与各话扉页（轨 2），自动切分出「卷首 / 目录」与各正文话数，自建工坊提供所见即所得的暂存分话确认面板；
  - **多卷合订目录一键入库（Multi-Volume Ingest）**：指定包含多卷 PDF（如 `第01卷.pdf` ~ `第07卷.pdf`）的服务器目录，系统按自然文件名升序自动将各卷映射为独立章节，全书页码平滑串联并生成各卷封面；
  - **全场景增补与重装**：追加新话（`AppendPagesModal`）与重新装订（`ReplacePagesModal`）全面支持拖拽 `.pdf` 文件与服务端路径。
- **画卷生命周期与多粒度自愈删除机制**：
  - **整本漫画彻底删除**：详情页一键「从纸间移除」，物理清除画页、多级 WebP 封面、360 缩略图，并级联注销 SQLite 索引与全文检索台词数据；
  - **单章节删除与页码自愈**：删除指定章节后，系统自动无缝压实剩余章节的起始页码与全书全局单调页码（$1 \dots N$ 严格连续不留断层），自动重算全书与章节封面；
  - **临时暂存物理释放与 1 小时自动 TTL**：支持手动撤销暂存，后台守护进程定期清理孤儿暂存区；5000 页上限与 1GB 分块流式落盘坚固防御解压炸弹与 OOM。
- **沉浸阅读器**：
  - 竖向连续 / 竖向翻页 / 横向翻页三种模式；
  - **排版作用域双轨制（Dual-Scope Reader Preferences）**：阅读器设置面板提供「📖 本作偏好」与「🌐 全局默认」双轨体系，支持即改即分离、实时视口联动、一键「恢复跟随全局」与历史脏基线静默自愈，彻底告别配置黑盒；
  - **条漫无缝长卷拼接与自适应画卷（Webtoon Seamless Stitched View）**：针对韩漫/条漫长卷切片撕裂痛点，提供「无缝长卷拼接」开关，彻底拔除行内占位页脚，消除页间黑缝与单页阴影；施加 -1px 亚像素微咬合（Micro-Overlap）杜绝高 DPR 缩放漏缝；视口悬浮画卷页标（`021 / 045`）滚动感应淡入淡出；排版硬约束锁定单页全宽；单本偏好独立记忆，且命中 `条漫` / `韩漫` / `Webtoon` 标签时智能自适应首开；
  - 横向模式支持左右滑动切页、鼠标滚轮自动映射为横向滚动，可自由切换“左→右 / 右→左（日漫）”；
  - 每屏支持 1 / 2 / 4 页多列排版；
  - 滚动驱动进度条（CSS Scroll Timeline + JS 兜底）、页码浮动指示、键盘翻页、适应宽度 / 适应高度、全屏沉浸；
  - **全幅加载骨架与独立装订插画**：每次进入漫画随机选取一张角色看板插画并伴随呼吸微光，整本书保持风格一致且彻底杜绝排版跳动；
  - 自动翻页计时辅助（预设 5/10/15/30 秒与 1~300 秒自定义，手动操作重置计时）；
  - 每本漫画独立记忆“上次阅读位置”，详情页一键直达“继续阅读”。
- **局部特征以图搜图（Visual Search）**：
  - 搜索框集成 Chrome Lens 风格识图芯片（带微缩预览、点击放大查看、一键清除 `×`）；
  - 支持直接剪贴板粘贴截图（`Ctrl+V`）、相机图标选择文件、图片拖拽到书架；
  - 局部 ORB 特征匹配：即使只有漫画的一小块分镜、表情包或台词截图，也能毫秒级定位是哪一本作品及具体匹配页码；
  - 书架卡片呈现匹配置信度高亮（如 `第 12 页 · 94%`），一键直达阅读器该页；
  - 支持多模态复合检索（图搜结果与文本关键词、标签 AND 组合筛选）；
  - 优雅降级：未启动识图服务时前端自动呈现提示引导，常规文本与标签检索 100% 正常运行。
- **访问安全、自设 PIN 码认领与全屏 Zero-DOM 门禁（ADR 0011）**：
  - **馆长与专属访客通行证**：环境变量 `COMIC_SHELF_SECRET` 控制馆长全权门禁；馆长在 Web 端「访客簿」中可动态派发个人专属通行证（支持设置 7/30/90/180天/永久有效、免密直达链接、一键续期与密钥换新）；未授权者 100% 拦截（HTTP 401），彻底杜绝公网扫描滥用；
  - **读者自设 PIN 码认领制（Reader PIN Claiming）**：读者首次点开通行证时自行设定 4~6 位纯数字 PIN 码确立号主归属（经 PBKDF2-HMAC-SHA256 100,000 轮安全哈希）；未授权者无法通过 PIN 校验被坚决拦截，彻底阻断群聊转发偷用与恶性互挤；支持合法号主 PIN 码防护下的多端 LRU 漫游自愈；
  - **全屏零残留门禁（Zero-DOM Gate View）**：前端根级采用两态解耦，未鉴权前绝对不挂载应用外壳与任何业务组件，屏幕仅渲染独立门禁纸室，DOM 树物理级 0 残留，彻底杜绝控制台修改 CSS 或删除节点窥探；
  - **个性化数据隔离与全局隐藏**：每位访客的红心收藏与跨端阅读进度基于轻量 SQLite WAL 严格隔离，互不干扰；馆长标记隐藏的漫画对所有访客统一 404 不可见；
  - **现代浏览器级图片防盗链**：结合 `Sec-Fetch-Site: cross-site` 与 `Referer` 拦截，杜绝外站把纸间当图床直连读取解密成品图。
- **万级书库受控分页与 SQLite 影子索引（ADR 0015）**：
  - **毫秒级查询与动态隔离**：在本地单文件数据库中建立 `comics_index` 影子索引，万级藏书切页与检索 < 2ms，动态 `LEFT JOIN` 各用户独立阅读进度与喜欢；单真理源（`album.json`）不变；
  - **接口职责解耦**：`/api/library` 专司受控分页切片，`/api/library/facets` 专司全貌统计与高频前 30 标签，切页 0 冗余带宽损耗；
  - **以图搜图穿透检索**：识图结果支持通过 `ids` 精准拉齐历史深层藏书，杜绝分页历史断层；
  - **跨端 SSE 变动感知**：多标签页/多设备发生增删或后台缓存完成时，静默对齐首屏切片与全貌统计。
- **万级藏书 Web Worker 检索卸载与三层防御架构（ADR 0018）**：
  - **双轨自适应计算**：<1000 本纯函数毫秒级直算，$\ge 1000$ 本无感卸载至专用 `libraryFilter.worker.ts`，主线程击键长任务归零（耗时 `< 0.5ms`），输入法绝不吞字、光标 120 FPS 绝不掉帧；
  - **极简 ID 传递契约**：线程间仅交换微量参数与有序 ID 数组，彻底消灭全量对象序列化反序列化风暴；
  - **DOM 受控折叠与软封顶**：`usePaginationFold` 受控折叠锁定渲染节点预算（搜索即刻重置步长为 12 本，展开软封顶 120 本），配合 `contain: layout style` 与原生图片懒加载，兼顾极端数据量展开与卡片悬浮外阴影零裁切。
- **案头藏书、阅读状态分段胶囊与归档专匣（Shelf Drawer & Segmented Tabs）**：
  - **阅读状态单选三态胶囊**：工具栏提供典雅的 `[ 全部 | 在读 | 已读 ]`（`readingStatus`）分段选项卡，与独立的「只看喜欢」微件正交并列，URL Query 双向联动，彻底杜绝交集为空的白屏反模式；
  - 书架默认「最近收录」排序下实行两层分桶：案头主书架展示未读与在读作品，已读完藏书整体沉底归档至底部的「卷末归档专匣」；
  - 抽屉支持语义化一键折叠展开、无级尺寸插值（`interpolate-size: allow-keywords`）平滑高度进出场动效、微降权质感陈列，且在全架书目均已读完时智能感知展开。
- **书架渲染性能、阈值流式展开与 60 本安全刹车（Safety Brake System）**：
  - 每本漫画展示 4 张封面，默认采用 **12 本/批（对应 12 × 4 = 48 张封面图）** 的增量预算；
  - **前 5 批视口触底自动加载**：基于 VueUse `useIntersectionObserver` 触底哨兵自动无感平滑展开，消除反复点击割裂；
  - **60 本安全刹车（Safety Brake）**：达到 60 本阈值后自动暂停无感滚动，在网格末尾露出折叠卡，提供「继续向下探索 24 本」与「展开全部」（240 本安全上限），兼顾探索自由度并彻底杜绝万级图片导致移动端标签页 OOM 闪退，确保底部的卷末归档专匣平滑可达；
  - 卡片使用 `contain: layout style` + `container-type: inline-size` 严格隔离，杜绝浮动裁切瑕疵。
- **统一矢量图标集、通用胶囊与现代浮层基建**：
  - 全站图标收敛到 `src/components/icons/`（1.8px 细线条描边 / 朱砂质感），零 Unicode 伪字符（`✕`/`✓`）；
  - **通用微件胶囊体系（`AppChip`）**：单一真相源收敛全站分类标签、筛选切换器（“只看喜欢”/“只看已读”）、计数值与可移除标记，原生支持多态语义（`<span>` ⇄ `<button aria-pressed>`）；
  - **多标签复合筛选与交集（AND）淘书**：全站标签筛选全面支持复合多选，点选时溢出抽屉保持常驻并动态呈现已选项数；纯内存响应式状态驱动，解耦路由 URL 干扰，保障跨页面导航原生流畅；
  - 基于 HTML Popover API 与 CSS Anchor Positioning 规范构建现代浮层，包含 `Modal`、`AppPopover`、`AppDropdown` 与带悬停安全桥的 `AppTooltip`。
- **PWA 独立安装、纸室离线模式与端侧自愈流水线（ADR 0005）**：
  - **标准 PWA 规范支持**：完整支持桌面/移动端独立窗口安装（Standalone）、离线秒开与后台静默更新，符合 W3C Web App Manifest 与 Service Worker 规范；
  - **端侧元数据持久化与 0ms 离线水合（IndexedDB SWR）**：建立 `comic-shelf-meta` 本地轻量数据库，断网冷启动秒级展示上次书架快照与离线藏书；多维检索与标签筛选在离线状态下 100% 可用，断网时自动无感触发静默离线接管；
  - **全链路离线漫游韧性**：离线进入详情页、章节页或阅读器自动降级读取 IndexedDB 详情或书架概要占位，**绝对不强退首页**；未离线画页展示水墨纸印缺页骨架；
  - **端侧离线记账与联网对齐队列（Offline Reconciliation Pipeline）**：断网翻页阅读进度与喜欢变动自动打上用户身份签名写入本地事务队列；网络自愈时按用户隔离自动批量回写后端 SQLite 并触发 SWR 静默刷新；
  - **优雅装订提醒（Prompt 模式）**：前端采用非侵入式悬浮装订横幅（`UpdateBanner`），阅读器沉浸模式下自动隐退避让，新版本随时在顶栏设备卡片内就绪装订；
  - **任务驱动型系统事件流与多标签广播（Task-Driven SSE & BroadcastChannel）**：常态浏览 0 pending 长连接悬挂；仅在导入或下载预缓存等活跃任务时自适应拉起 SSE 并在 5 秒平滑防抖后注销；同设备多标签页通过原生 `BroadcastChannel` 0 流量毫秒级互通；0 CPU 轮询开销；
- **漫画台词全文检索、快捷指令中枢与阅读器气泡呼吸高亮（Dialogue Search, Slash Commands & Dedicated DB）**：
  - **台词专库垂直解耦（`comic_dialogues.db`）**：在万级与十万级规模下，将 FTS5 Trigram 倒排索引虚拟表及增量同步元数据从主库物理隔离为 `comic_dialogues.db`，海量离线 OCR 批量写入通道与用户核心状态（翻页打点/收藏）零写锁争抢（Zero Lock Contention），彻底杜绝 `SQLITE_BUSY` 锁异常；
  - **原生 Trigram 倒排全文检索与短词防爆守卫**：基于 SQLite 3.34+ 原生 `tokenize='trigram'` 构建 `comic_dialogues_fts` 虚拟表，零第三方 C 库依赖，秒级模糊命中中日文无空格对白；前后端硬性门禁 `< 2` 字符阻断，彻底消除 Trigram 在极短词下全表 `LIKE` 扫描导致的 100% CPU 锁死；
  - **快捷指令中枢与命令胶囊（Slash Commands & Command Chip）**：搜索栏支持 `/` 快捷指令唤醒菜单（`/台词`、`/车号`、`/作者`、`/随机`），激活台词检索后提取为朱砂印章样式的命令胶囊（`〔 💬 台词 × 〕`），同时将书架卡片过滤严格冻结置空，杜绝“一搜台词列表就空”的体验断层；
  - **简繁双向互通归一化**：内置 3,881 对标准简繁映射词表，输入简体自动召回港台繁体本子，输入繁体亦能命中大陆简体翻译；
  - **书架搜索栏水墨联想浮层（`DialogueSearchPopover`）**：输入文字时防抖 300ms 异步全文检索，在搜索栏正下方展开纸本浮层；实行**静默伴生原则**（0 条结果时静默隐藏，不遮挡书架已过滤作品）；纯声明式解析分镜高亮（零 `v-html` 杜绝 XSS）；支持 WAI-ARIA Combobox 无障碍键盘视口跟随（`scrollIntoView`）与智能回车直达首项；
  - **多模态伴生协议解耦**：画页伴生数据 `{index}.ocr.json` 采用归一化百分比坐标 `[ymin, xmin, ymax, xmax]` ∈ [0, 1]，与图片原始物理分辨率彻底解耦；
  - **阅读器气泡呼吸微光直达**：URL 支持携带 `?page=42&bubble_box=0.1,0.2,0.3,0.4`（同页其余命中气泡由 `&bubble_boxes=a;b;c` 一并带来：代表气泡呼吸、其余命中气泡静态描边，前后端都按一页最多 6 处封顶），画卷视口加载就绪后，在台词气泡上浮现暖纸朱砂金色微光（2.2s 脉冲渐隐），强制挂载 `pointer-events: none` 零阻碍交互手势，底图加载门禁防止动画提前夭折，顶部分镜自适应翻转防溢出；
  - **幽灵索引自愈与删改联动**：漫画删除或重新装订（`replace-pages`）时原子清空 FTS5 记录，多章节分卷自动映射至全书拍平物理页码；
  - **多层纵深安全与沙箱隔离**：严格过滤 `hidden_from_guest` 隐私漫画，禁止未授权访客嗅探；路径穿越沙箱硬边界校验；查询入参限制 `max_length=200` 防 DoS；对白摘要严格转义彻底免疫 XSS；
  - **NAS 离线同步脚本**：提供 `python3 scripts/sync_ocr.py`，智能感知 NAS 挂载路径（`/mnt/nas_manga`）并一键批量建立台词索引。
- **智能体协同中枢与模型上下文协议（Model Context Protocol / MCP & WebMCP）**：
  - **三模服务端 MCP 协议架构**：FastAPI 提供标准 JSON-RPC 2.0 协议支持，包括 SSE 流式传输（`/api/mcp/sse` 与 `/mcp/sse`）、长连接消息端点（`/api/mcp/messages`）、直连 HTTP RPC（`POST /mcp` 与 `/api/mcp/rpc`）以及原生 Stdio 命令行模式（`python3 backend/app/mcp_server.py`），无缝直连 Claude Desktop、Antigravity、Cursor、飞书 Bot 与局域网微服务；SSE 握手只回发一次性 `session_id`（凭据不进 URL、不留反代日志），鉴权失败按登录同一套 IP 锁规则计数（与网页登录分开记账）；
  - **9 大原子数据工具**：`search_by_image`（局部特征识图）、`search_by_dialogue`（台词倒排全文检索）、`search_by_meaning`（按意思找台词，字面不通也能召回）、`query_shelf`（多维藏书筛选）、`get_comic_detail`（完整元数据与章节）、`recommend_unread`（智能未读书籍淘选）、`create_direct_pass`（单本沙箱免密直达凭据签发）、`get_shelf_stats`（书架聚合统计）、`get_story_context`（按页码区间取原始台词流，供分镜/脚本/对话生成管线）；
  - **单本沙箱临时直达凭据（Single-Book Sandbox Pass）**：外部智能体定位名场面后，可一键签发带 TTL（默认 2 小时，最长 7 天）的高熵临时阅读 Token 与直达链接（`/comic/{source}/{id}/read/{page}?temp_token={token}`）；访客点开链接自动静默免密登入并锁定在单本沙箱中，**严格禁止窥探书架全景与其他作品（HTTP 403 阻断）**，写操作一律拦截；配备画页 `Token + IP` 复合滑动窗口频控（180 页/分钟），杜绝外链滥用抓取；
  - **前端原生 WebMCP 视口控制**：基于 VueUse 15 `useWebMCP` 规范，在书架、详情、发现与阅读器四大核心页面向 Chrome 原生 `document.modelContext` 声明式注册交互控制工具（支持翻页/跳页/章节跳转/排版切换/缓存触发），非兼容浏览器自动优雅空跑；
  - **内网机器专属密钥（Machine API Token）与 MCP 子凭据分轨鉴权**：支持配置 `COMIC_SHELF_MACHINE_TOKEN` 供局域网应用与自动化流水线调用 REST API 与入库同步；另有 `COMIC_SHELF_MCP_TOKEN` 专供外部智能体解锁 MCP 工具（需同时配置 `COMIC_SHELF_SECRET` 才生效），可随时更换撤销；机器密钥进不了 MCP，与网页端馆长密码完全解耦互不干扰；
  - **客户端配置指南**：关于局域网 NAS（TrueNAS/群晖）SSE 模式直连、Claude Desktop / Cursor 配置模板与本机 Stdio 管道集成，请参阅 **[DEPLOYMENT.md §9 MCP 智能体配置与连接指南](DEPLOYMENT.md#9-mcpmodel-context-protocol智能体配置与连接指南)**。
- **分级离线缓存体系与安全边界**：基于 Workbox 实现 App Shell 核心资产预缓存 + 漫画画页 Cache-First（最大 3000 篇目 LRU 淘汰）；日常清理仅释放画页缓存、保留元数据快照；彻底重置才清空所有 DB；**绝对不触碰服务器已下载珍藏数据（`backend/data/`）**。

---

## 本地运行与开发

项目使用 Vite+ 工具链，日常命令使用 `vp`（或通过本地 npm scripts 调用）。

```bash
# 1. 初始化 Python 后端依赖（创建 .venv 并安装依赖）
pnpm setup:py

# 2. 安装前端依赖
vp install
# 或 pnpm install

# 3.（可选）台词 OCR 算力依赖——只有要跑 scripts/ocr.sh 的机器需要，读者端不用装
bash scripts/ocr.sh install       # 检测到 NVIDIA 显卡即在项目内建 .venv-ocr/ 并默认走 GPU
# 必须在 setup:py 之后执行：否则脚本会拿宿主 python 装依赖（Homebrew 的 python 会直接拒绝）
# Apple 机器装不出加速器（onnxruntime 无 macOS CUDA 构建），留 CPU 线即可，大批量交给带卡机器

# 4. 启动开发环境（前后端热重载）
pnpm dev:all

# 或分别启动：
pnpm api       # 后端 FastAPI（端口 8000）
vp dev         # 前端 Vite+（端口 5173，已自动反代 /api 到 8000）
```

常用质量与维护命令：

```bash
vp check                               # 格式化 + Lint + 类型检查
vp test src/__tests__/<Target>.spec.ts # 精准单测验证（严禁日常全量）
pnpm reindex:image                     # 增量追加以图搜图索引（秒级完成，自动适配本地/Docker环境）
vp build                               # 生产打包
```

> 💡 **以图搜图索引构建**：批量收录或缓存新漫画后，随时可在终端执行 `pnpm reindex:image` 秒级追加新图特征至倒排索引；若宿主机未编译 `imsearch`，脚本会自动检测正在运行的 Docker 识图容器并在容器内执行。更多说明详见下文以图搜图章节。

---

## Docker & TrueNAS 部署（推荐）

纸间支持 Docker Compose 一键启动或 NAS（TrueNAS Scale / Unraid / 群晖）图形化部署，开箱即用：

API 固定单工作进程，启动时对 `library/.writer.lock` 加排他锁，同一书库只运行一个 API 实例；下载和图片处理仍可在线程内并发。存储异常回退范围与备份处理见 [并发与故障恢复边界](DEPLOYMENT.md#11-本地书库的并发与故障恢复边界)。

```bash
# 方式 1：双容器一键启动（含以图搜图，需 CPU 支持 AVX2）
docker compose up -d --build

# 方式 2：极简轻量单容器启动（推荐低功耗 NAS 如 N5095/N5105/J4105，加 --no-deps 跳过搜图避免 132 报错）
docker compose up -d --no-deps --build paper-room

# 常用启停运维：
# docker compose down                # 停止并移除容器
# docker compose logs -f paper-room  # 查看主服务运行日志

# 访问阅览室：浏览器打开 http://<服务器IP>:8000
```

> **⚡ 容器环境变量与部署核对（Docker 零依赖，无需 .env 文件）**：
>
> - 🔴 **公网 / VPS 部署唯一必配**：设置容器环境变量 `COMIC_SHELF_SECRET="你的管理密码"`（可在 `docker-compose.yml` 的 `environment` 节直接填入，或在 NAS 图形界面添加；纯内网家庭环境直接留空免密）；
> - 🟡 **存储持久化生命线**：将宿主机存储卷映射至容器内的 `/app/data`（所有漫画原图、元数据与搜图索引均保存在此处）；
> - 🟢 **其余环境变量**：内置默认值（8000 端口、3 路防封下载并发、4 路缩略图限流等），初次部署通常无需调整。
>
> 📖 **完整部署指引与参数字典**：包含 TrueNAS Scale、Unraid、群晖 NAS 挂载配置、环境变量详解、反向代理与权限排查，请参阅 **[DEPLOYMENT.md](DEPLOYMENT.md)**。

---

## 部署后如何触发以图搜图索引（`reindex:image`）

纸间对已缓存的漫画采用**增量索引机制**：导入漫画时不会阻塞主线程，由管理员在批量导入后按需更新特征库。

### 1. Docker Compose 容器内一键触发（最常用）

无需在服务器安装 Rust 或任何依赖，直接在终端执行：

```bash
# 【日常增量追加】扫描新增漫画并秒级推入倒排索引（旧特征 100% 保留，零重复计算）：
docker compose exec imsearch sh -c "imsearch add /app/data/library && imsearch build"
docker compose restart imsearch

# 【全量重置重训】重新训练 512 聚类中心并重建索引（首次初始化或强制重构时使用）：
docker compose exec imsearch sh -c "imsearch add /app/data/library && imsearch train -c 512 -i 800 -m 30 && rm -f /root/.config/imsearch/invlists.bin && imsearch build"
docker compose restart imsearch
```

### 2. 宿主机 / WSL2 一键服务运维（分布式高性能识图）

当 NAS 为低功耗 CPU 时，可在电脑/WSL2 上运行 `imsearch`，通过 SMB 挂载 NAS 漫画目录进行高性能识图：

```bash
pnpm imsearch start    # 后台启动识图服务 (:8765)
pnpm imsearch stop     # 停止服务
pnpm imsearch restart  # 重启服务
pnpm imsearch status   # 查看运行状态与健康度
pnpm imsearch reindex  # 日常增量追加新本子特征并自动热重载（秒级）
pnpm imsearch train    # 全量重新训练 512 聚类中心并重建索引
pnpm imsearch logs     # 查看实时搜索日志
```

### 3. 宿主机一键脚本智能代理（单机 Docker 模式）

如果你在项目根目录下，也可直接运行：

```bash
# 日常增量构建（脚本会自动检测正在运行的 Docker 识图容器并自动在容器内执行）
pnpm reindex:image
# 或直接运行
bash scripts/reindex.sh

# 全量重训模式
bash scripts/reindex.sh --full
```

---

## 存储路径与数据结构

数据目录统一受 `COMIC_SHELF_DATA` 控制（默认 `backend/data`，Docker 内为 `/app/data`）：

```text
$COMIC_SHELF_DATA/
├── jm_html_domain.json                  # 禁漫网页域名 6 小时缓存
├── jm_session.json                      # 禁漫 AVS 会话凭据与 Cookies 缓存（0o600 私有安全权限）
├── picacg_session.json                  # 哔咔会话凭据与 JWT 缓存（0o600 私有安全权限）
├── discovery/                           # 官方榜单数据分源落盘（{source}_{timeframe}.json，封面纯内存代理零落盘）
├── imsearch/                            # 识图索引与特征库（centroids.bin / invlists.bin / imsearch.db）
└── library/
    └── <source>/                         # provider key：jm / pica / local
        └── <source_id>/                  # 禁漫车号、哔咔 ID 或自建 source_id（如 523607 / 5ebe... / tiya-frames）；本地印章为 LOC_{source_id}
            ├── album.json                # 元数据 + favorite + pages[].cached + chapters[] + cover_indices[]
            ├── remote.json               # 远端 URL + scramble_id + decode_version
            ├── pages/00001.webp          # 单章节：已解密拼好的成品页（扁平）
            ├── pages/<chapter>/00001.webp# 多章节：页面按章节 ID 分落子目录
            ├── covers/001.jpg            # 展示封面（720px 基准 JPEG，与 WebP 双模并存）
            ├── covers/001_360.webp       # 首屏展示缩略图（Accept: image/webp 内容协商，按需生成）
            ├── covers/chapters/<cid>.jpg # 章节封面池（按需生成，支持 WebP 与 360 缩略规格）
            ├── thumbs/00001.jpg          # 单章节：360px 索引缩略图
            └── thumbs/<chapter>/00001.jpg# 多章节：分章节 360px 缩略图
```

> **全书拍平设计**：`album.json` 的 `pages` 始终是全书拍平的全局页码表（1..`page_count`），每页记录所属 `chapter`；`chapters[]` 记录各章节的 id、标题、页数及起始全局页（`start`）。单章节与多章节数据结构向前兼容，旧缓存零迁移。

---

## 接口与开发文档索引

纸间拥有完备的接口定义与系统设计文档体系：

| 文档                                                           | 内容与定位                                                                                                                                   |
| :------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------- |
| **交互式 API 文档**                                            | 服务运行时的 `/docs`（Swagger UI）与 `/redoc`，由 FastAPI 自动生成；默认关闭，设 `COMIC_SHELF_ENABLE_DOCS=true` 才开放，公网部署建议保持关闭 |
| **[CONTEXT.md](CONTEXT.md)**                                   | 纸间领域模型与术语表（单一语义源，核心概念、收藏夹状态、阅读器与基础设施定义）                                                               |
| **[DEPLOYMENT.md](DEPLOYMENT.md)**                             | 生产容器化部署全景：Docker Compose、TrueNAS Scale / Unraid / 群晖 NAS 挂载配置、环境变量详解、反向代理与权限排查                             |
| **[docs/PITFALLS.md](docs/PITFALLS.md)**                       | 错题本（每条“症状 / 根因 / 红线”，按编号或关键词查）                                                                                         |
| **[CSS / JS 技术雷达](docs/CSS_RADAR.md)**                     | [CSS 技术雷达](docs/CSS_RADAR.md) 与 [JS 技术雷达](docs/JS_RADAR.md)（浏览器兼容性快查表、已落地特性的用法与降级方案）                       |
| **[docs/agents/architecture.md](docs/agents/architecture.md)** | 后端架构设计、数据存储模型、Provider 扩展体系、安全门禁与 SSE 单向事件流                                                                     |
| **[docs/agents/frontend.md](docs/agents/frontend.md)**         | 前端视图与 Composable 地图、阅读器分页与手势、PWA 离线缓存与性能策略                                                                         |
| **[DESIGN_NOTES.md](DESIGN_NOTES.md)**                         | 纸间设计系统规范（Living Design System）、品牌哲学、色彩/组件层级与核心设计定律                                                              |
| **[docs/adr/](docs/adr/)**                                     | 架构决策记录（Architecture Decision Records，涵盖系统重大架构抉择）                                                                          |

---

## 扩展其他漫画站（Provider 体系）

1. 在 `backend/app/providers/` 新建文件，继承 `ComicProvider`；
2. 实现 `normalize_id`、`fetch`（只抓取元数据与图片 URL，不下载实体图片）和 `download_page`；
3. 在 `backend/app/providers/registry.py` 中注册该 Provider。

存储层、缓存管理、API、前端封面与阅读器将自动获得新站点支持，前端不需要改动任何业务渲染代码。

---

## 开源协议与鸣谢（License & Acknowledgements）

本项目基于 **MIT License** 开源。感谢以下优秀的开源项目与社区生态：

- [JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python) (MIT License) — 提供了可靠的禁漫元数据解析与图片反混淆解密算法。
- [PicaComic](https://github.com/wgh136/PicaComic) (MIT License) by @wgh136 — 为哔咔移动端 REST 接口规范、HMAC-SHA256 签名机制与分流端点提供了宝贵且权威的开源参考。
- [curl_cffi](https://github.com/lexiforest/curl_cffi) (MIT License) — 提供底层现代 TLS 指纹模拟与高性能 HTTP 客户端能力。
- [imsearch](https://github.com/lolishinshi/imsearch) (GPL-3.0 License) by @aloxaf — 高性能二次元局部特征点图片搜索引擎（本项目通过独立容器 HTTP API 网络隔离调用，严格保障纸间项目的 MIT 开源合规性）。
- [FastAPI](https://fastapi.tiangolo.com/) & [Uvicorn](https://www.uvicorn.org/) — 高性能 Python 异步后端。
- [Vue.js](https://vuejs.org/) / [VueUse](https://vueuse.org/) / [Pinia](https://pinia.vuejs.org/) — 优雅轻盈的前端生态。
- [Vite+](https://viteplus.dev/) — 现代化统一前端工具链。

---

## 版权提示

请只缓存你有权保存、且用于个人学习交流的内容。不要公开部署、不要传播。
