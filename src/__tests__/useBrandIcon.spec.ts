import { describe, it, expect, beforeEach } from 'vite-plus/test'
import { useBrandIcon } from '@/composables/useBrandIcon'

describe('useBrandIcon composable', () => {
  beforeEach(() => {
    document.head.innerHTML = `
      <link rel="icon" type="image/webp" href="/brand-icon.webp" />
      <link rel="icon" type="image/png" sizes="192x192" href="/pwa-192x192.png" />
      <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
    `
  })

  it('provides brandIcon ref with valid avatar asset path', () => {
    const { brandIcon } = useBrandIcon()
    expect(typeof brandIcon.value).toBe('string')
    expect(brandIcon.value).toMatch(/^\/(brand-icons\/icon-\d+\.webp|brand-icon\.webp)$/)
  })

  it('syncFavicon updates primary tab favicon without touching apple-touch-icon or pwa-192x192', () => {
    const { brandIcon, syncFavicon } = useBrandIcon()

    syncFavicon()

    const primaryFavicon = document.querySelector<HTMLLinkElement>("link[rel='icon']:not([sizes])")
    expect(primaryFavicon?.getAttribute('href')).toBe(brandIcon.value)
    expect(primaryFavicon?.getAttribute('type')).toBe('image/webp')

    // Safeguard: apple-touch-icon MUST NOT be modified
    const appleTouchIcon = document.querySelector<HTMLLinkElement>("link[rel='apple-touch-icon']")
    expect(appleTouchIcon?.getAttribute('href')).toBe('/apple-touch-icon.png')

    // Safeguard: high-resolution PWA png icon MUST NOT be modified
    const pwaIcon = document.querySelector<HTMLLinkElement>("link[sizes='192x192']")
    expect(pwaIcon?.getAttribute('href')).toBe('/pwa-192x192.png')
  })
})
