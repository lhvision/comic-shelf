<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, onAuthSuccess } from '@/api/client'
import { useAuth } from '@/composables/useAuth'
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
const { authRequired, authenticated, logout, openModal } = useAuth()

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

async function fetchProviders() {
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
}

onMounted(fetchProviders)
onAuthSuccess(fetchProviders)
</script>

<template>
  <header class="site-header">
    <button class="brand" type="button" @click="goLibrary" aria-label="回到全部收藏">
      <img class="brand-mark" src="/brand-icon.webp" alt="" aria-hidden="true" />
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

    <div class="header-right">
      <p class="header-note">本地优先 · 缓存后不再访问远端</p>
      <button
        v-if="authRequired"
        type="button"
        class="auth-badge-btn"
        :class="{ locked: !authenticated }"
        :title="authenticated ? '口令已验证（点击退出锁定）' : '点击输入通行口令'"
        @click="authenticated ? logout() : openModal()"
      >
        <svg
          viewBox="0 0 24 24"
          width="13"
          height="13"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <template v-if="authenticated">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 9.9-1" />
          </template>
          <template v-else>
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </template>
        </svg>
        <span>{{ authenticated ? '已通行' : '未解锁' }}</span>
      </button>
    </div>
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

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  justify-content: flex-end;
}

.header-note {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.auth-badge-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  background: var(--paper-1);
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--success);
  cursor: pointer;
  transition: all var(--duration-1) var(--ease-out);
}

.auth-badge-btn:hover {
  background: var(--paper-2);
  border-color: var(--line-strong);
}

.auth-badge-btn.locked {
  color: var(--accent);
  border-color: var(--accent-soft);
  background: var(--accent-soft);
}

@media (max-width: 640px) {
  .site-header {
    grid-template-columns: auto 1fr auto;
  }

  .header-note {
    display: none;
  }
}
</style>
