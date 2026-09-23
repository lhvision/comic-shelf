<script setup lang="ts">
/**
 * @file DialogueSearchPopover.vue
 * @description 书架搜索栏台词全文检索联想面板。
 *
 * 核心特性：
 * 1. Product 模式典藏纸本质感，实体纸面背景与柔和墨影，严禁紫蓝渐变与毛玻璃；
 * 2. 纯声明式解析分镜台词高亮片段，零 v-html，杜绝 XSS 注入风险；
 * 3. 严格符合 WAI-ARIA Combobox / Listbox 无障碍标准契约；
 * 4. 键盘焦点自动同步视口滚动跟随（scrollIntoView），杜绝视口盲航；
 * 5. 封面自适应防崩退化与典藏朱砂金墨分镜导引指示；
 * 6. 一行一页：后端已把同页多个命中气泡聚合成一条，行间展示的是该页最高分的代表句，
 *    同页命中超过一处时在微信息行标注「N 处命中」，单命中不重复宣告。
 */

import { nextTick, ref, useTemplateRef, watch } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import { MAX_HIGHLIGHT_BOXES } from '@/composables/useReaderBubble'
import type { DialogueSearchItem } from '@/types'
import { coverFileUrl } from '@/api/client'
import { getSourceShortName } from '@/utils/source'

const focusedIndex = defineModel<number>('focusedIndex', { default: -1 })

const props = withDefaults(
  defineProps<{
    open: boolean
    results: DialogueSearchItem[]
    total: number
    isSearching: boolean
    error?: string
    query: string
  }>(),
  {
    error: '',
  },
)

const emit = defineEmits<{
  select: [item: DialogueSearchItem]
  close: []
}>()

const listContainerRef = useTemplateRef<HTMLElement>('listContainerRef')
const failedCovers = ref<Record<string, boolean>>({})

function onCoverError(key: string) {
  failedCovers.value[key] = true
}

function getItemCoverUrl(item: DialogueSearchItem): string {
  if (item.cover) return item.cover
  return coverFileUrl(item.source, item.source_id, 0)
}

/**
 * 监听键盘导航索引变化，驱动列表视口平滑对齐跟随
 */
watch(focusedIndex, async (idx) => {
  if (idx === undefined || idx < 0) return
  await nextTick()
  // ref 必须在 nextTick 之后再取：回车选中会先 close() 卸载 v-if 块，
  // 在 await 之前判空挡不住随后到来的 null
  const list = listContainerRef.value
  if (!list) return
  const items = list.querySelectorAll('.result-item')
  const activeEl = items[idx] as HTMLElement | undefined
  if (activeEl) {
    activeEl.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' })
  }
})

const snippetTokensCache = new Map<string, Array<{ text: string; isMark: boolean }>>()

/**
 * 安全解析台词高亮片段，将 `<mark>` 标签转换为安全的结构化 Token 数组（带有限容量缓存加速）
 */
function parseSnippetTokens(raw: string): Array<{ text: string; isMark: boolean }> {
  if (!raw) return []
  const cached = snippetTokensCache.get(raw)
  if (cached) return cached

  const tokens: Array<{ text: string; isMark: boolean }> = []
  const regex = /<mark>(.*?)<\/mark>/gi
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = regex.exec(raw)) !== null) {
    if (match.index > lastIndex) {
      tokens.push({
        text: raw.slice(lastIndex, match.index),
        isMark: false,
      })
    }
    tokens.push({
      text: match[1] ?? '',
      isMark: true,
    })
    lastIndex = regex.lastIndex
  }

  if (lastIndex < raw.length) {
    tokens.push({
      text: raw.slice(lastIndex),
      isMark: false,
    })
  }

  if (snippetTokensCache.size >= 500) {
    snippetTokensCache.clear()
  }
  snippetTokensCache.set(raw, tokens)
  return tokens
}

function getSourceLabel(source: string): string {
  return getSourceShortName(source)
}

function onSelect(item: DialogueSearchItem) {
  emit('select', item)
}

/**
 * 同页多命中的预期管理：报出的两个数必须都对得上画面。
 * 用「至少」是因为 `bubble_count` 是候选池（fetch_limit 行）内的计数，
 * 极端高频页会少报；行内保持简洁，保留口径只在这里说
 */
