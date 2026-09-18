/**
 * @file client.ts
 * @description 纸间全站统一 API 门面与契约中枢（Unified API Facade & Contract Central）。
 *
 * 架构重构与设计说明：
 * 1. 【领域模块化划分】：按业务职责拆解为 8 大单一职责领域模块（Auth, Library, Cache, Workshop, Discovery, Search, Reader, Curator）；
 * 2. 【分层解耦与可测试性】：底层 HTTP 传输拦截、Token 广播与 Baseline 2024 复合信号下沉至 `core/http.ts`，URL 工具下沉至 `core/urls.ts`；
 * 3. 【100% 向后兼容与零破坏性变更】：统一聚合导出 `api` 门面对象及所有历史具名函数与工具类型，全仓无缝迁移；
 * 4. 【完备契约注释】：所有领域函数配备完整 TSDoc，严格遵循无未使用变量与强类型检查。
 */

import * as auth from './modules/auth'
import * as library from './modules/library'
import * as cache from './modules/cache'
import * as workshop from './modules/workshop'
import * as discovery from './modules/discovery'
import * as search from './modules/search'
import * as reader from './modules/reader'
import * as curator from './modules/curator'

// Re-export core transport and helpers
export * from './core/http'
export * from './core/urls'

// Re-export domain modules
export * from './modules/auth'
export * from './modules/library'
export * from './modules/cache'
export * from './modules/workshop'
export * from './modules/discovery'
export * from './modules/search'
export * from './modules/reader'
export * from './modules/curator'

/**
 * 纸间统一 API 客户端对象（聚合全站所有领域功能）
 */
export const api = {
  // === 1. 认证与权限 (Auth) ===
  /** 探测后端服务健康状态与鉴权需求 */
  health: auth.health,
  /** 获取当前登录用户的权限与角色状态 */
  authStatus: auth.authStatus,
  /** 馆长密码或访客凭证登录 */
  login: auth.login,
  /** 认领并激活访客通行证 */
  claimPass: auth.claimPass,
  /** 签发单本专属沙箱直达通行证（Direct Pass） */
  createDirectPass: auth.createDirectPass,
  /** 注销当前登录会话 */
  logout: auth.logout,

  // === 2. 书架与作品 (Library) ===
  /** 获取支持的漫画图源 Provider 清单（内存缓存） */
  providers: library.providers,
  /** 多维度分页检索与筛选书架中的漫画作品 */
  library: library.library,
  /** 获取书架的聚合统计数据（Facets） */
  libraryFacets: library.libraryFacets,
  /** 获取作品详情结构化数据（支持 bypassCache） */
  detail: library.detail,
  /** 向书架导入远端作品 */
  importComic: library.importComic,
  /** 从书架中永久删除指定作品 */
  deleteComic: library.deleteComic,
  /** 切换指定作品的收藏状态 */
  setFavorite: library.setFavorite,
  /** 更新作品自定义元数据 */
  updateMetadata: library.updateMetadata,

  // === 3. 离线缓存与并发管理 (Cache) ===
  /** 触发指定作品的全本后台离线缓存下载 */
  cacheAll: cache.cacheAll,
  /** 查询指定作品的全本离线缓存进度 */
  cacheProgress: cache.cacheProgress,
  /** 查询指定单章节的离线缓存进度 */
  chapterCacheProgress: cache.chapterCacheProgress,
  /** 触发指定单章节的后台离线下载与解密 */
  cacheChapter: cache.cacheChapter,
  /** 查询指定作品当前关联的下载任务详情 */
  cacheJob: cache.cacheJob,
  /** 查询全站所有正在运行或排队的后台下载任务列表 */
  cacheJobs: cache.cacheJobs,
  /** 获取当前的全局图片下载并发限制 */
  downloadConcurrency: cache.downloadConcurrency,
  /** 调整全局图片下载并发限制 */
  setDownloadConcurrency: cache.setDownloadConcurrency,
  /** 获取访客隐私可见性策略 */
  guestPrivacy: cache.guestPrivacy,
  /** 设置访客隐私可见性策略 */
  setGuestPrivacy: cache.setGuestPrivacy,

  // === 4. 本地工坊与章节编辑 (Workshop) ===
  /** 在本地自建库中创建全新漫画作品 */
  createLocalComic: workshop.createLocalComic,
  /** 从服务器本地路径导入漫画文件夹或归档 */
  importLocalPath: workshop.importLocalPath,
  /** 上传并嗅探 PDF 文件结构 */
  inspectPdf: workshop.inspectPdf,
  /** 删除服务器暂存的 PDF 临时文件 */
  deleteStagedPdf: workshop.deleteStagedPdf,
  /** 基于已暂存的 PDF 执行切分渲染并入库为本地画集 */
  createFromStagedPdf: workshop.createFromStagedPdf,
  /** 向作品或指定章节上传并插入多张画页 */
  uploadPages: workshop.uploadPages,
  /** 整话/整本覆盖替换画页 */
  replaceComicPages: workshop.replaceComicPages,
  /** 从服务器本地路径重新加载并替换画页 */
  replaceComicPagesFromPath: workshop.replaceComicPagesFromPath,
  /** 追加画页或合并其他画集内容 */
  appendPages: workshop.appendPages,
  /** 重命名或修改指定章节标题 */
  updateChapter: workshop.updateChapter,
  /** 删除指定作品的某一章节 */
  deleteChapter: workshop.deleteChapter,

  // === 5. 发现榜单 (Discovery) ===
  /** 获取官方发现排行榜数据（日榜、周榜、月榜） */
  discoveryRanking: discovery.discoveryRanking,

  // === 6. 视觉搜图与台词全文检索 (Search) ===
  /** 查询以图搜图服务引擎的就绪状态与特征索引总量 */
  imageSearchStatus: search.imageSearchStatus,
  /** 上传图片文件检索相似漫画画页 */
  imageSearch: search.imageSearch,
  /** 基于 SQLite FTS5 对全库漫画台词进行全文检索 */
  searchDialogue: search.searchDialogue,

  // === 7. 阅读进度 (Reader) ===
  /** 获取指定作品的最新阅读进度 */
  getReadingProgress: reader.getReadingProgress,
  /** 提交并更新指定作品的阅读进度 */
  saveReadingProgress: reader.saveReadingProgress,

  // === 8. 馆长通行证运维 (Curator) ===
  /** 获取全站所有访客通行证列表 */
  getCuratorPasses: curator.getCuratorPasses,
  /** 签发全新的访客通行证 */
  createCuratorPass: curator.createCuratorPass,
  /** 更新或调整已有访客通行证的信息 */
  updateCuratorPass: curator.updateCuratorPass,
  /** 撤销并永久删除指定的访客通行证 */
  deleteCuratorPass: curator.deleteCuratorPass,
  /** 解绑指定通行证下绑定的特定访客设备 */
  deleteCuratorPassDevice: curator.deleteCuratorPassDevice,
}
