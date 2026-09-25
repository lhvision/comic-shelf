import { ref, type Ref } from 'vue'

const BRAND_ICONS = [
  '/brand-icons/icon-1.webp',
  '/brand-icons/icon-2.webp',
  '/brand-icons/icon-3.webp',
  '/brand-icons/icon-4.webp',
  '/brand-icons/icon-5.webp',
  '/brand-icons/icon-6.webp',
  '/brand-icons/icon-7.webp',
]

// Pick a random icon on initial page load / refresh
const initialIndex = Math.floor(Math.random() * BRAND_ICONS.length)
const currentIcon = ref(BRAND_ICONS[initialIndex] || '/brand-icon.webp')

export interface UseBrandIconReturn {
  /** 当前选中的品牌看板头像 URL（响应式引用） */
  brandIcon: Ref<string>
  /** 同步当前选中的品牌头像至浏览器标签页 Favicon */
  syncFavicon: () => void
}

/**
 * 品牌看板头像与标签页 Favicon 联动 Composable。
 *
 * 职责：
 * 1. 在页面加载/刷新时，从预设的高清看板头像池（`/brand-icons/`）中随机挑选一款头像；
 * 2. 供顶栏（AppHeader）与门禁看板（GateView）展示当前会话的看板娘形象；
 * 3. 将选中的头像同步到浏览器当前标签页的 Favicon 中。
 *
 * 【架构防御红线】（错题本 #72 / iOS PWA 稳定性防线）：
 * 严禁使用 `link[rel*='icon']` 等包含匹配选择器！
 * `'apple-touch-icon'` 包含 `'icon'` 子串，通配选择会导致 `<link rel="apple-touch-icon">`
 * 被动态覆写为 WebP 格式的随机头像，引发 iOS Safari 在「添加到主屏幕」时图标频繁漂移、
 * 或因 SpringBoard 不兼容 WebP 格式而退化为网页截图/白屏。
 * 本函数严格仅匹配 `link[rel='icon']:not([sizes])` 与 `link[rel='shortcut icon']`。
 */
export function useBrandIcon(): UseBrandIconReturn {
  function syncFavicon(): void {
    if (typeof document === 'undefined') return
    const links = document.querySelectorAll<HTMLLinkElement>(
      "link[rel='icon']:not([sizes]), link[rel='shortcut icon']",
    )
    links.forEach((link) => {
      link.href = currentIcon.value
      link.type = 'image/webp'
    })
  }

  return {
    brandIcon: currentIcon,
    syncFavicon,
  }
}
