# CONTEXT.md — 纸间 · Paper Room 领域术语表

> 本项目只有一份 context（单体前端 + 后端）。本文件是纯术语表，不含实现细节。
> 术语达成共识后即时更新；ADR 单独放 `docs/adr/`。

## 品牌与定位

- **纸间（Paper Room）**：产品名。定位是"本地优先的个人漫画收藏夹"，不是公开站点，也不是泛化爬虫。
- **私人阅览室 / 卡片目录（Reading room / Card catalog）**：产品视觉语言的隐喻——暖纸色、墨色、朱砂色，像图书馆卡片与旧书脊；明确禁止紫色渐变、玻璃拟态堆叠、霓虹、emoji 当图标。

## 核心概念

- **本子（Comic / Book）**：书库里的一条漫画作品记录。用户视角的"一本"。
- **车号（display_id）**：作品在来源站点的唯一编号（如禁漫 `523607`），是"放进纸间"时用户需要输入的东西。`display_id` 与 `source` 组合才是全局唯一。
- **来源（Source / Provider）**：作品的远端出处（目前只有 `jm` 禁漫；预留 `picacg` 哔咔）。每个来源有独立的 `short_label`、编号格式、数据目录 `library/<source>/<source_id>/`。
- **收录（Import）**：把一本作品"放进纸间"的动作。规则：先查本地 `album.json`，命中则 `from_cache=true` 绝不请求远端；首次收录缓存前 4 页做封面。
- **本地化（Caching / Cachify）**：把页面图片下载到本地（`cached_pages` / `cache_complete`）。图片必须走解密工具，禁止直接保存下载字节。
- **封面（Cover）**：作品的预览图，取自首页前几张；书架卡片与详情页轮播的视觉锚点。
- **喜欢（Favorite）**：给一本作品打上的"已喜欢"标记，可用来筛选（只看喜欢）。
- **页面索引（Page index）**：详情页展示所有页码缩略图的区段，点击任意页直接进阅读器；为性能按 48 页增量渲染。
- **章节（Chapter / 話）**：一本多话合集里的一个独立 photo。模型上每章有 `{id,index,title,page_count,start}`，
  `start` 是该章在**全书全局页码**里的起始页。多话作品详情页按「章节目录」摆放（封面 + 章节信息），
  点某话进入「章节子路由」看该话页索引；阅读器页码/继续阅读/封面仍走全局页码。单章节作品 `chapters` 为空。
- **增量更新（Incremental Refresh / Incremental Update）**：针对书库已有漫画的更新动作。保持本地已有图片与元数据缓存不变，仅拉取远端新增章节（Chapter）或新增页码（PageRecord）的图片信息与元数据；单话升级为多话时自动无缝物理迁移旧文件至首话目录。
- **阅读器（Reader）**：沉浸式读图界面，支持三种模式。见下方"阅读器"组。

## 收藏夹状态

- **书库（Library / Shelf）**：用户的全部收藏集合，书架页展示。
- **标签（Tag）**：作品上的分类标签，书架页可筛选；标签数量用于排序展示。
- **筛选（Filter）**：书架页对收藏的检索手段——标题/车号/作者/标签关键词、标签点选、"只看喜欢"。
- **以图搜图（Visual search / Image search）**：通过上传/粘贴截图特征比对，快速定位所属本子及具体匹配页码的检索能力。
- **识图芯片（Image search chip）**：搜索输入框内呈现当前检索图片的紧凑卡片微件，包含微缩预览、点击查看大图与清除按钮（×）。
- **匹配结果（Match result）**：识图检索命中的作品（`source`/`source_id`）、具体页码（`page_index`）与匹配置信度。

## 阅读器

- **阅读模式（Reader Mode）**：三种——`竖向连续`（垂直滚动无吸附）、`竖向翻页`（一次一屏）、`横向翻页`（左右滑动，支持 RTL 日漫方向）。
- **每屏页数（Pages per view）**：一次显示 1 / 2 / 4 页；窄屏（<=680px）只允许 1/2。
- **图片适配（Fit）**：`适应宽度` 或 `适应高度`，影响图片在屏内的缩放方式。
- **继续阅读（Last-read）**：每本作品独立记录"上次翻到第几页"（`comic-shelf:last-read:<source>/<sourceId>`），详情页据此显示"继续阅读"。
- **自动切换（Auto-turn）**：按固定间隔（5/10/15/30 秒）自动翻到下一屏的辅助功能；开启后 HUD 常驻，手动操作重置计时。
- **阅览室暗色环境（Reader room）**：阅读器固定的深色环境（`--reader-*` tokens），不随系统亮/暗主题切换，与书房（书架首页）的亮色纸面刻意区分。

## 基础设施

- **书库数据（Library data）**：后端 `backend/data/library/` 下的本地持久化，不得删除。
- **设计令牌（Design tokens）**：`src/styles/tokens.css` 中的颜色/间距/字号/圆角/动效体系，UI 改动必须收敛到 token，禁止硬编码漂移。
- **实验开关（Experiment）**：`HTML-in-Canvas 卡片`——把书架卡片整块 DOM 绘制进 canvas 的实验性渲染路径，由实验 store 控制开关。
- **插画资产池（Illustration Pool）**：全站看板角色与加载插画的统一发现与随机轮换池（`/loading-*.webp`），支持零配置自动感知新资产。
- **环境暗印水印（Ambient Watermark）**：页面与弹窗底层的极浅角色暗纹，以纸质水印质感呈现，亮色与暗色模式下均保持极低对比度，绝不干扰前景内容与文字可读性。
- **全幅加载占位（Full-frame Page Loading）**：阅读器单页加载时与漫画页面等比撑满的骨架占位，大画幅展示装订插画并彻底消除排版跳动。
- **访问密钥（Auth Secret）**：环境变量 `COMIC_SHELF_SECRET` / `COMIC_SHELF_AUTH_TOKEN`。配置后全站开启轻量门禁防护，未授权禁止访问 API 与漫画图片；未配置时保持零门槛内网模式。
- **防盗链（Hotlink Protection）**：基于现代浏览器 `Sec-Fetch-Site: cross-site` 识别及 Referer 校验机制，严禁外部第三方网站跨站直连纸间作为存储桶或图片代理。
- **视图过渡（View Transition）**：全站单页与局域状态变更时的平滑快照过渡机制，包括页面层级路由推进/后退（`forward` / `backward` Types）、封面到详情大画幅的「共享封面形变」、局域视图过渡（`Element.startViewTransition`）以及弹窗与按钮状态演进，无缝遵循纸间 `--duration-1/2/3` 与无障碍降级。
- **共享封面形变（Shared Cover Morph）**：书架卡片封面（`comic-cover-active`）与本子详情 Hero 封面在路由跳转时的动态连续尺寸与位置插值（神奇移动）。
- **局域视图过渡（Element-Scoped Transition）**：局限于单个组件 DOM 子树内的独立状态过渡（如图片装订就绪、收藏按钮红心状态、并发步进器），不阻塞整页交互与全局重绘。
