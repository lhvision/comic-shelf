export interface ResolvedComic {
  source: string
  id: string
  name: string
}

export declare function isSafeUrl(raw?: string | null): boolean
export declare function resolveComicInfo(rawUrl?: string | null): ResolvedComic | null
export declare function buildUrlPatterns(domains: string[]): string[]
export interface DetectComicOptions {
  domains?: string[]
  serverUrl?: string
}

export declare function detectComicFromTab(
  tab?: { id?: number; url?: string; pendingUrl?: string } | null,
  options?: DetectComicOptions,
): Promise<{ comic?: ResolvedComic; error?: string } | null>

export declare function getConfig(): Promise<{
  serverUrl: string
  token: string
  enableNotifications: boolean
}>
export declare function showNotification(
  title: string,
  message: string,
  targetUrl?: string | null,
): Promise<void>
export declare function importComic(
  comic: ResolvedComic,
  options?: { openTab?: boolean; silent?: boolean },
): Promise<{ ok: boolean; detailUrl?: string; fromCache?: boolean }>
