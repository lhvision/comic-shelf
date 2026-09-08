import { useRouter } from 'vue-router'
import type { Router } from 'vue-router'

/**
 * 判断目标路径是否属于指定父路径的下级子路由。
 *
 * @param parentPath 父级页面路径（例如 `/comic/jm/123`）
 * @param targetPath 待检测的目标路径（例如 `/comic/jm/123/chapter/ch1` 或 `/`）
 * @returns 若属于下级子路径则返回 true，否则返回 false
 */
export function isChildRoute(parentPath: string, targetPath: string): boolean {
  if (!parentPath || !targetPath) return false
  const normalizedParent = parentPath.replace(/\/+$/, '')
  const prefix = `${normalizedParent}/`
  return targetPath.startsWith(prefix)
}

/**
 * 判断历史上一页是否精确匹配所属本子详情页（可携带 query 参数或 hash 锚点）。
 *
 * @param albumPath 本子详情页路径（例如 `/comic/jm/123`）
 * @param backState 浏览器历史栈记录中的上一页路径（`window.history.state.back`）
 * @returns 若匹配父详情页路径则返回 true，否则返回 false
 */
export function isParentAlbumRoute(albumPath: string, backState?: string | null): boolean {
  if (!backState) return false
  const normalized = albumPath.replace(/\/+$/, '')
  return (
    backState === normalized ||
    backState.startsWith(`${normalized}?`) ||
    backState.startsWith(`${normalized}#`)
  )
}

/**
 * 章节子路由向上返回父详情页（来源感知回退与替换兜底）。
 *
 * 逻辑契约：
 * 1. 若历史上一页恰好是所属本子详情页（标准前进链路：详情页 -> 章节子路由），
 *    则通过 `router.back()` 优雅出栈，无损还原父详情页离开时的滚动位置与章节展开折叠状态；
 * 2. 否则（如冷启动直达单话、外链接入或历史缺失），使用 `router.replace` 兜底替换，
 *    绝不在历史栈中盲目 `push` 累加多余的父详情条目而诱发下级回弹死循环。
 *
 * @param router Vue Router 实例
 * @param source 来源标识（如 `jm` / `local`）
 * @param sourceId 作品 ID
 */
export function navigateUpFromChapter(router: Router, source: string, sourceId: string): void {
  const albumPath = `/comic/${source}/${sourceId}`
  const backState =
    typeof window !== 'undefined' && window.history.state?.back
      ? String(window.history.state.back)
      : undefined

  if (isParentAlbumRoute(albumPath, backState)) {
    router.back()
  } else {
    void router.replace(albumPath)
  }
}

/**
 * 章节子路由内同级切话（视口切换模型）。
 *
 * 逻辑契约：
 * 将章节详情页视为针对单话的专注展示台，同层切换章节使用 `router.replace`，
 * 保持单话专注视口语义，避免在浏览器历史中堆叠连续切话条目，
 * 确保读者点击「返回本子详情」时始终可单次精准出栈回到父详情页。
 *
 * @param router Vue Router 实例
 * @param source 来源标识
 * @param sourceId 作品 ID
 * @param chapterId 目标章节 ID
 */
export function switchChapter(
  router: Router,
  source: string,
  sourceId: string,
  chapterId: string,
): void {
  void router.replace(`/comic/${source}/${sourceId}/chapter/${encodeURIComponent(chapterId)}`)
}

/**
 * 校验指定路径是否为本子详情页（Rank 2）合法的上级来源路径。
 *
 * 判定守则（层级树状防御）：
 * 1. 绝对禁止回退至任何下级子页面（Rank 3 章节 `/chapter/` 或 Rank 4 阅读器 `/read/`）；
 * 2. 绝对禁止回退至当前本子的任何子路由（`isChildRoute`）；
 * 3. 绝对禁止回退至自建工坊创建表单（`/create`），避免表单重复提交或回显脏状态；
 * 4. 仅当上一页属于合法的上级/平级根视图（如书库 `/`、发现页 `/discovery` 等）时返回 true。
 *
 * @param currentDetailPath 当前本子详情页路径
 * @param backState 历史上一页路径
 */
export function isSafeUpstreamRoute(currentDetailPath: string, backState?: string | null): boolean {
  if (!backState) return false
  if (isChildRoute(currentDetailPath, backState)) return false
  if (backState.includes('/read/')) return false
  if (backState.includes('/chapter/')) return false
  if (
    backState === '/create' ||
    backState.startsWith('/create?') ||
    backState.startsWith('/create#')
  ) {
    return false
  }
  return true
}

/**
 * 本子详情页向上返回（纵深防御拦截与来源保真）。
 *
 * 逻辑契约：
 * 1. 本子详情页（Rank 2）返回按钮的语义为「返回书库/来源页」；
 * 2. 纵深防御拦截（Downward Navigation Guard）：若 `history.state.back` 指向当前漫画的
 *    子路由（如 `/chapter/` 或 `/read/`）、或任何阅读器/章节/工坊表单，绝对禁止 `router.back()`，
 *    必须向上安全回退至书架 `{ name: 'library' }`；
 * 3. 仅当 `back` 指向真正的上级或平级合法来源（如书架 `/`、发现页 `/discovery`、带筛选参路由）时，
 *    才放行 `router.back()`，以无损还原来源页的滚动位置与查询参数。
 *
 * @param router Vue Router 实例
 * @param source 来源标识
 * @param sourceId 作品 ID
 */
export function navigateUpFromDetail(router: Router, source: string, sourceId: string): void {
  const currentDetailPath = `/comic/${source}/${sourceId}`
  const backState =
    typeof window !== 'undefined' && window.history.state?.back
      ? String(window.history.state.back)
      : undefined

  if (isSafeUpstreamRoute(currentDetailPath, backState)) {
    router.back()
  } else {
    void router.replace({ name: 'library' })
  }
}

/**
 * 自建工坊页面向上返回书库（Rank 2 向上返回）。
 *
 * 逻辑契约：
 * 1. 若 history.state.back 属于合法的上层/平级页面（如书架、发现），放行 `router.back()`；
 * 2. 避免在表单页回退至阅读器或章节等深层页面；
 * 3. 否则使用 `router.replace({ name: 'library' })` 兜底回退至书架。
 *
 * @param router Vue Router 实例
 */
export function navigateUpFromCreate(router: Router): void {
  const backState =
    typeof window !== 'undefined' && window.history.state?.back
      ? String(window.history.state.back)
      : undefined

  if (backState && !backState.includes('/read/') && !backState.includes('/chapter/')) {
    router.back()
  } else {
    void router.replace({ name: 'library' })
  }
}

/**
 * 纸间层级树状导航组合式函数。
 * 提供符合领域模型与避坑规范的向上返回与视口切换能力，彻底根绝历史栈死循环。
 */
export function useHierarchicalNavigation() {
  const router = useRouter()

  function goUpFromChapter(source: string, sourceId: string) {
    navigateUpFromChapter(router, source, sourceId)
  }

  function goToChapter(source: string, sourceId: string, chapterId: string) {
    switchChapter(router, source, sourceId, chapterId)
  }

  function goUpFromDetail(source: string, sourceId: string) {
    navigateUpFromDetail(router, source, sourceId)
  }

  function goUpFromCreate() {
    navigateUpFromCreate(router)
  }

  return {
    goUpFromChapter,
    goToChapter,
    goUpFromDetail,
    goUpFromCreate,
  }
}
