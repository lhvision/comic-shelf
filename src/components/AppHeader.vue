<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useEventListener, useResizeObserver, useScroll } from '@vueuse/core'
import { api, onAuthSuccess } from '@/api/client'
import { useAuth } from '@/composables/useAuth'
import { useBrandIcon } from '@/composables/useBrandIcon'
import AppIcon from '@/components/AppIcon.vue'
import StoragePopover from '@/components/StoragePopover.vue'
import GuestModal from '@/components/curator/GuestModal.vue'
import { useGuestPasses } from '@/composables/useGuestPasses'
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
const { authRequired, isGuest, canWrite, logout, openModal } = useAuth()
const { brandIcon } = useBrandIcon()
const { openModal: openGuestModal } = useGuestPasses()

const navScrollEl = ref<HTMLElement | null>(null)
const { arrivedState, measure } = useScroll(navScrollEl)

useResizeObserver(navScrollEl, () => {
  measure()
})
useEventListener('resize', () => {
  measure()
})

const navItems = computed<NavItem[]>(() => {
  const items: NavItem[] = [
    { to: '/', label: '全部' },
    ...providers.value.map((provider, index) => ({
      to: `/?source=${provider.key}`,
      label: provider.short_label || provider.label,
      index: String(index + 1).padStart(2, '0'),
      sourceKey: provider.key,
    })),
  ]
  if (canWrite.value) {
    items.push({
      to: '/discovery',
      label: '发现',
      index: '精选',
    })
  }
  return items
})

function isActive(item: NavItem) {
  if (item.to === '/discovery') {
    return route.path === '/discovery'
  }
  if (route.path !== '/') return false
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
    <div class="header-left">
      <button class="brand" type="button" @click="goLibrary" aria-label="回到全部收藏">
        <img class="brand-mark" :src="brandIcon" alt="" aria-hidden="true" />
        <span>
          <strong>纸间</strong>
          <small>Paper Room</small>
        </span>
      </button>

      <nav
        ref="navScrollEl"
        class="site-nav"
        :class="{
          'has-scroll-left': !arrivedState.left,
          'has-scroll-right': !arrivedState.right,
        }"
        aria-label="来源导航"
      >
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          :class="{ active: isActive(item) }"
        >
          <span v-if="item.index" class="nav-index">{{ item.index }}</span>
          <span class="nav-label">{{ item.label }}</span>
        </RouterLink>
      </nav>
    </div>

    <div class="header-right">
      <p class="header-note">本地优先 · 缓存后不再访问远端</p>
      <StoragePopover />
      <button
        v-if="canWrite"
        type="button"
        class="guest-roster-btn"
        title="打开访客簿，管理与印发专属通行证"
        @click="openGuestModal"
      >
        <AppIcon name="users" size="xs" :stroke-width="1.8" />
        <span class="guest-roster-label">〔 访客簿 〕</span>
      </button>

      <button
        v-if="authRequired"
        type="button"
        class="auth-badge-btn"
        :class="{
          curator: canWrite,
          guest: isGuest,
          locked: !canWrite && !isGuest,
        }"
        :title="
          canWrite
            ? '馆长管理中（点击退出管理回到访客）'
            : isGuest
              ? '访客阅览中（点击解锁馆长权限）'
              : '点击输入通行口令'
        "
        @click="canWrite ? logout() : openModal()"
      >
        <AppIcon
          :name="canWrite ? 'unlock' : isGuest ? 'book-open' : 'lock'"
          size="xs"
          :stroke-width="2"
        />
        <span class="auth-label">
          {{ canWrite ? '〔 馆长已入座 〕' : isGuest ? '〔 访客阅览 〕' : '未解锁' }}
        </span>
      </button>
    </div>
    <GuestModal />
  </header>
</template>

<style scoped>
.site-header {
  position: sticky;
  top: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-height: var(--header-h);
  padding: 0 var(--page-pad);
  border-bottom: 1px solid var(--line);
  background: color-mix(in oklab, var(--paper-0) 82%, transparent);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  transform: translateZ(0);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  min-width: 0;
  flex: 1;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2-5);
  padding: 0;
  background: transparent;
  color: var(--ink-0);
  text-align: left;
  flex-shrink: 0;
}