function hitCountTitle(item: DialogueSearchItem): string {
  const total = item.bubble_count ?? 1
  const drawn = Math.min(total, MAX_HIGHLIGHT_BOXES)
  return drawn >= total
    ? `这一页至少命中 ${total} 处，进入阅读器全部描出`
    : `这一页至少命中 ${total} 处，阅读器只描出最相关的 ${drawn} 格`
}

function onMouseEnterItem(index: number) {
  focusedIndex.value = index
}
</script>

<template>
  <Transition name="popover-fade">
    <div
      v-if="open"
      id="dialogue-search-popover"
      class="dialogue-popover"
      role="listbox"
      aria-label="分镜台词搜索结果"
    >
      <!-- 头部：命中状态与快捷提示 -->
      <div class="popover-head">
        <div class="head-title">
          <AppIcon name="search" size="xs" class="head-icon" />
          <span class="head-text">分镜台词检索</span>
          <span v-if="results.length > 0" class="head-badge">命中 {{ total }} 页</span>
        </div>
        <button
          type="button"
          class="head-close-btn"
          aria-label="关闭台词搜索面板"
          title="关闭 (Esc)"
          @click="emit('close')"
        >
          <kbd class="kbd-hint">Esc</kbd>
          <AppIcon name="close" size="xs" />
        </button>
      </div>

      <!-- 加载中微状态 -->
      <div v-if="isSearching" class="popover-loading">
        <div class="loading-bar" />
        <span class="loading-text">正在翻寻分镜对白与台词…</span>
      </div>

      <!-- 检索异常提示 -->
      <div v-else-if="error" class="popover-error">
        <AppIcon name="info" size="xs" class="error-icon" />
        <span>{{ error }}</span>
      </div>

      <!-- 命中的对白列表 -->
      <div v-else-if="results.length > 0" ref="listContainerRef" class="results-list" tabindex="-1">
        <div
          v-for="(item, idx) in results"
          :id="`dialogue-opt-${idx}`"
          :key="`${item.source}-${item.source_id}-${item.page_index}`"
          class="result-item"
          :class="{ 'is-focused': focusedIndex === idx }"
          role="option"
          :aria-selected="focusedIndex === idx"
          @click="onSelect(item)"
          @mouseenter="onMouseEnterItem(idx)"
        >
          <!-- 漫画封面缩略图 -->
          <div class="item-cover-wrapper">
            <img
              v-if="!failedCovers[`${item.source}-${item.source_id}`]"
              :src="getItemCoverUrl(item)"
              :alt="item.title"
              class="item-cover"
              loading="lazy"
              @error="onCoverError(`${item.source}-${item.source_id}`)"
            />
            <div v-else class="item-cover-fallback">
              <AppIcon name="book-open" size="xs" />
            </div>
          </div>

          <!-- 对白详情区 -->
          <div class="item-body">
            <div class="item-top">
              <span class="source-badge">{{ getSourceLabel(item.source) }}</span>
              <span class="comic-title" :title="item.title">{{ item.title }}</span>
              <span class="page-tag">P.{{ item.page_index }}</span>
            </div>

            <!-- 台词气泡文本片段（朱砂高亮，两行截断） -->
            <div class="dialogue-bubble">
              <template
                v-for="(token, tIdx) in parseSnippetTokens(item.snippet || item.text)"
                :key="tIdx"
              >
                <mark v-if="token.isMark" class="dialogue-mark">{{ token.text }}</mark>
                <span v-else>{{ token.text }}</span>
              </template>
            </div>

            <!-- 分镜微信息：单命中不重复宣告，只有同页多处命中才占这一行 -->
            <div
              v-if="(item.bubble_count ?? 1) > 1 || (item.authors && item.authors.length > 0)"
              class="item-meta"
            >
              <span
                v-if="(item.bubble_count ?? 1) > 1"
                class="meta-item meta-hit"
                aria-describedby="dialogue-hit-note"
                :title="hitCountTitle(item)"
              >
                {{ item.bubble_count }} 处命中
              </span>
              <span v-if="item.authors && item.authors.length > 0" class="meta-item author">
                {{ item.authors.slice(0, 2).join(' / ') }}
              </span>
            </div>
          </div>

          <!-- 直达动作图标 -->
          <div class="item-action" aria-hidden="true">
            <AppIcon name="arrow-right" size="xs" class="action-icon" />
          </div>
        </div>
      </div>

      <!-- 短词提示状态（少于 2 字） -->
      <div v-else-if="query.trim().length < 2" class="popover-empty">
        <AppIcon name="info" size="sm" class="empty-icon" />
        <div class="empty-content">
          <p class="empty-title">请输入至少 2 个字以检索台词</p>
          <p class="empty-hint">分镜台词倒排索引加速检索，支持简繁中文互通</p>
        </div>
      </div>

      <!-- 搜索空状态 -->
      <div v-else class="popover-empty">
        <AppIcon name="info" size="sm" class="empty-icon" />
        <div class="empty-content">
          <p class="empty-title">未在已索引分镜中找到包含「{{ query }}」的台词</p>
          <p class="empty-hint">支持简繁中文双向互通；仅索引已提取分镜气泡的典藏藏书</p>
        </div>
      </div>

      <!-- 底部提示栏 -->
      <p v-if="results.length > 0" id="dialogue-hit-note" class="visually-hidden">
        一行代表一页。标注「N
        处命中」表示这一页有多句台词命中；进入阅读器后，相关度最高的那一句呼吸高亮，
        其余命中气泡最多再描出 {{ MAX_HIGHLIGHT_BOXES - 1 }} 格。
      </p>
      <div class="popover-footer">
        <span class="footer-tip">上下键选择 · 回车直达画页 · 阅读器描出该页命中气泡</span>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.dialogue-popover {
  position: absolute;
  top: calc(100% + var(--space-2));
  left: 0;
  right: 0;
  width: 100%;
  max-width: min(36rem, 100%);
  background: var(--paper-0);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-2);
  box-shadow: var(--shadow-3);
  z-index: var(--z-popover);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 头部 */
