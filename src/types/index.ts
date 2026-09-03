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
}

export interface ComicDetail {
  meta: ComicMeta
  cached_pages: number
  cache_complete: boolean
  cover_paths: string[]
}

export interface ImportRequest {
  id: string
  source?: string
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
}

export interface LocalChapterInput {
  id: string
  title: string
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
