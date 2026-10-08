export interface BuiltinProvider {
  source: string
  name: string
  badge: string
  domains: string[]
}

export declare const BUILTIN_PROVIDERS: BuiltinProvider[]
export declare const DEFAULT_DOMAINS: string[]
export declare function sanitizeDomain(raw?: string | null): string
export declare function isValidDomain(raw?: string | null): boolean
