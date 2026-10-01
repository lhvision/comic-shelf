# ADR 0032 — 数据库层领域子包解耦与向后兼容契约

- **日期**：2026-10-01
- **状态**：Accepted
- **关联**：承接 ADR 0006 (访客通行证与 SQLite 隔离)、ADR 0015 (万级书库分页与 SQLite 影子索引)、ADR 0017 (台词全文检索与气泡图层)、ADR 0028 (台词语义检索独立出口)；更新 `docs/agents/architecture.md`

## 背景与问题

纸间自早期单一 SQLite 辅助存储演进至今，逐步承载了书架影子索引、访客通行证鉴权、设备槽位 LRU 轮转、单本沙箱临时直达、OCR 过滤熔断、FTS5 全文检索引擎、以及向量语义检索。

随着能力扩充，`backend/app/db.py` 膨胀为单一文件 **3,168 行、78 个顶层函数** 的巨型上帝模块（God Module）：

1. **物理存储与职责混乱**：`comic_shelf.db`（主库）与 `comic_dialogues.db`（台词专库）两套完全物理隔离的 SQLite 数据库在同一个文件内交叉操作，Schema 定义、迁移与 CRUD 混杂；
2. **高认知负荷**：台词领域包含大量的 OCR 边界熔断、广告过滤、BM25/LIKE 评分与分镜坐标算法（占 1,350+ 行，超 42%），与安全鉴权、书架影子索引放在同一个文件内，极大增加了日常审阅和维护心智负担；
3. **调用面极宽**：全工程有 12 个核心领域文件及 12 个单测强依赖 `app.db`，且测试中广泛采用 `mock.patch("app.db.xxx")`。

## 方案论证与权衡（Grilling Analysis）

围绕拆分边界、依赖关系与向后兼容性，进行了严格的方案推演与决策收敛：

### 1. 拆分维度：按领域与 Router 对齐（Domain Partitioning）

- **否决方案（纯二分法：按主库/台词库切分）**：
  主库依然包含 1800+ 行，鉴权通行证与藏书影子索引仍混杂在一起，没有彻底解决内聚性问题。
- **采纳方案（领域四分法 + 基础连接 + 迁移管理）**：
  拆分子模块与 FastAPI 上层路由（`routers/`）严格呼应：
  - `connection.py`：数据库路径、`get_db` / `get_dialogue_db` 连接池上下文、WAL PRAGMA 设置、`_escape_like` 通配符转义；
  - `schema.py`：集中式 DDL 建表与历史增量字段（`title_norm`, `cached_pages`, `raw` 等）迁移生命周期管理；
  - `passes.py`：访客通行证（Guest Pass）、设备槽位（Device Slot）、PIN 密码学处理、单本沙箱直达（Direct Pass）；
  - `user_state.py`：用户收藏（Favorites）与阅读进度（Progress）；
  - `index.py`：藏书影子索引（Comic Index）、分面聚合（Facets）缓存与快照、多维复杂筛选、定时巡检更新；
  - `dialogues.py`：台词 FTS5 倒排索引、OCR 文本清洗去噪、语义向量嵌入、分镜气泡坐标几何计算、故事上下文切片。

### 2. 对外暴露方式：Python 包与零破坏兼容（Zero-breaking Backward Compatibility）

- **核心目标**：绝不破坏全库现有的任何一处 `from app.db import ...`、`import app.db as db_mod`，以及全部单测中的 `mock.patch("app.db.upsert_comic_index")` 等打桩点。
- **实现手段**：
  - 将 `backend/app/db.py` 转化为包目录 `backend/app/db/`；
  - 在 `__init__.py` 中全量 re-export 所有原有 78 个函数与核心业务常量（如 `MAX_PAGE_BOXES`, `DIALOGUE_KIND`, `PARATEXT_KIND`, `STORY_CONTEXT_MAX_LINES` 等）；
  - 对动态变化的全局路径（`_DB_PATH`、`_DIALOGUE_DB_PATH`），通过 `__init__.py` 的 module-level `__getattr__` 挂载实时 getter，确保单测在动态调用 `set_db_path()` 切换临时数据库时，所有子模块与外部引用均能感知实时路径。

### 3. 依赖方向与防循环引用（Circular Dependency Safeguards）

- `connection.py` 作为纯底层基础设施，不依赖任何业务模块；
- `set_db_path()` 在底层完成连接路径变更后，通过局部安全导入触发 `index.invalidate_facets_cache(force=True)`；
- `schema.py` 和 `index.py` 单向依赖 `dialogues.py`（进行索引回填与级联清除），`dialogues.py` 则仅通过 `get_db()` 跨库查询影子索引元数据，杜绝了模块间循环引用。

## 架构成效

1. **单文件规模显著收敛**：从 3,168 行单文件转为 6 个高内聚子文件（`connection`: ~90行, `schema`: ~320行, `passes`: ~480行, `user_state`: ~120行, `index`: ~880行, `dialogues`: ~1250行）；
2. **零破坏升级**：后端 16 个单元测试文件全量通过（0 failures），业务路由代码 0 行修改；
3. **架构防退化约束**：严禁后续维护者再次引入上帝文件；凡属于新业务领域的数据库操作，必须按照功能内聚原则就近入驻对应领域子模块。
