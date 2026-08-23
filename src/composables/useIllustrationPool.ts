/**
 * 插画资产池 —— 自动发现与随机轮换池。
 * 通过 Vite import.meta.glob 自动感知 public/loading-*.webp 资产，
 * 新增插画直接放入 public 目录即可自动扩容，无需修改任何代码。
 */

const globMap = import.meta.glob('/public/loading-*.{webp,png,jpg,jpeg}', {
  eager: true,
})

const discovered = Object.keys(globMap)
  .map((path) => {
    const match = path.match(/(loading-[^/]+\.(?:webp|png|jpg|jpeg))$/i)
    return match ? `/${match[1]}` : ''
  })
  .filter(Boolean)
  .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))

export const DEFAULT_ILLUSTRATIONS: readonly string[] =
  discovered.length > 0
    ? discovered
    : [
        '/loading-1.webp',
        '/loading-2.webp',
        '/loading-3.webp',
        '/loading-4.webp',
        '/loading-5.webp',
        '/loading-tiya.webp',
      ]

export function useIllustrationPool() {
  const illustrations = DEFAULT_ILLUSTRATIONS
  const count = illustrations.length

  function getRandomIllustration(): string {
    if (count === 0) return '/loading-1.webp'
    const index = Math.floor(Math.random() * count)
    return illustrations[index] ?? '/loading-1.webp'
  }

  function getIllustration(variantOrIndex?: number | string): string {
    if (typeof variantOrIndex === 'string') {
      if (variantOrIndex.startsWith('/')) return variantOrIndex
      if (variantOrIndex === 'tiya') return '/loading-tiya.webp'
      return `/${variantOrIndex}`
    }
    if (typeof variantOrIndex === 'number' && Number.isFinite(variantOrIndex)) {
      const idx = variantOrIndex > 0 ? (variantOrIndex - 1) % count : 0
      return illustrations[idx] ?? illustrations[0] ?? '/loading-1.webp'
    }
    return getRandomIllustration()
  }

  return {
    illustrations,
    count,
    getRandomIllustration,
    getIllustration,
  }
}
