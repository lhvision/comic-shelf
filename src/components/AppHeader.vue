<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import type { ProviderInfo } from '@/types'

interface NavItem {
  to: string
  label: string
  index?: string
  sourceKey?: string
}

const route = useRoute()
const router = useRouter()
const providers = ref<ProviderInfo[]>([])

const navItems = computed<NavItem[]>(() => [
  { to: '/', label: '全部' },
  ...providers.value.map((provider, index) => ({
    to: `/?source=${provider.key}`,
    label: provider.short_label || provider.label,
    index: String(index + 1).padStart(2, '0'),
    sourceKey: provider.key,
  })),
])

function isActive(item: NavItem) {
  if (!item.sourceKey) return route.query.source === undefined
  return route.query.source === item.sourceKey
}

function goLibrary() {
  router.push('/')
}

onMounted(async () => {
  try {
    providers.value = await api.providers()
  } catch {
    // Fall back to the embedded default so navigation still works offline.
    providers.value = [
      {
        key: 'jm',
        label: '禁漫天堂 (JMComic)',
        short_label: '禁漫',
        id_pattern: '',
        example: '',
        description: '',
      },
    ]
  }
})
</script>

<template>
  <header class="site-header">
    <button class="brand" type="button" @click="goLibrary" aria-label="回到全部收藏">
      <img class="brand-mark" src="/brand-icon.png" alt="" aria-hidden="true" />
      <span>
        <strong>纸间</strong>
        <small>Paper Room</small>
      </span>
    </button>

    <nav class="site-nav" aria-label="来源导航">
      <RouterLink
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        :class="{ active: isActive(item) }"
      >
        <span v-if="item.index" class="nav-index">{{ item.index }}</span>
        {{ item.label }}
      </RouterLink>
    </nav>

    <p class="header-note">本地优先 · 缓存后不再访问远端</p>
  </header>
</template>

<style scoped>
.site-header {
  position: sticky;
  top: 0;
  z-index: 40;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: var(--space-5);
  min-height: var(--header-h);
  padding: 0 var(--page-pad);
  border-bottom: 1px solid var(--line);
  background: color-mix(in oklab, var(--paper-0) 82%, transparent);
  backdrop-filter: blur(14px);
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  padding: 0;
  background: transparent;
  color: var(--ink-0);
  text-align: left;
}

.brand-mark {
  width: 2.25rem;
  height: 2.25rem;
  object-fit: contain;
  border-radius: 0.5rem;
  background: color-mix(in oklab, var(--ink-0) 6%, transparent);
  transition: rotate var(--duration-2) var(--ease-spring);
}

.brand:hover .brand-mark {
  rotate: -6deg;
}

.brand strong {
  display: block;
  font-family: var(--font-display);
  font-size: var(--text-md);
  line-height: 1.1;
  letter-spacing: 0.08em;
}

.brand small {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  letter-spacing: 0.14em;
  color: var(--ink-2);
  text-transform: uppercase;
}

.site-nav {
  display: flex;
  gap: var(--space-4);
  align-self: stretch;
}

.site-nav a {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--ink-1);
  transition: color var(--duration-1) var(--ease-out);
}

.site-nav a::after {
  content: '';
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  height: 2px;
  background: var(--accent);
  transform: scaleX(0);
  transform-origin: right;
  transition: transform var(--duration-2) var(--ease-out);
}

.site-nav a:hover,
.site-nav a.active {
  color: var(--ink-0);
}

.site-nav a.active::after {
  transform: scaleX(1);
  transform-origin: left;
}

.nav-index {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-2);
}

.header-note {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
}

@media (max-width: 640px) {
  .site-header {
    grid-template-columns: auto 1fr;
  }

  .header-note {
    display: none;
  }
}
</style>
