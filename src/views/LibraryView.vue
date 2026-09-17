<script setup lang="ts">
import {
  computed,
  defineAsyncComponent,
  nextTick,
  onMounted,
  ref,
  useTemplateRef,
  watch,
} from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { useEventListener, useFileDialog } from '@vueuse/core'

const ImportPanel = defineAsyncComponent(() => import('@/components/ImportPanel.vue'))
import LibraryHero from '@/components/library/LibraryHero.vue'
import TagFilterBar from '@/components/library/TagFilterBar.vue'
import ComicGrid from '@/components/library/ComicGrid.vue'
import ImageSearchChip from '@/components/library/ImageSearchChip.vue'
import DialogueSearchPopover from '@/components/library/DialogueSearchPopover.vue'
import SearchCommandChip from '@/components/library/SearchCommandChip.vue'
import SearchCommandMenu from '@/components/library/SearchCommandMenu.vue'
import ThemeSelect from '@/components/ThemeSelect.vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import { useLibraryStore } from '@/stores/library'
import { useLibraryFilter } from '@/composables/useLibraryFilter'
import { useLibrarySync } from '@/composables/useLibrarySync'
import { useShelfState } from '@/composables/useShelfState'
import { useImageSearch } from '@/composables/useImageSearch'
import { useShelfSearch } from '@/composables/useShelfSearch'
import { AVAILABLE_COMMANDS } from '@/composables/useSearchCommands'
import { useToast } from '@/composables/useToast'
import { useAuth } from '@/composables/useAuth'
import { useSystemEvents } from '@/composables/useSystemEvents'
import { useOfflineSync } from '@/composables/useOfflineSync'
import { api, DEFAULT_PROVIDERS } from '@/api/client'
import type { ProviderInfo } from '@/types'

const store = useLibraryStore()
const route = useRoute()
const router = useRouter()
const { toast } = useToast()
const { canWrite, userId } = useAuth()
const { broadcastLocalChange } = useSystemEvents()
const { isOnline } = useOfflineSync()
const providers = ref<ProviderInfo[]>(DEFAULT_PROVIDERS)

const shelf = useShelfState()
const { activeUnfoldCount, archiveOpen, archiveUnfoldCount, unifiedUnfoldCount, tagTrayExpanded } =
  shelf

const activeSource = computed(() =>
  typeof route.query.source === 'string' ? route.query.source : '',
)
const shelfTitle = computed(
  () =>
    ({ jm: '禁漫天堂藏书', picacg: '哔咔漫画藏书', local: '本地自建图集' })[activeSource.value] ??
    '全部藏书',
)

const imageSearch = useImageSearch()
const cameraBtnTooltip = computed(() =>
  imageSearch.isChecking.value
    ? '正在探测识图服务...'
    : imageSearch.isAvailable.value
      ? '上传图片以图搜图'
      : '识图服务未连接，点击重新探测',
)

const { open: openFileDialog, onChange: onFileDialogChange } = useFileDialog({
  accept: 'image/*',
  multiple: false,
})
onFileDialogChange((files) => {
  if (files?.[0]) void imageSearch.searchWithFile(files[0])
})

async function onCameraClick() {
  if (imageSearch.isChecking.value) return
  if (imageSearch.isAvailable.value || (await imageSearch.checkStatus(true))) {
    openFileDialog()
  } else {
    toast('识图服务未启动或无法连接，请确认后台服务已开启', 'error')
  }
}

useEventListener(window, 'paste', imageSearch.handlePaste)

const {
  search,
  activeTags,
  favoritesOnly,
  readingStatus,
  sortBy,
  totalBooks,
  totalPages,
  totalCachedPages,
  tagCounts,
  imageSearchMatchMap,
  filtered,
} = useLibraryFilter(
  computed(() => store.items || []),
  activeSource,
  imageSearch.searchResults,
  {
    search: shelf.search,
    activeTags: shelf.activeTags,
    favoritesOnly: shelf.favoritesOnly,
    readingStatus: shelf.readingStatus,
    sortBy: shelf.sortBy,
    facets: computed(() => store.facets),
  },
)

const { fetchLibrary } = useLibrarySync({
  activeSource,
  search,
  activeTags,
  favoritesOnly,
  readingStatus,
  sortBy,
  imageSearchResults: imageSearch.searchResults,
})

