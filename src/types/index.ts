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
  cover_count: number
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
  has_guest_secret?: boolean
}

export interface LoginResult {
  ok: boolean
  token: string
  role?: 'admin' | 'guest'
}
