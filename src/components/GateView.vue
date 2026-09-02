<script setup lang="ts">
/**
 * @file GateView.vue
 * @description 纸间 · 全屏零残留门禁大门组件（Zero-DOM Gate View）。
 *
 * 核心架构：
 * 1. 作为 App.vue 的根级 v-else 视图，未通过验证前整个 App 骨架（顶栏、书架、阅读器）物理级 0 DOM 挂载；
 * 2. 编排门禁三态表单（GateSecretForm ➔ GateClaimForm ➔ GatePinForm）；
 * 3. 挂载 MutationObserver 哨兵，免疫 DevTools 控制台篡改 display: none / 删除节点。
 */

import { onMounted, onUnmounted, ref } from 'vue'
import { useAuth } from '@/composables/useAuth'
import { useBrandIcon } from '@/composables/useBrandIcon'
import AmbientWatermark from '@/components/AmbientWatermark.vue'
import GateSecretForm from '@/components/gate/GateSecretForm.vue'
import GateClaimForm from '@/components/gate/GateClaimForm.vue'
import GatePinForm from '@/components/gate/GatePinForm.vue'

const { requiresClaim, requiresPin, username } = useAuth()
const { brandIcon } = useBrandIcon()

const gateCardRef = ref<HTMLElement | null>(null)
let tamperObserver: MutationObserver | null = null

onMounted(() => {
  // 🛡️ Active Anti-Tamper Safeguard: Prevent DevTools from style-injecting display: none or hiding the gate
  if (typeof window !== 'undefined' && gateCardRef.value) {
    tamperObserver = new MutationObserver((mutations) => {
      for (const m of mutations) {
        if (
          m.type === 'attributes' &&
          (m.attributeName === 'style' ||
            m.attributeName === 'hidden' ||
            m.attributeName === 'class')
        ) {
          const target = m.target as HTMLElement
          if (target && target.style.display === 'none') {
            target.style.removeProperty('display')
          }
          if (target && target.hasAttribute('hidden')) {
            target.removeAttribute('hidden')
          }
        }
      }
    })
    tamperObserver.observe(gateCardRef.value, { attributes: true })
    if (gateCardRef.value.parentElement) {
      tamperObserver.observe(gateCardRef.value.parentElement, { attributes: true })
    }
  }
})

onUnmounted(() => {
  tamperObserver?.disconnect()
  tamperObserver = null
})
</script>

<template>
  <div class="gate-viewport" role="main" aria-labelledby="gate-title">
    <AmbientWatermark variant="page" />
    <div ref="gateCardRef" class="gate-card">
      <AmbientWatermark variant="modal" />

      <!-- Header Section -->
      <header class="gate-header">
        <div class="gate-brand-badge">
          <img class="brand-logo" :src="brandIcon" alt="" aria-hidden="true" />
        </div>
        <div class="gate-title-group">
          <div class="brand-eyebrow">
            <strong>纸间</strong>
            <span>Paper Room</span>
          </div>

          <template v-if="requiresClaim">
            <h1 id="gate-title" class="gate-title">认领借阅通行证</h1>
            <p class="gate-subtitle">首次使用借阅证，请自设 4~6 位数字 PIN 码确立所有权</p>
          </template>

          <template v-else-if="requiresPin">
            <h1 id="gate-title" class="gate-title">读者借书证验证</h1>
            <p class="gate-subtitle">
              已认领通行证（{{ username || '读者' }}），请输入您的个人 PIN 码
            </p>
          </template>

          <template v-else>
            <h1 id="gate-title" class="gate-title">阅览室通行门禁</h1>
            <p class="gate-subtitle">私人收藏受口令保护，请输入通行口令以进入</p>
          </template>
        </div>
      </header>

      <!-- Three-Phase Form Orchestration -->
      <GateClaimForm v-if="requiresClaim" />
      <GatePinForm v-else-if="requiresPin" />
      <GateSecretForm v-else />

      <!-- Footer -->
      <footer class="gate-footer">
        <span>防盗链与私有数据安全保护已就绪</span>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.gate-viewport {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: grid;
  place-items: center;
  padding: var(--space-4);
  background: var(--paper-0);
  min-height: 100dvh;
}

.gate-card {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  width: min(100%, 430px);
  background: var(--paper-1);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-3);
  padding: var(--space-6);
  box-shadow: var(--shadow-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  animation: gateReveal var(--duration-2) var(--ease-out);
}

.gate-header,
.gate-footer {
  position: relative;
  z-index: 1;
}

.gate-header {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.gate-brand-badge {
  width: 3.25rem;
  height: 3.25rem;
  border-radius: var(--radius-2);
  background: var(--paper-0);
  border: 1px solid var(--line-strong);
  display: grid;
  place-items: center;
  flex-shrink: 0;
  box-shadow: var(--shadow-1);
  overflow: hidden;
}

.brand-logo {
  width: 2.4rem;
  height: 2.4rem;
  object-fit: contain;
  border-radius: var(--radius-1);
}

.gate-title-group {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.brand-eyebrow {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-2);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.brand-eyebrow strong {
  font-family: var(--font-display);
  font-size: var(--text-xs);
  color: var(--accent);
  letter-spacing: 0.04em;
}

.gate-title {
  font-family: var(--font-display);
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--ink-0);
  margin: 0;
  letter-spacing: 0.02em;
}

.gate-subtitle {
  font-size: var(--text-xs);
  color: var(--ink-2);
  margin: 0;
  line-height: 1.4;
}

.gate-footer {
  padding-top: var(--space-3);
  border-top: 1px dashed var(--line);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-2);
  text-align: center;
}

@keyframes gateReveal {
  from {
    transform: scale(0.96);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .gate-card {
    animation: none;
  }
}
</style>
