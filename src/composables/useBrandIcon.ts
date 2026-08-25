import { ref } from 'vue'

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

export function useBrandIcon() {
  function syncFavicon() {
    if (typeof document === 'undefined') return
    const links = document.querySelectorAll<HTMLLinkElement>("link[rel*='icon']")
    links.forEach((link) => {
      link.href = currentIcon.value
    })
  }

  return {
    brandIcon: currentIcon,
    syncFavicon,
  }
}
