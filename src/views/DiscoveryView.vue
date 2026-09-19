<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import DiscoveryCard from '@/components/discovery/DiscoveryCard.vue'
import SegmentedTabs from '@/components/SegmentedTabs.vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import { useDiscovery } from '@/composables/useDiscovery'
import { useDiscoveryWebMCP } from '@/composables/useDiscoveryWebMCP'
import { useAuth } from '@/composables/useAuth'
import { getSourceBadge, getSourceName, getSourceShortName } from '@/utils/source'
import type { DiscoveryItem, DiscoveryTimeframe } from '@/types'

const router = useRouter()
const { canWrite } = useAuth()

// Composable top-level destructuring (DESIGN_NOTES §13)
const {
  source,
  timeframe,
  feed,
  loading,
  refreshing,
  error,
  ingestingMap,
  loadRanking,
  ingestComic,
} = useDiscovery()

useDiscoveryWebMCP({
  source,
  timeframe,
  feed,
  loadRanking,
  ingestComic,
  router,
})

const sourceTabs: { key: 'jm' | 'picacg'; label: string; sub: string }[] = [
  { key: 'jm', label: getSourceName('jm'), sub: getSourceBadge('jm') },
  { key: 'picacg', label: getSourceName('picacg'), sub: getSourceBadge('picacg') },
]

const timeframeTabs = computed(() => {
  if (source.value === 'picacg') {
    return [
      { key: 'week' as const, label: '7天热门', sub: '周榜' },
      { key: 'month' as const, label: '30天热门', sub: '月榜' },
      { key: 'day' as const, label: '24小时榜', sub: '日榜' },
    ]
  }
  return [
    { key: 'week' as const, label: '本周必看', sub: '周榜' },
    { key: 'month' as const, label: '本月热门', sub: '月榜' },
    { key: 'day' as const, label: '今日精选', sub: '日榜' },
  ]
})

const pageSubtitle = computed(
  () =>
    `实时连接${getSourceShortName(source.value)}官方精选与排行，快速发现热门新刊并一键收录至本地书库`,
)

const items = computed<DiscoveryItem[]>(() => feed.value?.items || [])
const inLibraryCount = computed(() => items.value.filter((it) => it.in_library).length)
const totalCount = computed(() => items.value.length)

function selectSource(src: 'jm' | 'picacg') {
  if (loading.value || refreshing.value) return
  void loadRanking(src, timeframe.value, false)
}

function selectTab(tf: DiscoveryTimeframe) {
  if (loading.value || refreshing.value) return
  void loadRanking(source.value, tf, false)
}

function refreshCurrent() {
  if (refreshing.value || loading.value) return
  void loadRanking(source.value, timeframe.value, true)
}

onMounted(() => {
  if (!canWrite.value) {
    void router.replace('/')
    return
  }
  void loadRanking(source.value, timeframe.value, false)
})
</script>

<template>
  <main class="discovery-view container">
    <header class="discovery-header">
      <div class="discovery-title-area">
        <div class="title-with-pill">
          <h1 class="page-title">发现 · 官方精选</h1>
          <span class="pill pill--accent">馆长专属雷达</span>
        </div>
        <p class="page-subtitle">
          {{ pageSubtitle }}
        </p>
      </div>

      <div class="discovery-controls">
        <div class="tabs-group">
          <SegmentedTabs
            v-model="source"
            :items="sourceTabs"
            size="md"
            :disabled="loading || refreshing"
            aria-label="图源榜单"
            @change="selectSource"
          />
          <SegmentedTabs
            v-model="timeframe"
            :items="timeframeTabs"
            size="md"
            :disabled="loading || refreshing"
            aria-label="榜单周期"
            @change="selectTab"
          />
        </div>

        <div class="meta-action-bar">
          <span v-if="feed?.updated_at" class="update-time"> 更新于 {{ feed.updated_at }} </span>
          <span v-if="totalCount > 0" class="badge">
            已收录 {{ inLibraryCount }} / {{ totalCount }}
          </span>
          <AppButton
            variant="ghost"
            size="sm"
            :loading="refreshing"
            :disabled="loading"
            class="refresh-btn"
            @click="refreshCurrent"
          >
            <template #prefix>
              <AppIcon v-if="!refreshing" class="refresh-svg" name="refresh" size="sm" />
            </template>
            <span>{{ refreshing ? '刷新中…' : '刷新榜单' }}</span>
          </AppButton>
        </div>
      </div>
    </header>

    <!-- Error State -->
    <section v-if="error && !items.length" class="state-card error-card">
      <p class="state-msg">获取排行榜失败：{{ error }}</p>
      <AppButton variant="primary" size="md" @click="refreshCurrent"> 重新尝试 </AppButton>
    </section>

    <!-- Loading Skeletons -->
    <section v-else-if="loading && !items.length" class="discovery-grid">
      <div v-for="i in 10" :key="i" class="skeleton-card">
        <div class="skeleton-cover skeleton-shimmer"></div>
        <div class="skeleton-body">
          <div class="skeleton-line line-title skeleton-shimmer"></div>
          <div class="skeleton-line line-meta skeleton-shimmer"></div>
          <div class="skeleton-btn skeleton-shimmer"></div>
        </div>
      </div>
    </section>

    <!-- Content Grid -->
    <section v-else-if="items.length" class="discovery-grid">
      <DiscoveryCard
        v-for="(item, index) in items"
        :key="item.id"
        :item="item"
        :rank="index + 1"
        :ingesting="Boolean(ingestingMap[item.source_id])"
        @ingest="ingestComic"
      />
    </section>

    <!-- Empty State -->
    <section v-else class="state-card empty-card">
      <p class="state-msg">暂无该榜单推荐条目</p>
      <AppButton variant="primary" size="md" @click="refreshCurrent"> 立即刷新 </AppButton>
    </section>
  </main>
</template>

<style scoped>
.discovery-view {
  padding-top: var(--space-6);
  padding-bottom: var(--space-16);
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.discovery-header {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  padding-bottom: var(--space-5);
  border-bottom: 1px solid var(--line);
}

.discovery-title-area {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.title-with-pill {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.page-title {
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--ink-0);
  margin: 0;
  letter-spacing: -0.02em;
}

.page-subtitle {
  font-size: var(--text-sm);
  color: var(--ink-2);
  margin: 0;
}

.discovery-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.tabs-group {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.meta-action-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.update-time {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-2);
}

.refresh-svg {
  display: block;
}

.discovery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--space-5);
}

@media (min-width: 1200px) {
  .discovery-grid {
    grid-template-columns: repeat(5, 1fr);
  }
}

@media (max-width: 640px) {
  .discovery-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-3);
  }
}

.state-card {
  padding: var(--space-12);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  border: 1px dashed var(--line);
  border-radius: var(--radius-3);
  background: var(--paper-0);
  text-align: center;
}

.state-msg {
  font-size: var(--text-sm);
  color: var(--ink-1);
  margin: 0;
}

.skeleton-card {
  border-radius: var(--radius-2);
  border: 1px solid var(--line);
  background: var(--paper-0);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.skeleton-cover {
  aspect-ratio: 3 / 4.15;
}

.skeleton-body {
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.skeleton-line {
  height: 0.875rem;
  border-radius: var(--radius-1);
}

.line-title {
  width: 80%;
}

.line-meta {
  width: 50%;
}

.skeleton-btn {
  height: var(--control-xs);
  border-radius: var(--radius-2);
  margin-top: var(--space-2);
}
</style>
