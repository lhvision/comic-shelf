import type { Ref } from 'vue'
import type { useWebMCP } from '@vueuse/core'
import type { IconName } from '@/components/icons'

export interface PageRecord {
  index: number
  file: string
  ext: string
  cached: boolean
  /** Chapter id this page belongs to; empty for single-chapter albums. */
  chapter?: string
}

export interface Chapter {
  id: string
  /** 1-based chapter ordinal within the album */
  index: number
  title: string
  page_count: number
  /** 1-based global page index at which this chapter begins */
  start: number
}

export interface ComicMeta {
  source: string
  source_id: string
  display_id: string
  title: string
  authors: string[]
  works: string[]
  actors: string[]
  tags: string[]
  description: string
  uploader: string | null
  page_count: number
  published_at: string
  updated_at: string
  views: string
  likes: string
  comment_count: number
  favorite: boolean
  hidden_from_guest?: boolean
  cover_count: number
  cover_indices?: number[]
  custom_pages?: boolean
  source_url: string
  pages: PageRecord[]
  imported_at: string
  last_checked_at: string
  raw: Record<string, unknown>
  /** Chapter/section list for multi-chapter albums; empty for single-chapter. */
  chapters?: Chapter[]
  /** 自动追更巡检周期天数（0 表示关闭，默认 15） */
  auto_update_interval_days?: number
  /** 上次由后台自动追更巡检的时间戳 */
  last_auto_checked_at?: string
}

export interface LibrarySummary {
  source: string
  source_id: string
  display_id: string
  title: string
  authors: string[]
  works: string[]
  actors: string[]
  tags: string[]
  favorite: boolean
  hidden_from_guest?: boolean
  page_count: number
  views: string
  likes: string
  uploaded_at: string
  published_at: string
  updated_at: string
  imported_at: string
  cover_paths: string[]
  cached_pages: number
  cover_count: number
  /** T11：章节标题，书架搜索可命中「第 5 话」等 */
  chapter_titles?: string[]
  /** 用户个人阅读进度：上次翻到的页码（0 表示未读） */
  last_page?: number
}

export type ReadingStatus = 'all' | 'reading' | 'completed' | 'unread'
export type SortKey = 'recent' | 'title' | 'pages' | 'cached'

export interface LibraryQueryParams {
  page?: number
  page_size?: number
  offset?: number
  ids?: string
  status?: ReadingStatus
  favorite?: boolean
  source?: string
  q?: string
  search?: string
  tag?: string
  tags?: string
  sort?: string
}

