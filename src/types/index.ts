export interface PageRecord {
  index: number
  file: string
  ext: string
  cached: boolean
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
