<script setup lang="ts">
import { computed, onMounted, onUnmounted, toRef, watch, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ImportPanel from '@/components/ImportPanel.vue'
import LibraryHero from '@/components/library/LibraryHero.vue'
import TagFilterBar from '@/components/library/TagFilterBar.vue'
import ComicGrid from '@/components/library/ComicGrid.vue'
import ImageSearchChip from '@/components/library/ImageSearchChip.vue'
import ThemeSelect from '@/components/ThemeSelect.vue'
import AppIcon from '@/components/AppIcon.vue'
import { useLibraryStore } from '@/stores/library'
import { useExperimentsStore } from '@/stores/experiments'
import { useLibraryFilter } from '@/composables/useLibraryFilter'
import { useImageSearch } from '@/composables/useImageSearch'
import { useToast } from '@/composables/useToast'
import { useViewTransition } from '@/composables/useViewTransition'
import { useAuth } from '@/composables/useAuth'

/**
 * 书架首页 —— 纯编排视图。
 * 检索/排序/过滤下沉至 useLibraryFilter，子区段下沉至 components/library/。
 */
const store = useLibraryStore()
const experiments = useExperimentsStore()
const route = useRoute()
const router = useRouter()
const { toast } = useToast()
const { withViewTransition } = useViewTransition()
const { canWrite } = useAuth()
const fileInput = ref<HTMLInputElement | null>(null)

const activeSource = computed(() =>
  typeof route.query.source === 'string' ? route.query.source : '',
)

const {
  isAvailable,
  isChecking,
  isSearching,
  error: searchError,
  searchImagePreviewUrl,
  searchResults,
  searchWithFile,
  clearImage,
  checkStatus,
  handlePaste,
  handleDrop,
} = useImageSearch()

// 遵守 DESIGN_NOTES §13 约束：Composable 返回值在 setup 顶层解构
const {
  search,
  activeTag,
  favoritesOnly,
  sortBy,
  sourceItems,
  totalPages,
  totalCachedPages,
  tagCounts,
  imageSearchMatchMap,
  filtered,
  setSort,
} = useLibraryFilter(toRef(store, 'items'), activeSource, searchResults)

onMounted(() => {
  void store.load()
  store.startPollingIfActive()
  window.addEventListener('paste', handlePaste)
})

onUnmounted(() => {
  window.removeEventListener('paste', handlePaste)
})

function onFavoriteToggled(source: string, sourceId: string, favorite: boolean) {
  if (favoritesOnly.value) {
    void withViewTransition(() => {
      store.setFavoriteLocal(source, sourceId, favorite)
    })
  } else {
    store.setFavoriteLocal(source, sourceId, favorite)
  }
}

function selectTag(tag: string) {
  void withViewTransition(() => {
    activeTag.value = tag
  })
}

function toggleFavorites() {
  void withViewTransition(() => {
    favoritesOnly.value = !favoritesOnly.value
  })
}

function onSortChange(value: string) {
  void withViewTransition(() => {
    setSort(value)
  })
}

function onClearImage() {
  void withViewTransition(() => {
    clearImage()
  })
}

function openComic(source: string, sourceId: string) {
  router.push(`/comic/${source}/${sourceId}`)
}

function onFileSelected(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    void searchWithFile(file)
    target.value = '' // Reset
  }
}

const cameraBtnTooltip = computed(() => {
  if (isChecking.value) return '正在探测识图服务...'
  if (isAvailable.value) return '上传图片以图搜图'
  return '识图服务未连接，点击重新探测'
})

async function onCameraClick() {
  if (isChecking.value) return
  if (isAvailable.value || (await checkStatus(true))) {
    fileInput.value?.click()
  } else {
    toast('识图服务未启动或无法连接，请确认后台服务已开启', 'error')
  }
}

watch(
  () => store.error,
  (value) => {
    if (value) toast(value, 'error')
  },
)

watch(searchError, (value) => {
  if (value) toast(value, 'error')
})
</script>

<template>
  <div class="library-view" @drop.prevent="handleDrop" @dragover.prevent>
    <LibraryHero
      :book-count="sourceItems.length"
      :cached-pages="totalCachedPages"
      :total-pages="totalPages"
    >
      <template #import v-if="canWrite">
        <ImportPanel class="hero-import" @imported="openComic" />
      </template>
    </LibraryHero>

    <section class="shelf container" aria-labelledby="shelf-title">
      <div class="shelf-head">
        <div>
          <p class="eyebrow">The stacks</p>
          <h2 id="shelf-title">{{ activeSource ? '来源收藏' : '全部收藏' }}</h2>
        </div>

        <div class="search-container">
          <label class="search-field field">
            <span aria-hidden="true">⌕</span>
            <ImageSearchChip
              v-if="searchImagePreviewUrl"
              :preview-url="searchImagePreviewUrl"
              :is-searching="isSearching"
              @clear="onClearImage"
              class="search-lens-pill"
            />
            <input v-model="search" type="search" placeholder="标题 / 车号 / 作者 / 标签" />
            <button
              class="camera-btn icon-btn"
              type="button"
              :class="{ 'is-muted': !isAvailable, 'is-loading': isChecking }"
              :title="cameraBtnTooltip"
              :aria-label="cameraBtnTooltip"
              :aria-busy="isChecking"
              @click="onCameraClick"
            >
              <AppIcon name="camera" size="md" />
            </button>
            <input
              ref="fileInput"
              type="file"
              accept="image/*"
              class="visually-hidden"
              @change="onFileSelected"
            />
          </label>
        </div>

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
            @update:model-value="onSortChange"
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
        @toggle-favorites="toggleFavorites"
        @select-tag="selectTag"
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
        :search-match-map="imageSearchMatchMap"
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
  position: relative;
  isolation: isolate;
  overflow-x: clip;
  padding-bottom: var(--space-10);
  min-height: 100vh;
}

.shelf,
.site-foot {
  position: relative;
  z-index: 1;
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

.search-container {
  display: flex;
  align-items: center;
  width: 100%;
}

.search-field {
  min-height: 2.8rem;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding-right: var(--space-2);
}

.search-field input[type='search'] {
  flex: 1;
  min-width: 0;
}

.search-lens-pill {
  flex-shrink: 0;
}

.camera-btn {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  color: var(--ink-2);
  transition:
    color var(--duration-2) var(--ease-out),
    opacity var(--duration-2) var(--ease-out);
  cursor: pointer;
}

.camera-btn:hover {
  color: var(--ink-0);
}

.camera-btn.is-muted {
  opacity: 0.55;
}

.camera-btn.is-muted:hover {
  opacity: 0.9;
}

.camera-btn.is-loading {
  opacity: 0.35;
  cursor: wait;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
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

  .search-container {
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
