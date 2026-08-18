<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ImportPanel from '@/components/ImportPanel.vue'
import LibraryHero from '@/components/library/LibraryHero.vue'
import TagFilterBar from '@/components/library/TagFilterBar.vue'
import ComicGrid from '@/components/library/ComicGrid.vue'
import ThemeSelect from '@/components/ThemeSelect.vue'
import { useLibraryStore } from '@/stores/library'
import { useExperimentsStore } from '@/stores/experiments'
import { useToast } from '@/composables/useToast'

/**
 * 书架首页 —— 只负责"数据源 + 筛选状态"的编排。
 * hero / 标签筛选条 / 卡片网格已下沉到 components/library/，
 * 本文件保留：来源过滤、搜索/标签/收藏/排序等筛选状态与派生计算。
 */

const store = useLibraryStore()
const experiments = useExperimentsStore()
const route = useRoute()
const router = useRouter()
const { toast } = useToast()

const search = ref('')
const activeTag = ref('')
const favoritesOnly = ref(false)
const sortBy = ref<'recent' | 'title' | 'pages' | 'cached'>('recent')

onMounted(() => {
  void store.load()
  // 页面加载后若仍有后台缓存任务在跑，立即恢复实时进度轮询。
  store.startPollingIfActive()
})

const activeSource = computed(() =>
  typeof route.query.source === 'string' ? route.query.source : '',
)

const sourceItems = computed(() =>
  activeSource.value
    ? store.items.filter((item) => item.source === activeSource.value)
    : store.items,
)

const totalPages = computed(() => sourceItems.value.reduce((sum, item) => sum + item.page_count, 0))

const totalCachedPages = computed(() =>
  sourceItems.value.reduce((sum, item) => sum + item.cached_pages, 0),
)

const tagCounts = computed(() => {
  const counts = new Map<string, number>()
  for (const item of sourceItems.value) {
    for (const tag of item.tags) {
      counts.set(tag, (counts.get(tag) ?? 0) + 1)
    }
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 18)
})

const filtered = computed(() => {
  const needle = search.value.trim().toLocaleLowerCase()
  let items = sourceItems.value.filter((item) => {
    const matchSearch =
      needle.length === 0 ||
      item.title.toLocaleLowerCase().includes(needle) ||
      item.display_id.toLocaleLowerCase().includes(needle) ||
      item.authors.some((value) => value.toLocaleLowerCase().includes(needle)) ||
      item.works.some((value) => value.toLocaleLowerCase().includes(needle)) ||
      item.actors.some((value) => value.toLocaleLowerCase().includes(needle)) ||
      item.tags.some((value) => value.toLocaleLowerCase().includes(needle))

    const matchTag = activeTag.value === '' || item.tags.includes(activeTag.value)
    const matchFavorite = !favoritesOnly.value || item.favorite
    return matchSearch && matchTag && matchFavorite
  })

  items = [...items]
  switch (sortBy.value) {
    case 'title':
      items.sort((a, b) => a.title.localeCompare(b.title, 'zh-CN'))
      break
    case 'pages':
      items.sort((a, b) => b.page_count - a.page_count)
      break
    case 'cached':
      items.sort(
        (a, b) =>
          b.cached_pages / Math.max(b.page_count, 1) - a.cached_pages / Math.max(a.page_count, 1),
      )
      break
    default:
      items.sort(
        (a, b) => new Date(b.imported_at || 0).getTime() - new Date(a.imported_at || 0).getTime(),
      )
  }
  return items
})

function setSort(value: string) {
  sortBy.value = value as typeof sortBy.value
}

/**
 * 喜欢按钮已经在 board card 里完成了 api.setFavorite（乐观），
 * 这里只本地更新 store 里的那一项，不整表刷新，避免列表全部重绘闪屏。
 */
function onFavoriteToggled(source: string, sourceId: string, favorite: boolean) {
  store.setFavoriteLocal(source, sourceId, favorite)
}

function openComic(source: string, sourceId: string) {
  router.push(`/comic/${source}/${sourceId}`)
}

watch(
  () => store.error,
  (value) => {
    if (value) toast(value, 'error')
  },
)
</script>

