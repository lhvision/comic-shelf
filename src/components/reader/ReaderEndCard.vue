<script setup lang="ts">
/**
 * 阅读器结尾卡 —— "本子翻完了"，出现在横向 RTL 的开头屏或书末。
 * 纯展示：标题文案固定，返回动作通过 emit 交给父级导航。
 */
withDefaults(
  defineProps<{
    /** 横向模式下列为可吸附的整屏卡片 */
    snap?: boolean
  }>(),
  { snap: false },
)

defineEmits<{ back: [] }>()
</script>

<template>
  <div class="reader-end" :data-snap="snap">
    <p class="eyebrow">End of book</p>
    <h2>本子翻完了</h2>
    <button class="btn btn-primary" type="button" @click="$emit('back')">回到详情</button>
  </div>
</template>

<style scoped>
.reader-end {
  flex: 0 0 100%;
  min-width: 100%;
  min-height: 100dvh;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: var(--space-4);
  text-align: center;
  padding: var(--reader-chrome-h) var(--space-5);
}

.reader-end[data-snap='true'] {
  scroll-snap-align: start;
}

.reader-end h2 {
  font-size: var(--text-2xl);
}
</style>
