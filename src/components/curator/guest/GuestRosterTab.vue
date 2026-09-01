<script setup lang="ts">
/**
 * @file GuestRosterTab.vue
 * @description 访客簿现存名册面板。
 *
 * 核心功能：
 * - 模糊搜索（用户名、Token 掩码、已绑定设备名称/IP）；
 * - 状态胶囊筛选（全部、待激活、使用中、已满额、已失效）；
 * - 骨架/加载中、空状态与错误重试编排；
 * - 渲染 `GuestCard` 卡片列表。
 */

import { computed, ref } from 'vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import GuestCard from './GuestCard.vue'
import type { GuestPass } from '@/types'

/** 状态筛选胶囊选项键 */
type FilterKey = 'all' | 'pending' | 'active' | 'full' | 'disabled'

const props = defineProps<{
  /** 通行证全量列表 */
  passes: GuestPass[]
  /** 是否正在拉取名册中 */
  loading: boolean
  /** 拉取失败错误信息 */
  fetchError: string | null
}>()

const emit = defineEmits<{
  /** 触发刷新名册列表 */
  refresh: []
  /** 首张通行证印发引导跳转 */
  issueFirst: []
}>()

/** 当前激活的状态筛选键 */
const currentFilter = ref<FilterKey>('all')
/** 搜索过滤关键字 */
const searchQuery = ref('')

const pendingCount = computed(
  () => props.passes.filter((p) => p.activation_status === 'pending').length,
)
const activeCount = computed(
  () => props.passes.filter((p) => p.activation_status === 'active').length,
)
const fullCount = computed(() => props.passes.filter((p) => p.activation_status === 'full').length)
const disabledCount = computed(
  () =>
    props.passes.filter(
      (p) => p.activation_status === 'disabled' || p.activation_status === 'expired',
    ).length,
)

const filterTabs = computed(() => [
  { key: 'all' as const, label: '全部', count: props.passes.length },
  { key: 'pending' as const, label: '待激活', count: pendingCount.value },
  { key: 'active' as const, label: '使用中', count: activeCount.value },
  { key: 'full' as const, label: '已满额', count: fullCount.value },
  { key: 'disabled' as const, label: '已失效', count: disabledCount.value },
])

const filteredPasses = computed(() => {
  let list = props.passes
  if (currentFilter.value === 'pending') {
    list = list.filter((p) => p.activation_status === 'pending')
  } else if (currentFilter.value === 'active') {
    list = list.filter((p) => p.activation_status === 'active')
  } else if (currentFilter.value === 'full') {
    list = list.filter((p) => p.activation_status === 'full')
  } else if (currentFilter.value === 'disabled') {
    list = list.filter(
      (p) => p.activation_status === 'disabled' || p.activation_status === 'expired',
    )
  }

  const query = searchQuery.value.trim().toLowerCase()
  if (query) {
    list = list.filter((p) => p.username.toLowerCase().includes(query))
  }

  return list
})

function resetFilters() {
  currentFilter.value = 'all'
  searchQuery.value = ''
}
</script>

<template>
  <section
    id="tabpanel-roster"
    class="tab-content roster-pane"
    role="tabpanel"
    aria-label="现存名册列表"
  >
    <div class="roster-toolbar">
      <div class="roster-summary">
        <span class="roster-tip">共登记 {{ passes.length }} 位访客</span>
      </div>
      <div class="roster-toolbar-right">
        <div v-if="passes.length > 2" class="roster-search-box">
          <AppIcon name="search" size="xs" class="search-icon" />
          <input
            v-model="searchQuery"
            type="search"
            class="roster-search-input"
            placeholder="搜索访客..."
            aria-label="搜索访客名称"
          />
        </div>
        <button
          type="button"
          class="refresh-btn"
          title="重新获取最新名册数据"
          :disabled="loading"
          @click="emit('refresh')"
        >
          <AppIcon name="refresh" size="xs" :class="{ 'spin-icon': loading }" />
          <span>刷新</span>
        </button>
      </div>
    </div>

    <!-- 状态快捷筛选胶囊 -->
    <div
      v-if="passes.length > 0"
      class="filter-bar"
      role="radiogroup"
      aria-label="名册激活状态筛选"
    >
      <button
        v-for="flt in filterTabs"
        :key="flt.key"
        type="button"
        class="filter-tab-btn"
        :class="{ active: currentFilter === flt.key }"
        :aria-checked="currentFilter === flt.key"
        role="radio"
        @click="currentFilter = flt.key"
      >
        <span>{{ flt.label }}</span>
        <span class="filter-badge">{{ flt.count }}</span>
      </button>
    </div>

    <!-- 加载中 -->
    <div v-if="loading && passes.length === 0" class="state-panel">
      <AppIcon name="refresh" size="lg" class="spin-icon" />
      <p>正在翻阅名册…</p>
    </div>

    <!-- 接口异常 -->
    <div v-else-if="fetchError && passes.length === 0" class="state-panel error">
      <AppIcon name="info" size="lg" />
      <p class="state-msg">{{ fetchError }}</p>
      <button type="button" class="retry-btn" @click="emit('refresh')">重新翻阅名册</button>
    </div>

    <!-- 暂无名册（无数据） -->
    <div v-else-if="passes.length === 0" class="state-panel empty">
      <div class="empty-seal">暂无访客</div>
      <p class="empty-hint">尚未印发任何通行证，点击下方按钮即可派发。</p>
      <AppButton variant="primary" size="md" @click="emit('issueFirst')">
        <AppIcon name="plus" size="sm" />
        <span>登记第一张通行证</span>
      </AppButton>
    </div>

    <!-- 筛选无结果 -->
    <div v-else-if="filteredPasses.length === 0" class="state-panel empty">
      <div class="empty-seal">无匹配通行证</div>
      <p class="empty-hint">当前筛选或搜索条件下暂无访客卡片。</p>
      <AppButton variant="secondary" size="sm" @click="resetFilters">
        <span>重置筛选并查看全部 {{ passes.length }} 位访客</span>
      </AppButton>
    </div>

    <!-- 借书卡名册卡片列表 -->
    <ul v-else class="pass-card-list">
      <GuestCard v-for="item in filteredPasses" :key="item.id" :item="item" />
    </ul>
  </section>