.popover-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
  background: var(--paper-1);
  border-bottom: 1px solid var(--line);
}

.head-title {
  display: flex;
  align-items: center;
  gap: var(--space-1-5);
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--ink-1);
}

.head-icon {
  color: var(--accent);
}

.head-badge {
  font-size: var(--text-caption);
  font-family: var(--font-mono);
  padding: 0 var(--space-1-5);
  background: color-mix(in oklab, var(--accent) 14%, transparent);
  color: var(--accent);
  border-radius: var(--radius-1);
}

.head-close-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  background: none;
  border: none;
  min-height: 44px;
  min-width: 44px;
  padding: var(--space-1) var(--space-2);
  color: var(--ink-2);
  cursor: pointer;
  border-radius: var(--radius-1);
  transition: color var(--duration-2) var(--ease-out);
}

.head-close-btn:hover {
  color: var(--ink-0);
}

.kbd-hint {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  background: var(--paper-0);
  border: 1px solid var(--line);
  padding: 0 4px;
  border-radius: 3px;
}

/* 加载状态 */
.popover-loading {
  padding: var(--space-5) var(--space-3);
  text-align: center;
  color: var(--ink-2);
  font-size: var(--text-xs);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
}

.loading-bar {
  width: 50%;
  height: 2px;
  background: color-mix(in oklab, var(--accent) 25%, transparent);
  position: relative;
  overflow: hidden;
  border-radius: 1px;
}

.loading-bar::after {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 40%;
  background: var(--accent);
  animation: bar-pulse 1.2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}

@keyframes bar-pulse {
  0% {
    left: -40%;
  }
  100% {
    left: 100%;
  }
}

/* 错误状态 */
.popover-error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-3);
  color: var(--danger);
  font-size: var(--text-xs);
}

.error-icon {
  flex-shrink: 0;
}

/* 结果列表 */
.results-list {
  max-height: min(24rem, 55vh);
  overflow-y: auto;
  padding: var(--space-1);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  outline: none;
}

.results-list::-webkit-scrollbar {
  width: 6px;
}