export interface LibraryPageResponse {
  items: LibrarySummary[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

export interface LibraryStats {
  total_books: number
  total_pages: number
  cached_pages: number
}

export interface LibraryFacetsResponse {
  stats: LibraryStats
  top_tags: Array<[string, number]>
}

export interface ComicDetail {
  meta: ComicMeta
  cached_pages: number
  cache_complete: boolean
  cover_paths: string[]
}

/** 支持的漫画图源 Provider 标识符 */
export type ComicSource = 'jm' | 'picacg' | 'local'

export interface ImportRequest {
  id: string
  source: ComicSource | (string & {})
  prefetch_covers?: number
  prefetch_all?: boolean
  refresh?: boolean
}

export interface ImportResult {
  meta: ComicMeta
  from_cache: boolean
  prefetched: number
  warnings: string[]
  /** True when page/cover caching is still running in the background. */
  background?: boolean
}

export interface CacheJob {
  source: string
  source_id: string
  chapter_id?: string | null
  running: boolean
  done: boolean
  total: number
  prefetched: number
  warnings: string[]
  error: string
  started_at: number | null
  finished_at: number | null
}

export interface CacheProgress {
  cached: number
  total: number
  complete: boolean
}

export interface DownloadConcurrency {
  limit: number
  min: number
  max: number
  env_controlled: boolean
}

export interface ProviderInfo {
  key: string
  label: string
  short_label: string
  id_pattern: string
  example: string
  description: string
}

export interface ImageSearchResultItem {
  source: string
  source_id: string
  page_index: number
  is_cover: boolean
  score: number
}

export interface ImageSearchStatus {
  available: boolean
  url?: string
}

export interface AuthStatus {
  auth_required: boolean
  authenticated: boolean
  can_write: boolean
  role: 'admin' | 'guest' | 'unauthorized'
  username?: string
  user_id?: string
  is_claimed?: boolean
  requires_pin?: boolean
  requires_claim?: boolean
}

export interface LoginResult {
  ok: boolean
  token: string
  role?: 'admin' | 'guest'
  username?: string
  user_id?: string
  device_token?: string
  is_claimed?: boolean
  requires_pin?: boolean
  requires_claim?: boolean
}

export interface MetadataUpdatePayload {
  title?: string
  authors?: string[]
  works?: string[]
  actors?: string[]
  tags?: string[]
  description?: string
  uploader?: string
  cover_indices?: number[]
  hidden_from_guest?: boolean
  auto_update_interval_days?: number
}

export interface LocalChapterInput {
  id: string
  title: string
  start?: number
  page_count?: number
}

export interface PdfChapterPreview {
  id: string
  index: number
  title: string
  start: number
  page_count: number
}

export interface PdfInspectResponse {
  staging_token: string
  title: string
  authors: string[]
  total_pages: number
  chapters: PdfChapterPreview[]
  detection_track: 'toc' | 'ocr' | 'fallback'
}

export interface CreateFromStagedPdfPayload {
  staging_token: string
  id?: string
  title: string
  authors?: string[]
  works?: string[]
  actors?: string[]
  tags?: string[]
  description?: string
  uploader?: string
  chapters: PdfChapterPreview[]
  cover_indices?: number[]
  hidden_from_guest?: boolean
}

export interface LocalComicCreatePayload {
  id?: string
  title: string
  authors?: string[]
  works?: string[]
  actors?: string[]
  tags?: string[]
  description?: string
  uploader?: string
  chapters?: LocalChapterInput[]
  cover_indices?: number[]
  hidden_from_guest?: boolean
}

export interface LocalPathImportPayload {
  path: string
  id?: string
  title?: string
  authors?: string[]
  works?: string[]
  actors?: string[]
  tags?: string[]
  description?: string
  uploader?: string
  cover_indices?: number[]
  hidden_from_guest?: boolean
}

export interface LocalAppendPayload {
  target_chapter?: string
  new_chapter_title?: string
  server_path?: string
}

export type ComicAppendPayload = LocalAppendPayload

export type DiscoveryTimeframe = 'week' | 'month' | 'day'

export interface DiscoveryItem {
  id: string
  source_id: string
  source: string
  title: string
  author: string
  category: string
  url?: string
  cover_url?: string
  updated_at?: string
  in_library: boolean
}

export interface DiscoveryFeed {
  source?: string
  timeframe: DiscoveryTimeframe
  updated_at: string
  items: DiscoveryItem[]
}

export interface DropdownOption<K = string | number> {
  key: K
  label: string
  icon?: IconName | (string & {})
  hint?: string
  sub?: string
  disabled?: boolean
  danger?: boolean
  separator?: boolean
  checked?: boolean
}

export type GuestPassActivationStatus = 'pending' | 'active' | 'full' | 'disabled' | 'expired'

export interface GuestDevice {
  id: number
  pass_id: number
  device_token: string
  device_name: string
  user_agent: string
  last_ip: string
  created_at: number
  last_active_at: number
}

export interface GuestPass {
  id: number
  username: string
  token: string
  expires_at: number | null
  is_active: boolean
  is_expired: boolean
  is_claimed?: boolean
  has_pin?: boolean
  max_devices: number
  device_count: number
  devices: GuestDevice[]
  activation_status: GuestPassActivationStatus
  is_cooling_locked?: boolean
  is_rate_limited?: boolean
  created_at: number
  updated_at: number
}

export interface GuestPrivacySettings {
  guest_hide_new_comics: boolean
}

export interface CreateGuestPassPayload {
  username: string
  expires_days?: number | null
  custom_token?: string | null
  pin?: string | null
  max_devices?: number
}

export interface UpdateGuestPassPayload {
  username?: string
  is_active?: boolean
  extend_days?: number
  reset_token?: boolean
  reset_pin?: boolean
  custom_pin?: string | null
  expires_days?: number | null
  max_devices?: number
}

export interface ClaimGuestPassPayload {
  token: string
  pin: string
  username?: string
}

export interface ReadingProgressInfo {
  ok: boolean
  last_page: number
  total_pages: number
  updated_at: number
}

/**
 * 台词检索的单条结果：一条是一页，不是一个气泡。
 * `text` / `box` 属于该页相关度最高的代表气泡，同页其余命中气泡只给坐标（`other_boxes`）。
 */
export interface DialogueSearchItem {
  source: string
  source_id: string
  display_id?: string
  title: string
  page_index: number
  bubble_id?: number | string
  /** 该页命中的气泡数，没有坐标的也计入；是候选池内计数，高频页可能少报 */
  bubble_count?: number | null
  text: string
  snippet?: string
  box: number[]
  /** 同页其余命中气泡的归一化坐标，不含代表气泡与没有坐标的命中；条数有封顶 */
  other_boxes: number[][]
  lang?: string
  cover?: string
  authors?: string[]
  /** 代表气泡的台词相关度，0..1，越大越相关；只在本次结果内比高低，不能跨查询比较 */
  rank_score: number
}

export interface DialogueSearchResponse {
  /** 页级结果列表，条数即命中页数 */
  results: DialogueSearchItem[]
  /** 命中页数，恒等于 results 长度（后端未做全库 COUNT，也不是气泡总数） */
  total: number
}

export interface DirectPassPayload {
  source: string
  source_id: string
  page_index?: number
  ttl_seconds?: number
}

export interface DirectPassResponse {
  token: string
  source: string
  source_id: string
  page_index: number
  expires_at: number
  expires_in: number
  direct_url: string
}

export type WebMCPTool = ReturnType<typeof useWebMCP>

/**
 * 统一 WebMCP 组合式函数返回类型泛型构造器。
 * 基础包含 `isSupported: Ref<boolean>`，并通过映射类型将传入的工具 Key 联合自动映射为可选的 `WebMCPTool`。
 */
export type WebMCPComposableReturn<K extends string = never> = {
  isSupported: Ref<boolean>
} & {
  [P in K]?: WebMCPTool
}
