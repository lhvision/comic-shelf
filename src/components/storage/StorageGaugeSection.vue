<script setup lang="ts">
/**
 * @file StorageGaugeSection.vue
 * @description 存储容量平直标尺与资产分项账单展示区组件。
 *
 * 核心功能：
 * - 3px 平直刻度槽进度指示器与使用百分比；
 * - 核心应用资产（代码/字体/底色） vs 漫画画页缓存分项账单；
 * - 安全边界说明注脚。
 */

import AppIcon from '@/components/AppIcon.vue'
import { MANGA_IMAGE_MAX_BUDGET } from '@/composables/useOfflineStorage'

defineProps<{
  /** 浏览器提供的总配额字节数（为 0 表示未知） */
  quota: number
  /** 格式化后的总配额字符串（如 "120.0 GB"） */
  quotaFormatted: string
  /** 已使用百分比数值（0 ~ 100） */
  percentage: number
  /** 漫画画页离线预算百分比数值（0 ~ 100） */
  budgetPercentage?: number
  /** 格式化后的应用核心资源占用大小 */
  coreAssetBytesFormatted: string
  /** 离线缓存的漫画画页总数 */
  mangaImageCount: number
  /** 格式化后的漫画画页占用大小 */
  mangaImageBytesFormatted: string
  /** 客户端运行环境状态 */
  environmentStatus?: 'ready' | 'insecure_http' | 'unsupported'
}>()
</script>

<template>
  <div>
    <!-- 存储容量平直标尺（基于漫画画页预算） -->
    <section class="storage-gauge" aria-label="漫画画页离线预算">
      <div class="gauge-meta">
        <span class="gauge-name">漫画离线缓存预算</span>
        <span class="gauge-value font-mono">
          <strong>{{ mangaImageCount }}</strong>
          <small>
            / {{ MANGA_IMAGE_MAX_BUDGET.toLocaleString() }} 张上限 ({{
              mangaImageBytesFormatted
            }})</small
          >
        </span>
      </div>

      <div
        class="storage-track"
        role="progressbar"
        :aria-valuenow="Math.round(budgetPercentage ?? percentage)"
        aria-valuemin="0"
        aria-valuemax="100"
        :aria-valuetext="`已占用 ${mangaImageCount} 张画页 (${mangaImageBytesFormatted})`"
        :aria-label="`漫画离线缓存已使用 ${Math.round(budgetPercentage ?? percentage)}%`"
      >
        <div
          class="storage-fill"
          :style="{
            transform: `scaleX(${Math.max((budgetPercentage ?? percentage) > 0 ? 0.015 : 0, Math.min(1, (budgetPercentage ?? percentage) / 100))})`,
          }"
        ></div>
      </div>
    </section>

    <!-- 分项账单细分清单 -->
    <ul class="storage-breakdown" role="list">
      <li class="breakdown-item">
        <div class="item-text">
          <span class="item-title">纸间核心资产</span>
          <small class="item-desc">App 外壳 · 脚本 · 字体（离线秒开）</small>
        </div>
        <span class="item-metric font-mono">{{ coreAssetBytesFormatted }}</span>
      </li>

      <li class="breakdown-item">
        <div class="item-text">
          <span class="item-title">漫画阅览缓存</span>
          <small class="item-desc">
            {{ mangaImageCount }} 张已读页面与封面 · 保留最新
            {{ MANGA_IMAGE_MAX_BUDGET.toLocaleString() }} 页面
          </small>
        </div>
        <span class="item-metric font-mono">{{ mangaImageBytesFormatted }}</span>
      </li>

      <li v-if="quota > 0" class="breakdown-item">
        <div class="item-text">
          <span class="item-title">设备物理总配额</span>
          <small class="item-desc">浏览器物理磁盘分配空间（总容量充裕）</small>
        </div>
        <span class="item-metric font-mono font-muted">{{ quotaFormatted }}</span>
      </li>
    </ul>

    <!-- 局域网 HTTP 模式提示 -->
    <div v-if="environmentStatus === 'insecure_http'" class="storage-notice font-mono">
      <AppIcon name="info" size="xs" :stroke-width="1.8" />
      <span>当前为局域网 HTTP 模式，离线持久化需在 HTTPS 域名下生效</span>
    </div>

    <!-- 安全边界提示 -->
    <div class="storage-boundary">
      <AppIcon name="info" size="xs" :stroke-width="1.8" />
      <p>仅释放本设备浏览器缓存，绝不影响服务器书库。</p>
    </div>
  </div>
</template>

<style scoped>
/* 存储刻度槽：3px 平直装订质感 */
.storage-gauge {
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
}

.gauge-meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  font-size: var(--text-xs);
}

.gauge-name {
  color: var(--ink-1);
}

.gauge-value strong {
  color: var(--ink-0);
  font-weight: 600;
}

.gauge-value small {
  color: var(--ink-2);
}

.storage-track {
  width: 100%;
  height: 6px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  overflow: hidden;
}

.storage-fill {
  height: 100%;
  width: 100%;
  background: var(--accent);
  border-radius: var(--radius-1);
  transform-origin: left;
  transition: transform var(--duration-2) var(--ease-out);
}

/* 分项清单 */
.storage-breakdown {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  padding: var(--space-2-5) 0;
  margin: var(--space-3-5) 0;
}

.breakdown-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-2);
}

.item-title {
  display: block;
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--ink-0);
  line-height: 1.2;
}

.item-desc {
  display: block;
  font-size: var(--text-caption);
  color: var(--ink-2);
  line-height: 1.3;
}

.item-metric {
  font-size: var(--text-xs);
  color: var(--ink-1);
  white-space: nowrap;
}

.storage-notice {
  display: flex;
  align-items: center;
  gap: var(--space-1-5);
  padding: var(--space-1-5) var(--space-2);
  margin-bottom: var(--space-2-5);
  background: color-mix(in oklab, var(--accent) 8%, var(--paper-1));
  border: 1px solid color-mix(in oklab, var(--accent) 25%, var(--line));
  border-radius: var(--radius-1);
  color: var(--ink-1);
  font-size: var(--text-caption);
  line-height: 1.4;
}

/* 安全边界提示 */
.storage-boundary {
  display: flex;
  align-items: center;
  gap: var(--space-1-5);
  color: var(--ink-2);
  font-size: var(--text-caption);
  line-height: 1.35;
}

.storage-boundary p {
  margin: 0;
}

@media (prefers-reduced-motion: reduce) {
  .storage-fill {
    transition: none !important;
  }
}
</style>