</template>

<style scoped>
.tab-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* 名册面板顶部信息 */
.roster-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: 0 var(--space-1);
}

.roster-summary {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
  white-space: nowrap;
}

.roster-toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.roster-search-box {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0 var(--space-2);
  height: 32px;
  background: var(--paper-1);
  border: 1px solid var(--line);
  border-radius: var(--radius-pill, 9999px);
  color: var(--ink-2);
  transition: all var(--duration-1) var(--ease-out);
}

.roster-search-box:focus-within {
  border-color: var(--accent);
  background: var(--paper-0);
  color: var(--ink-0);
}

.roster-search-input {
  border: none;
  background: transparent;
  padding: 0;
  font-size: var(--text-xs);
  color: var(--ink-0);
  outline: none;
  width: 110px;
}

.roster-search-input::placeholder {
  color: var(--ink-2);
}

.roster-tip {
  font-size: var(--text-caption);
  color: var(--ink-2);
}

.refresh-btn {
  min-height: 32px;
  padding: 0 var(--space-2);
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-1);
  font-size: var(--text-caption);
  color: var(--ink-2);
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all var(--duration-1) var(--ease-out);
}

.refresh-btn:hover {
  color: var(--ink-0);
  border-color: var(--line);
}

/* 状态快捷筛选胶囊栏 */
.filter-bar {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  overflow-x: auto;
  padding: 2px var(--space-1) var(--space-1) var(--space-1);
  scrollbar-width: none;
}

.filter-bar::-webkit-scrollbar {
  display: none;
}

.filter-tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  padding: 0 var(--space-3);
  border-radius: var(--radius-pill, 9999px);
  border: 1px solid var(--line);
  background: var(--paper-1);
  color: var(--ink-1);
  font-size: var(--text-caption);
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--duration-1) var(--ease-out);
}

.filter-tab-btn:hover {
  background: var(--paper-2);
  color: var(--ink-0);
  border-color: var(--line-strong);
}

.filter-tab-btn.active {
  background: var(--paper-0);
  border-color: var(--accent);
  color: var(--accent);
  font-weight: 600;
  box-shadow: var(--shadow-1);
}

.filter-badge {
  font-family: var(--font-mono);
  font-size: 11px;
  padding: 0 6px;
  border-radius: 9999px;
  background: var(--paper-2);
  color: var(--ink-2);
}

.filter-tab-btn.active .filter-badge {
  background: var(--accent-soft);
  color: var(--accent);
}

/* 状态占位 */
.state-panel {
  padding: var(--space-8) var(--space-4);
  text-align: center;
  color: var(--ink-2);
  font-size: var(--text-body);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
}

.state-panel.error {
  color: var(--accent);
}

.retry-btn {
  min-height: 40px;
  padding: 0 var(--space-4);
  border-radius: var(--radius-1);
  border: 1px solid var(--accent);
  background: var(--accent-soft);
  color: var(--accent);
  cursor: pointer;
  font-weight: 600;
}

.empty-seal {
  font-family: var(--font-display);
  font-size: var(--text-title);
  color: var(--ink-2);
  border: 1px solid var(--line);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-1);
  background: var(--paper-1);
}

.empty-hint {
  font-size: var(--text-caption);
  color: var(--ink-2);
  margin-bottom: var(--space-2);
}

/* 名册卡片列表（随 Modal 单源平滑滚动） */
.pass-card-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.spin-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 640px) {
  .roster-toolbar {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
  }

  .roster-toolbar-right {
    display: flex;
    align-items: center;
    gap: var(--space-1-5);
    margin-left: auto;
  }

  .roster-search-box {
    width: auto;
  }

  .roster-search-input {
    width: 90px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spin-icon {
    animation: none !important;
  }
}
</style>