<template>
  <div class="library-view">
    <LibraryHero
      :book-count="sourceItems.length"
      :cached-pages="totalCachedPages"
      :total-pages="totalPages"
    >
      <template #import>
        <ImportPanel class="hero-import" @imported="openComic" />
      </template>
    </LibraryHero>

    <section class="shelf container" aria-labelledby="shelf-title">
      <div class="shelf-head">
        <div>
          <p class="eyebrow">The stacks</p>
          <h2 id="shelf-title">{{ activeSource ? '来源收藏' : '全部收藏' }}</h2>
        </div>

        <label class="search-field field">
          <span aria-hidden="true">⌕</span>
          <input v-model="search" type="search" placeholder="标题 / 车号 / 作者 / 标签" />
        </label>

        <div class="sort-field">
          <span>排序</span>
          <ThemeSelect
            label="排序"
            :model-value="sortBy"
            :options="[
              { value: 'recent', label: '最近收录' },
              { value: 'title', label: '标题' },
              { value: 'pages', label: '页数' },
              { value: 'cached', label: '本地完整度' },
            ]"
            @update:model-value="setSort"
          />
        </div>
      </div>

      <div v-if="experiments.htmlCanvasSupported" class="experiment-bar surface">
        <div>
          <span class="eyebrow">Experiment</span>
          <p>
            HTML-in-Canvas 卡片：把整张书架卡片的
            <strong>封面 + 标题 + 标签 + 缓存进度</strong>
            等多个 DOM 节点绘制进一个 canvas。
          </p>
        </div>
        <label class="experiment-toggle">
          <input v-model="experiments.htmlCanvasCards" type="checkbox" />
          <span>启用 Canvas 卡片</span>
          <small>启用后书架卡片会显示 CANVAS 徽标</small>
        </label>
      </div>

      <TagFilterBar
        :favorites-only="favoritesOnly"
        :active-tag="activeTag"
        :tag-counts="tagCounts"
        :filtered-count="filtered.length"
        @toggle-favorites="favoritesOnly = !favoritesOnly"
        @select-tag="activeTag = $event"
      />

      <p v-if="store.activeCachingCount" class="cache-active-note" role="status">
        <span class="cache-active-note__dot" aria-hidden="true" />
        后台正在缓存 {{ store.activeCachingCount }} 本，进度会在卡片上实时更新
      </p>

      <ComicGrid
        :loading="store.loading"
        :items="filtered"
        :use-canvas="experiments.htmlCanvasCards"
        :has-any-items="store.items.length > 0"
        :live-cache="store.liveCache"
        @favorite-toggled="onFavoriteToggled"
      />
    </section>

    <footer class="site-foot container">
      <p>本工具只代理你主动输入的作品，仅用于学习与个人备份；请支持原作者，勿传播盗版内容。</p>
    </footer>
  </div>
</template>

<style scoped>
.library-view {
  padding-bottom: var(--space-10);
}

.shelf {
  padding-top: var(--space-6);
}

.shelf-head {
  display: grid;
  grid-template-columns: auto minmax(16rem, 26rem) auto;
  gap: var(--space-4);
  align-items: end;
  padding-bottom: var(--space-5);
  border-bottom: 1px solid var(--line-strong);
}

.shelf-head h2 {
  font-size: var(--text-2xl);
}

.search-field {
  min-height: 2.8rem;
}

.sort-field {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--ink-2);
}

.experiment-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-4);
  margin-top: var(--space-4);
  padding: var(--space-3) var(--space-4);
  font-size: var(--text-xs);
  color: var(--ink-1);
}

.experiment-bar p {
  margin: 0;
  line-height: 1.6;
}

.experiment-toggle {
  display: grid;
  justify-items: start;
  gap: 0.25rem;
  white-space: nowrap;
}

.experiment-toggle input {
  accent-color: var(--accent);
}

.experiment-toggle small {
  color: var(--ink-2);
  font-size: 0.7rem;
}

.cache-active-note {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-4);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--line);
  border-radius: 999px;
  background: color-mix(in oklab, var(--paper-0) 72%, var(--paper-1));
  color: var(--ink-2);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

.cache-active-note__dot {
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 999px;
  background: var(--accent);
  animation: cache-note-pulse var(--duration-2) var(--ease-out) infinite;
}

.site-foot {
  margin-top: var(--space-10);
  padding-top: var(--space-5);
  border-top: 1px solid var(--line);
  color: var(--ink-2);
  font-size: var(--text-xs);
  text-align: center;
}

@keyframes cache-note-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

@media (prefers-reduced-motion: reduce) {
  .cache-active-note__dot {
    animation: none;
  }
}

@media (max-width: 960px) {
  .shelf-head {
    grid-template-columns: 1fr auto;
  }

  .search-field {
    grid-column: 1 / -1;
    grid-row: 2;
  }
}

@media (max-width: 760px) {
  .experiment-bar {
    align-items: flex-start;
    flex-direction: column;
  }

  .experiment-toggle {
    white-space: normal;
  }
}

@media (max-width: 560px) {
  .shelf-head {
    grid-template-columns: 1fr;
  }

  .sort-field {
    justify-content: space-between;
  }
}
</style>