.results-list::-webkit-scrollbar-thumb {
  background: var(--line-strong);
  border-radius: 3px;
}

/* 结果条目 */
.result-item {
  display: flex;
  align-items: center;
  gap: var(--space-2-5);
  padding: var(--space-2) var(--space-2-5);
  border-radius: var(--radius-1);
  border: 1px solid transparent;
  background-color: transparent;
  cursor: pointer;
  transition:
    background-color var(--duration-1) var(--ease-out),
    border-color var(--duration-1) var(--ease-out),
    box-shadow var(--duration-1) var(--ease-out);
}

.result-item:hover,
.result-item.is-focused {
  background-color: var(--paper-1);
  border-color: var(--line-strong);
  box-shadow: inset 2px 0 0 var(--accent);
}

/* 封面 */
.item-cover-wrapper {
  width: 40px;
  height: 54px;
  flex-shrink: 0;
  border-radius: var(--radius-1);
  overflow: hidden;
  border: 1px solid var(--line);
  background: var(--paper-2);
  display: flex;
  align-items: center;
  justify-content: center;
}

.item-cover {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.item-cover-fallback {
  color: var(--ink-2);
}

/* 内容主体 */
.item-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.item-top {
  display: flex;
  align-items: center;
  gap: var(--space-1-5);
  font-size: var(--text-xs);
}

.source-badge {
  font-size: var(--text-caption);
  font-weight: 600;
  padding: 1px var(--space-1);
  border-radius: var(--radius-1);
  background: var(--paper-2);
  color: var(--ink-1);
  flex-shrink: 0;
}

.comic-title {
  font-weight: 600;
  color: var(--ink-0);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.page-tag {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--accent);
  background: color-mix(in oklab, var(--accent) 10%, transparent);
  padding: 1px var(--space-1);
  border-radius: var(--radius-1);
  font-weight: 600;
  flex-shrink: 0;
}

/* 对白气泡框（2行优雅截断） */
.dialogue-bubble {
  background: var(--paper-0);
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  padding: var(--space-1) var(--space-2);
  font-size: var(--text-xs);
  line-height: var(--leading-body);
  color: var(--ink-0);
  word-break: break-word;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.dialogue-mark {
  background: color-mix(in oklab, var(--accent) 22%, transparent);
  color: var(--accent-strong);
  font-weight: 600;
  padding: 0 2px;
  border-radius: 2px;
}

.item-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-caption);
  color: var(--ink-2);
  font-family: var(--font-mono);
}

/* 命中数是本行唯一的新增信号，提到朱砂色；不加底色，避免与 .page-tag 抢层级 */
.meta-hit {
  color: var(--accent-strong);
  font-weight: 600;
}

.item-action {
  flex-shrink: 0;
  color: var(--ink-2);
  opacity: 0.6;
  transition:
    transform var(--duration-2) var(--ease-out),
    opacity var(--duration-2) var(--ease-out),
    color var(--duration-2) var(--ease-out);
}

.result-item:hover .item-action,
.result-item.is-focused .item-action {
  opacity: 1;
  color: var(--accent);
  transform: translateX(2px);
}

/* 空状态 */
.popover-empty {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-3);
  color: var(--ink-2);
}

.empty-icon {
  color: var(--ink-2);
  flex-shrink: 0;
}

.empty-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.empty-title {
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--ink-1);
  margin: 0;
}

.empty-hint {
  font-size: var(--text-caption);
  color: var(--ink-2);
  margin: 0;
}

/* 底部 */
.popover-footer {
  padding: var(--space-1-5) var(--space-3);
  background: var(--paper-1);
  border-top: 1px solid var(--line);
  font-size: var(--text-caption);
  color: var(--ink-2);
}

/* 过渡动效 */
.popover-fade-enter-active,
.popover-fade-leave-active {
  transition:
    opacity var(--duration-2) var(--ease-out),
    transform var(--duration-2) var(--ease-out);
}

.popover-fade-enter-from,
.popover-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (max-width: 681px) {
  .dialogue-popover {
    max-width: 100%;
  }

  .results-list {
    max-height: min(16rem, 38dvh);
  }
}
</style>
