<script setup lang="ts">
import { computed, ref } from 'vue'
import { onClickOutside } from '@vueuse/core'
import Modal from '@/components/Modal.vue'
import AppButton from '@/components/AppButton.vue'

/**
 * 详情页操作栏 —— 阅读/缓存/刷新 + 「更多」菜单（含危险移除）+ 缓存进度条。
 * 纯展示组件：需要父级配合的值由 props 传入，动作以 emit 上抛。
 *
 * 主次层级（票据 02）：只有「继续阅读」是主按钮；读页/缓存/刷新统一次级 btn-ghost。
 * 危险操作（Impeccable 重设计）：
 * - 「移除本地」不再摆在操作栏里，而是收进「更多 ⋯」菜单（本地缓存删了可惜，应弱化入口）；
 * - 点到后弹 Modal 做「二次确认」，且必须勾选「我已了解」才能点确认，防止误删。
 */
const props = withDefaults(
  defineProps<{
    /** 作品标题（用于危险确认文案） */
    title: string
    lastRead: number
    /** 「继续阅读」按钮文案；多章节时父级会带章节定位，缺省保持旧「第 N 页」文案。 */
    lastReadLabel?: string
    cachePercent: number
    caching: boolean
    cacheComplete: boolean
    cachedPages: number
    pageCount: number
    canWrite?: boolean
    source?: string
  }>(),
  { canWrite: true, source: 'jm' },
)

const emit = defineEmits<{
  startReading: [page?: number]
  cacheAll: []
  refreshMetadata: []
  removeComic: []
  editMetadata: []
  appendPages: []
}>()

/** 「更多」弹出菜单开合 */
const moreOpen = ref(false)
const moreRoot = ref<HTMLElement | null>(null)
/** 移除确认弹窗开合 */
const removeOpen = ref(false)
/** 二次确认勾选 */
const ackRemove = ref(false)

onClickOutside(moreRoot, () => {
  moreOpen.value = false
})

const removeBody = computed(
  () =>
    `《${props.title}》的本地页面与封面会被永久删除（共 ${props.cachedPages}/${props.pageCount} 页）。` +
    ' 删除后再次浏览需要重新访问远端并重新缓存，此操作不可撤销。',
)

function requestRemove() {
  moreOpen.value = false
  ackRemove.value = false
  removeOpen.value = true
}

function cancelRemove() {
  removeOpen.value = false
}

function confirmRemove() {
  removeOpen.value = false
  ackRemove.value = false
  emit('removeComic')
}

const cacheScale = computed(() => `scaleX(${props.cachePercent / 100})`)
</script>

<template>
  <div class="detail-actions">
    <div class="action-bar surface">
      <button class="btn btn-primary btn-read" type="button" @click="emit('startReading')">
        {{ lastReadLabel || (lastRead ? `继续阅读 · 第 ${lastRead} 页` : '开始阅读') }}
      </button>

      <button class="btn btn-ghost" type="button" @click="emit('startReading', 1)">
        从第 1 页开始
      </button>

      <button v-if="canWrite" class="btn btn-ghost" type="button" @click="emit('editMetadata')">
        编辑资料
      </button>

      <button
        v-if="canWrite && source === 'local'"
        class="btn btn-ghost"
        type="button"
        @click="emit('appendPages')"
      >
        增量追加…
      </button>

      <button
        v-if="canWrite && source !== 'local'"
        class="btn btn-ghost"
        type="button"
        :disabled="caching || cacheComplete"
        @click="emit('cacheAll')"
      >
        {{
          cacheComplete
            ? '已全部本地化'
            : caching
              ? `缓存中 ${cachePercent}%`
              : `缓存全部（已缓存 ${cachedPages}/${pageCount}）`
        }}
      </button>

      <button
        v-if="canWrite && source !== 'local'"
        class="btn btn-ghost"
        type="button"
        @click="emit('refreshMetadata')"
      >
        刷新资料
      </button>

      <div v-if="canWrite" ref="moreRoot" class="more-menu">
        <button
          class="btn btn-ghost more-trigger"
          type="button"
          :aria-expanded="moreOpen"
          :aria-haspopup="true"
          @click="moreOpen = !moreOpen"
        >
          ⋯ 更多
        </button>
        <div v-if="moreOpen" class="more-pop" role="menu">
          <button
            class="more-item danger-item"
            type="button"
            role="menuitem"
            @click="requestRemove"
          >
            移除本地缓存…
          </button>
        </div>
      </div>
    </div>

    <Modal :open="removeOpen" :title="`移除《${title}》？`" @cancel="cancelRemove">
      <p class="remove-copy">{{ removeBody }}</p>

      <label class="remove-ack">
        <input v-model="ackRemove" type="checkbox" />
        <span>我已了解：本地缓存会被永久删除，且无法撤销。</span>
      </label>

      <template #footer>
        <AppButton variant="ghost" size="md" type="button" @click="cancelRemove"> 取消 </AppButton>
        <AppButton
          variant="danger"
          size="md"
          type="button"
          :disabled="!ackRemove"
          @click="confirmRemove"
        >
          确认移除 {{ ackRemove ? '' : '（需勾选确认）' }}
        </AppButton>
      </template>
    </Modal>

    <div class="cache-summary" aria-hidden="true">
      <span />
    </div>
    <p class="cache-summary-text">
      本地缓存 {{ cachedPages }} / {{ pageCount }} 页（{{ cachePercent }}%）
    </p>
  </div>
</template>

<style scoped>
.detail-actions {
  margin-top: var(--space-5);
}

.action-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
}

.btn-read {
  min-width: 9rem;
  letter-spacing: 0.04em;
  box-shadow: var(--shadow-1);
}

.more-menu {
  position: relative;
  margin-left: auto;
}

.more-pop {
  position: absolute;
  top: calc(100% + var(--space-2));
  right: 0;
  z-index: 10;
  min-width: 10rem;
  padding: var(--space-1);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-2);
  background: var(--paper-0);
  box-shadow: var(--shadow-2);
}

.more-item {
  display: block;
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-1);
  text-align: left;
  font-size: var(--text-sm);
  color: var(--ink-1);
  background: transparent;
  border: 0;
}

.more-item:hover {
  background: var(--paper-1);
}

.danger-item {
  color: var(--accent-strong);
}

.danger-item:hover {
  background: var(--accent-soft);
}

.remove-copy {
  color: var(--ink-1);
}

.remove-ack {
  display: flex;
  gap: var(--space-2);
  align-items: flex-start;
  margin-top: var(--space-4);
  padding: var(--space-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--paper-1) 55%, transparent);
  font-size: var(--text-sm);
  line-height: 1.55;
}

.remove-ack input {
  margin-top: 0.25rem;
  accent-color: var(--accent);
}

.cache-summary {
  height: 4px;
  margin-top: var(--space-3);
  border-radius: 999px;
  background: var(--paper-2);
  overflow: hidden;
}

.cache-summary span {
  display: block;
  width: 100%;
  height: 100%;
  background: var(--accent);
  transform-origin: 0 50%;
  transform: v-bind(cacheScale);
  transition: transform var(--duration-3) var(--ease-out);
}

.cache-summary-text {
  margin-top: var(--space-1);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
  text-align: right;
}

@media (max-width: 681px) {
  .more-menu {
    margin-left: 0;
  }
}
</style>
