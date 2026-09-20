# ADR 0024 — PDF 画卷无损解包与双轨智能分话架构

- **日期**：2026-09-17
- **状态**：Accepted

## 背景

纸间（Paper Room）定位于“本地优先的个人漫画收藏夹与典雅展馆”。在此之前，自建工坊（`CreateComicView`）与服务端路径导入（`import_local_path`）仅支持纯光栅图片（JPG、PNG、WebP、AVIF 等），且服务端导入路径严格锁定为文件夹。

然而在现实网络资源中，大量漫画或个人藏书以单卷单行本或多话合订的 `.pdf` 格式流转（如单行本《与你相恋到生命尽头 第1卷.pdf》）。馆长在收录此类资源时面临明显痛点：

1. **格式格式阻隔**：自建工坊文件选择器（`accept: 'image/*'`）与后端存储层（`IMAGE_EXTS`）完全拒绝 `.pdf` 文件，导入前必须手动通过外部第三方软件解包转图；
2. **多话合订单体 PDF 章节结构丢失**：许多单行本整本（150~200页）压在同一个 PDF 中，缺乏自动化分话机制，导致收录后沦为扁平单卷，失去目录导航与单话断点；
3. **扫描漫画 PDF 缺失电子书签（TOC = 0）**：实机测试表明，绝大多数网上流通的漫画扫描版 PDF 并无内置大纲书签（Bookmarks / Outlines），传统基于 PDF 电子书签切分的方案全面失效；
4. **低效重编码与 CPU 算力浪费**：传统基于 PDF 栅格化工具（如 `pdf2image` / `poppler`）的解包方式以固定 DPI 强制将画页重新栅格化并重编码为 JPG/PNG，百页渲染需耗费数十秒乃至分钟，且造成画质二次劣化与 CPU 剧烈发热。

## 决策

1. **轻量无外部 C 系统依赖的底层引擎选型（PyMuPDF）**：
   - 在 `backend/requirements.txt` 正式引入 `pymupdf`；
   - 无需宿主机安装 poppler 或 ghostscript 动态链接库，保持单容器与宿主机环境极致纯净。

2. **原生图像流无损直出管道（Direct Stream Extraction）**：
   - 优先探测 PDF 页面内嵌的 Image XObject；
   - 漫画扫描 PDF 每页通常内嵌 1 张原始图像，通过底层无损直接导出二进制流（`extract_image`），166 页提取仅需 0.3 秒，0 重编码、0 像素失真；
   - 若遇矢量元素或多图拼版页面，优雅降级为 300 DPI 高保真光栅化渲染，并设置单边最高 3500px 尺寸硬上限，杜绝超大画幅致使内存暴涨。

3. **双轨分话探测器（Dual-Track Chapter Detector）**：
   - **第一轨（电子书签优先）**：若 PDF 包含 `doc.get_toc()` 大纲书签，自动提取章节标题、层级与起始页；
   - **第二轨（本地 OCR 扉页启发式推断）**：若无电子书签，复用本地既有的 `rapidocr-onnxruntime` 嗅探纸质印刷目录与各话扉页标志（如 `第 N 话`、`加笔/附录`、`番外`），自动计算 `start` 与 `page_count`；
   - **性能与防超时熔断（Anti-524 Timeout）**：为杜绝无界 OCR 导致 Cloudflare 524 或 Nginx 超时，引入双重熔断：
     1. 若第一轨 TOC 提取到 $\ge 2$ 个有效章节，立即短路早退（Early Return），完全跳过耗时 OCR；
     2. 若必须执行第二轨 OCR，限制最多抽样扫描 40 个候选页（`MAX_OCR_SCAN_PAGES = 40`），结合步长跳页采样，将耗时严格压制在安全区间；
   - 自动将第 1 话之前的封面、版权页、致辞与纸质目录归纳为独立的首个章节「卷首 / 目录」（`id: c0`），保持正文阅读心流。