const searchContainerEl = useTemplateRef<HTMLElement>('searchContainerEl')
const searchInputEl = useTemplateRef<HTMLInputElement>('searchInputEl')

const {
  searchInput,
  searchActiveCommand,
  searchPlaceholder,
  isCommandMenuOpen,
  commandMenuFocusedIndex,
  commandFilteredCommands,
  isDialogueOpen,
  dialogueResults,
  dialogueTotal,
  isDialogueSearching,
  dialogueError,
  dialogueQuery,
  dialogueFocusedIndex,
  handleSelectCommand,
  handleClearCommand,
  closeDialogueSearch,
  onSearchFocus,
  onSearchKeydown,
  navigateToResult,
} = useShelfSearch({
  activeSource,
  shelfSearch: search,
  filteredItems: filtered,
  allItems: computed(() => store.items || []),
  router,
  toast,
  searchContainerRef: searchContainerEl,
  searchInputRef: searchInputEl,
})

onBeforeRouteLeave(() => shelf.saveScrollPosition(window.scrollY))

watch(activeSource, (newSource, oldSource) => {
  if (oldSource !== undefined && newSource !== oldSource) {
    shelf.resetAllShelfState()
    window.scrollTo({ top: 0, behavior: 'instant' })
  }
})

onMounted(() => {
  if (shelf.shelfScrollY.value > 0) {
    nextTick(() => window.scrollTo({ top: shelf.shelfScrollY.value, behavior: 'instant' }))
  }
  if (shelf.search.value && !searchInput.value) {
    searchInput.value = shelf.search.value
  }
  void fetchLibrary(true, true)
  store.startPollingIfActive()
  api
    .providers()
    .then((res) => (providers.value = res))
    .catch(() => {})
})

function onFavoriteToggled(source: string, sourceId: string, favorite: boolean) {
  store.setFavoriteLocal(source, sourceId, favorite, userId.value)
  broadcastLocalChange({
    action: 'favorite_changed',
    source,
    source_id: sourceId,
    favorite,
    timestamp: Date.now(),
  })
}

const openComic = (s: string, id: string) => router.push(`/comic/${s}/${id}`)

watch([() => store.error, imageSearch.error], ([err1, err2]) => {
  const err = err1 || err2
  if (err) toast(err, 'error')
})
</script>