.brand-mark {
  width: 2.25rem;
  height: 2.25rem;
  object-fit: contain;
  border-radius: 0.5rem;
  background: color-mix(in oklab, var(--ink-0) 6%, transparent);
  transition: rotate var(--duration-2) var(--ease-spring);
  flex-shrink: 0;
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
  white-space: nowrap;
}

.brand small {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  letter-spacing: 0.14em;
  color: var(--ink-2);
  text-transform: uppercase;
  white-space: nowrap;
}

.site-nav {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-4);
  align-self: stretch;
  min-width: 0;
  overflow-x: auto;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
  padding: 0 var(--space-2);
  /* 优雅的纸卷渐变边缘羽化遮罩，感知与引导横向滑动手势 */
  mask-image: linear-gradient(
    to right,
    transparent 0,
    black var(--mask-left, 0px),
    black calc(100% - var(--mask-right, 0px)),
    transparent 100%
  );
  -webkit-mask-image: linear-gradient(
    to right,
    transparent 0,
    black var(--mask-left, 0px),
    black calc(100% - var(--mask-right, 0px)),
    transparent 100%
  );
  transition:
    --mask-left var(--duration-2) var(--ease-out),
    --mask-right var(--duration-2) var(--ease-out);
}

.site-nav.has-scroll-left {
  --mask-left: 1.25rem;
}

.site-nav.has-scroll-right {
  --mask-right: 1.5rem;
}

.site-nav::-webkit-scrollbar {
  display: none;
}

.site-nav a {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--space-1-5);
  font-size: var(--text-sm);
  color: var(--ink-1);
  transition: color var(--duration-1) var(--ease-out);
  white-space: nowrap;
  flex-shrink: 0;
  height: 100%;
  padding: 0 var(--space-1);
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
  line-height: 1;
}

.nav-label {
  white-space: nowrap;
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  justify-content: flex-end;
  flex-shrink: 0;
}

.header-note {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
  white-space: nowrap;
}

.guest-roster-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  line-height: 1.5;
  background: var(--paper-1);
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-1);
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all var(--duration-1) var(--ease-out);
}

.guest-roster-btn:hover {
  background: var(--paper-2);
  border-color: var(--accent);
  color: var(--accent);
}

.auth-badge-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  line-height: 1.5;
  background: var(--paper-1);
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-1);
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all var(--duration-1) var(--ease-out);
}

.auth-badge-btn:hover {
  background: var(--paper-2);
  border-color: var(--line-strong);
}

.auth-badge-btn.curator {
  color: var(--accent-strong);
  border-color: color-mix(in oklab, var(--accent) 30%, var(--line));
  background: var(--accent-soft);
}

.auth-badge-btn.curator:hover {
  background: color-mix(in oklab, var(--accent) 22%, var(--paper-0));
}

.auth-badge-btn.guest {
  color: var(--ink-2);
  border-color: var(--line);
  background: color-mix(in oklab, var(--paper-0) 60%, var(--paper-1));
}

.auth-badge-btn.guest:hover {
  color: var(--ink-0);
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
    gap: var(--space-2);
    padding: 0 var(--space-3);
  }

  .header-left {
    gap: var(--space-2);
  }

  .header-right {
    gap: var(--space-2);
  }

  .header-note {
    display: none;
  }

  .site-nav {
    gap: var(--space-2);
    padding: 0 var(--space-1);
  }

  .site-nav a {
    font-size: var(--text-xs);
    gap: var(--space-1);
  }

  .brand small {
    display: none;
  }

  .brand-mark {
    width: 2rem;
    height: 2rem;
  }

  .guest-roster-label,
  .auth-label {
    display: none;
  }

  .guest-roster-btn,
  .auth-badge-btn {
    width: var(--control-sm);
    height: var(--control-sm);
    min-width: var(--control-sm);
    min-height: var(--control-sm);
    padding: 0;
    justify-content: center;
  }
}

@media (max-width: 640px) and (pointer: coarse) {
  .guest-roster-btn::before,
  .auth-badge-btn::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    min-width: 44px;
    min-height: 44px;
  }
}
</style>