4. **自建工坊双模体验与多卷目录合集聚类**：
   - **服务端路径单文件直入**：`import_local_path` 放行直接指向单个 `.pdf` 文件的路径，自动解包并分话收录；
   - **多卷 PDF 目录合集导入（Multi-Volume Directory Ingest）**：当目录下包含多个卷/话的 `.pdf` 文件时（如 `第01卷.pdf` ~ `第07卷.pdf`），按文件名自然序列进行自然数字排序，为每一卷生成独立的 `Chapter`，平滑连续编排全书页码（$1 \dots N$）并生成章节独立封面；
   - **网页端暂存分话确认面板**：提供轻量分析接口，在正式入库前呈现系统推断出的章节草案，供馆长一键采纳或微调。

5. **画卷后续增补与重新装订全链路接入 PDF（Append & Re-binding）**：
   - **追加画卷 / 增补新卷（Append Pages）**：模态弹窗与后端存储层全面放行 `.pdf` 格式。若选择追加到指定章节，自动解压合并；若作为新卷追加，自动识别卷内小节或整卷切片，从 `meta.page_count + 1` 起算全局页码并自愈升阶；临时文件在解压后、`unlink` 前透传至分话探测器，保障追加分话准确无误；
   - **重新装订 / 替换画质（Replace Pages）**：支持单话替换或全卷重装，旧文件原子替换，缩略图按需重排。

6. **六层安全防护与自愈隔离机制（Six-Layer Security Hardening & Lifecycle Isolation）**：
   - **路径与沙箱安全**：`staging_token` 严格受控于 32 位十六进制正则；服务端路径受限于 `COMIC_SHELF_ALLOWED_DIRS` 白名单与软链接穿透保护；
   - **解压炸弹与 OOM 防护**：`MAX_PDF_PAGES = 5000` 刚性上限拦截；Web 上传采用 1GB 上限与 1MB 流式分块写入；探测加密 PDF 友好拦截；光栅化渲染尺寸 3500px 熔断限制；
   - **并发互斥与目录切换（Staging Swap）**：`create_from_staged_pdf` 采用 `_lock_for("local", source_id)` 全局并发锁并实施 slug 碰撞检查（409 Conflict）；文件组装先落盘于 `library/.work/.tmp_create_pages-*`，生成完毕后通过 `_replace_live_with_staging` 把旧目录放进 `.work/.save-*` 再切换，进程内失败回退，启动时按 `.in-progress` 恢复。这不是跨文件事务；崩溃恢复边界见 [部署指南 §11](../../DEPLOYMENT.md#11-本地书库的并发与故障恢复边界)；
   - **全生命周期与冷启动清理**：暴露 `DELETE /api/library/local/staged-pdf/{staging_token}` 物理释放接口；后台常驻 1 小时自动 TTL 垃圾回收；FastAPI 启动 `lifespan` 钩入无条件清扫（`max_age_seconds=0`），宿主机异常重启后残存孤儿暂存零泄漏；所有解包调用收敛于 `try...finally` 清理保底；
   - **权威后端单调索引指针（Monotonic Page Invariant）**：无论客户端传入何种章节 `start`，后端一律以内部全局递增写入计数器 `chap_start_page = global_idx` 强制约束，捍卫核心不变量 #3；
   - **删除断层自愈（Self-Healing Page Re-indexing）**：删除指定章节（`DELETE /api/library/{source}/{source_id}/chapters/{chapter_id}`）时，全书剩余章节与全局单调页号自动无缝压实连续重排（$1 \dots N$），绝不留空洞或错页；整本删除（`DELETE /api/library/{source}/{source_id}`）连带清除本地图片、SQLite 索引与全文检索台词。

## 后果

- **正面收益**：
  - 彻底打通纸间对 PDF 漫画资源的无缝原生支持，极速 0.3 秒无损提取与智能分话；
  - 完美解决扫描版无书签漫画的自动分话痛点；
  - 扁平化多卷目录（`01_第1卷.pdf` ~ `07_第7卷.pdf`）支持一键路径导入整部作品；
  - 画卷追加、重新装订、章节删除全链路自愈，页码严格保持连续。
- **注意事项与最佳实践**：
  - 网盘下载的多级嵌套目录（如 `番外/`、`后续更新/`、`台东立版1-7卷/`）存在字符排序倒置风险（F/H 排在 T 前），建议将 PDF 文件整理至同一漫画目录下按期望阅读顺序命名后导入，或先导入正篇再通过「追加页面」补充番外。
