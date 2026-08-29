# 错题本与避坑红线（Pitfalls Ledger）

> 纸间核心避坑速查表。全仓重构、审查或提交前必须核对，严禁踩踏红线。

---

### 1. 后端：依赖清理与中间件断层

- **禁令**：严禁清理 import 时删除未显式调用的全局依赖；权限检查统一收敛为 `is_curator`，禁止使用别名 `is_admin`。
- **根因**：误删 `auth.py` 的 `is_admin` 导致写操作接口全线报 500（`NameError`）。
- **防线**：提交前必须运行 `pnpm test:py`（AST 语法检查 + 中间件真实鉴权测试）。

### 2. 后端：JM 漫画下架 404 容错

- **禁令**：Provider 必须前置探测 `album_missing` 错误页特征，严禁假设所有 200/302 均为合法漫画 HTML。
- **根因**：下架本子重定向至 `/error/album_missing` 导致正则提取崩溃报 500。
- **防线**：命中下架特征时抛出 `ValueError`，由控制器统一转换为 HTTP 404。

### 3. 后端：多章节全局页码单调递增

- **禁令**：增量追加图片时必须重排全书章节（`rebuilt_pages`），严禁仅在目标章节内部自增。
- **根因**：局部自增导致后续章节 `start` 与全书页码断裂，阅读器跳页。
- **防线**：保证 `ch.start` 与 `page.index` 严格从 1 开始单调递增，必须跑通 `test_incremental_update.py`。

### 4. 后端：服务端路径导入沙箱隔离

- **禁令**：严禁直接读取未经校验的本地路径，禁止扫描根目录或敏感系统路径。
- **根因**：误输入宿主机路径引发任意文件遍历与隐私探测隐患。
- **防线**：所有本地路径必须通过 `_is_path_allowed()`，受限于 `ALLOWED_DIRS` 白名单沙箱。

### 5. 前端：Vue 3 响应式解包与顶层解构

- **禁令**：严禁向模板传递 Composable 包装对象（如直接传 `workshop` 并在模板读 `workshop.title`）。
- **根因**：Vue 3 仅对 `<script setup>` 顶层变量自动解包，嵌套 Ref 不解包显示 `[object Object]`。
- **防线**：Composable 返回的 Ref 必须在 `<script setup>` 顶层显式解构后绑定。

### 6. 前端：View Transitions 边界与阅读器防抢占

- **禁令**：严禁在阅读器内部翻页/切话中触发全屏路由过渡；所有 `startViewTransition` 必须绑定 catch 忽略 AbortError。
- **根因**：全屏快照排他，快速翻页被浏览器 Abort 抢占导致白屏崩溃。
- **防线**：全屏过渡仅限跨页面路由跳转（书架 ⇄ 详情 ⇄ 章节 ⇄ 阅读器）；阅读器内翻页零全屏过渡。

### 7. 前端：硬件图层裁剪（contain: paint 陷阱）

- **禁令**：带有 Hover 浮动、叠牌旋转、柔和阴影的卡片，绝对禁止使用 `contain: paint` 或 `content-visibility: auto`。
- **根因**：`contain: paint` 强制将超出容器边界的阴影和上浮边缘生硬裁切，产生黑边。
- **防线**：样式采用 `contain: layout style`；海量列表通过 48 图预算与 `useIntersectionObserver` 增量呈现。

### 8. 前端：useMemoize 失败缓存残留与参数签名

- **禁令**：所有异步 memoize 函数在 catch 中必须调用 `.delete(key)` 清理失败缓存。
- **根因**：Promise 被 Abort 后默认保留 rejected 缓存，用户重试永久报 `AbortError`。
- **防线**：包装函数显式声明完整参数签名（`(source, id, options?: RequestOptions) => ...`）。

### 9. 前端：书架切页回源骨架屏闪烁（SWR 保持）

- **禁令**：内存已有列表数据时二次切页严禁无条件重置 `loading = true`。
- **根因**：切换回书架时卡片销毁并闪现骨架屏，破坏阅读沉浸感。
- **防线**：SWR 机制：内存有数据时静默回源更新；仅在首次无数据或主动下拉刷新时展示骨架屏。

### 10. 前端：UI 变体与 Composable 类型契约一致性

- **禁令**：严禁在组件调用时使用未在 Prop 与 Composable TS 联合类型中定义的变体别名（如废弃的 `variant="solid"`）。
- **根因**：Props 与 Store/Composable 状态类型脱节导致静默样式丢失。
- **防线**：组件变体与 Composable 联合类型保持 1:1 对齐，`vp check` 零类型报错。

### 11. 前端：零伪图标字符与单源字典收敛

- **禁令**：严禁使用 Unicode 文本伪字符（`✕`/`✓`/`×`/`⋯`/`←`）或在业务代码手写散落 `<svg>`。
- **根因**：跨平台字体基线撕裂、屏幕阅读器读错（如 `'×'` 读成乘号）、多处 `v-if/v-else-if` 破坏开闭原则。
- **防线**：全站统一使用 `src/components/icons/`（`BaseIcon` 底座 + 原子组件 + `AppIcon` 分发器）。

### 12. 全仓：严禁硬编码宿主机本地绝对路径

- **禁令**：严禁在仓库任何代码、文档或配置中写入宿主机绝对路径（如 `file:///home/...`、`C:\Users\...`）。
- **根因**：他人 Clone 仓库或部署后链接失效、隐私泄露，破坏开源与团队协作一致性。
- **防线**：跨文件引用必须使用仓库相对路径（如 `[DEPLOYMENT.md](DEPLOYMENT.md)`、`src/pwa.ts`）；AI 助手向磁盘写文件前必须剔除对话中的 `file://` 协议。

---

## 🚦 交付门禁（三步必跑）

1. `vp check`：前端 0 error、0 warning、格式规范；
2. `pnpm test:py`：后端 0 syntax/import error，中间件全链路测试通过；
3. **定向单测**：仅运行改动对应的单测文件（严禁无差别全量阻塞）。