<template>
  <div class="library-view" @drop.prevent="imageSearch.handleDrop" @dragover.prevent>
    <LibraryHero
      :book-count="totalBooks"
      :cached-pages="totalCachedPages"
      :total-pages="totalPages"
      :active-source="activeSource"
      :can-write="canWrite && isOnline && !store.isOffline"
      :providers="providers"
    >
      <template #import v-if="canWrite && isOnline && !store.isOffline && activeSource">
        <ImportPanel :source="activeSource" @imported="openComic" />
      </template>
    </LibraryHero>

    <section class="shelf container" aria-labelledby="shelf-title">
      <div class="shelf-head">
        <div>
          <h2 id="shelf-title">{{ shelfTitle }}</h2>
        </div>

        <div ref="searchContainerEl" class="search-container">
          <div class="search-field field" role="search">
            <AppIcon name="search" size="xs" aria-hidden="true" />
            <SearchCommandChip
              v-if="searchActiveCommand"
              :command="searchActiveCommand"
              :label="AVAILABLE_COMMANDS.find((c) => c.id === searchActiveCommand)?.label || ''"
              @clear="handleClearCommand"
            />
            <ImageSearchChip
              v-if="imageSearch.searchImagePreviewUrl.value"
              :preview-url="imageSearch.searchImagePreviewUrl.value"
              :is-searching="imageSearch.isSearching.value"
              @clear="imageSearch.clearImage"
              class="search-lens-pill"
            />
            <input
              ref="searchInputEl"
              v-model="searchInput"
              type="search"
              role="combobox"
              aria-label="搜索书架藏书或输入 / 唤出快捷命令"
              aria-autocomplete="list"
              :aria-expanded="isCommandMenuOpen || isDialogueOpen"
              aria-haspopup="listbox"
              :aria-controls="
                isCommandMenuOpen
                  ? 'search-command-menu'
                  : isDialogueOpen
                    ? 'dialogue-search-popover'
                    : undefined
              "
              :aria-activedescendant="
                isCommandMenuOpen && commandFilteredCommands.length > 0
                  ? `cmd-opt-${commandMenuFocusedIndex}`
                  : isDialogueOpen && dialogueResults.length > 0 && dialogueFocusedIndex >= 0
                    ? `dialogue-opt-${dialogueFocusedIndex}`
                    : undefined
              "
              :placeholder="searchPlaceholder"
              @focus="onSearchFocus"
              @keydown="onSearchKeydown"
            />
            <AppButton
              class="camera-btn"
              shape="circle"
              variant="ghost"
              size="md"
              icon="camera"
              :class="{
                'is-muted': !imageSearch.isAvailable.value,
              }"
              :loading="imageSearch.isChecking.value"
              :title="cameraBtnTooltip"
              :aria-label="cameraBtnTooltip"
              @click="onCameraClick"
            />
          </div>

          <!-- 快捷指令选单浮层 -->
          <SearchCommandMenu
            v-model:focused-index="commandMenuFocusedIndex"
            :open="isCommandMenuOpen"
            :commands="commandFilteredCommands"
            @select="handleSelectCommand"
          />

          <!-- 分镜台词检索浮层（专注台词模式呈现） -->
          <DialogueSearchPopover
            v-if="searchActiveCommand === 'dialogue'"
            v-model:focused-index="dialogueFocusedIndex"
            :open="isDialogueOpen"
            :results="dialogueResults"
            :total="dialogueTotal"
            :is-searching="isDialogueSearching"
            :error="dialogueError"
            :query="dialogueQuery"
            @select="navigateToResult"
            @close="closeDialogueSearch"
          />
        </div>

        <div class="sort-field">
          <span>排序</span>
          <ThemeSelect
            v-model="sortBy"
            label="排序"
            :options="[
              { value: 'recent', label: '最近收录（未读优先）' },
              { value: 'title', label: '标题' },
              { value: 'pages', label: '页数' },
              { value: 'cached', label: '本地完整度' },
            ]"
          />
        </div>
      </div>

      <TagFilterBar
        v-model:tray-expanded="tagTrayExpanded"
        v-model:active-tags="activeTags"
        v-model:reading-status="readingStatus"
        :favorites-only="favoritesOnly"
        :tag-counts="tagCounts"
        :filtered-count="filtered.length"
        @toggle-favorites="favoritesOnly = !favoritesOnly"
      />

      <p v-if="store.isOffline || !isOnline" class="offline-active-note" role="status">
        <span class="offline-active-note__badge">
          <AppIcon name="archive" size="xs" />
          <span>〔 纸室离线模式 〕</span>
        </span>
        <span>当前展示本地快照与离线藏书</span>
      </p>

      <p v-if="store.activeCachingCount" class="cache-active-note" role="status">
        <span class="cache-active-note__dot" aria-hidden="true" />
        后台正在缓存 {{ store.activeCachingCount }} 本，进度会在卡片上实时更新
      </p>

      <ComicGrid
        v-model:active-count="activeUnfoldCount"
        v-model:archive-count="archiveUnfoldCount"
        v-model:unified-count="unifiedUnfoldCount"
        v-model:archive-open="archiveOpen"
        :loading="store.loading"
        :items="filtered"
        :has-any-items="totalBooks > 0 || store.items.length > 0"
        :live-cache="store.liveCache"
        :search-match-map="imageSearchMatchMap"
        :is-recent-sort="
          sortBy === 'recent' && !imageSearch.searchImagePreviewUrl.value && !search.trim()
        "
        :has-more="store.hasMore"
        :loading-more="store.loadingMore"
        :total-count="store.total"
        @favorite-toggled="onFavoriteToggled"
        @load-more="store.loadMore()"
        @load-all="store.loadAll()"
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
  position: relative;
  z-index: var(--z-dropdown);
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
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
  z-index: var(--z-dropdown);
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
  min-width: 44px;
  min-height: 44px;
  width: 2.25rem;
  height: 2.25rem;
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

.sort-field {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--ink-2);
}

.offline-active-note {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-4);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--accent-soft);
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--paper-0) 85%, var(--accent-soft));
  color: var(--ink-1);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

.offline-active-note__badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--accent);
  font-weight: 600;
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

@media (max-width: 560px) {
  .shelf-head {
    grid-template-columns: 1fr;
  }

  .sort-field {
    justify-content: space-between;
  }
}
</style>
