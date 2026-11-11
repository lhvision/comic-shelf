export interface BuiltinProvider {
  source: string
  name: string
  badge: string
  domains: string[]
  keywords?: string[]
}

export type CustomDomainsMap = Record<string, string[]>

export interface DomainOwner {
  source: string
  name: string
  badge: string
  isBuiltin: boolean
  conflictType: 'exact' | 'subdomain' | 'parent'
  conflictDomain: string
}

export interface MatchedProvider {
  source: string
  name: string
  badge: string
  matchedDomain: string
}

export declare const BUILTIN_PROVIDERS: BuiltinProvider[]
export declare const DEFAULT_DOMAINS: string[]
export declare function createEmptyCustomDomainsMap(): CustomDomainsMap
export declare function sanitizeDomain(raw?: string | null): string
export declare function isValidDomain(raw?: string | null): boolean
export declare function guessProviderFromDomain(raw?: string | null): string | null
export declare function findDomainOwner(
  raw?: string | null,
  customMap?: CustomDomainsMap,
): DomainOwner | null
export declare function migrateCustomDomains(stored: unknown): CustomDomainsMap
export declare function matchDomainToProvider(
  hostname?: string | null,
  customMap?: CustomDomainsMap,
): MatchedProvider | null
export declare function getAllConfiguredDomains(customMap?: CustomDomainsMap): string[]
