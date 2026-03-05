<script setup lang="ts">
import { computed } from 'vue'
import type { Locale } from '../i18n'
import { useLocale } from '../composables/useLocale'

const props = defineProps<{ timings: Record<string, number>; locale: Locale }>()

const { t } = useLocale()

const items = computed(() => {
  const entries = Object.entries(props.timings).filter(([, v]) => typeof v === 'number' && v > 0)
  const maxVal = Math.max(...entries.map(([, v]) => v), 1)
  return entries.map(([name, val]) => ({
    name,
    value: val,
    pct: (val / maxVal) * 100,
    display: val >= 1 ? `${val.toFixed(1)}s` : `${(val * 1000).toFixed(0)}ms`,
  }))
})
</script>

<template>
  <div v-if="items.length" class="timings-section">
    <div class="timings-header">
      <span>⏱️</span>
      {{ t('timingsTitle') }}
    </div>
    <div class="timing-bar-list">
      <div v-for="ti in items" :key="ti.name" class="timing-item">
        <span class="timing-name">{{ ti.name }}</span>
        <div class="timing-bar-bg">
          <div class="timing-bar-fill" :style="{ width: ti.pct + '%' }" />
        </div>
        <span class="timing-value">{{ ti.display }}</span>
      </div>
    </div>
  </div>
</template>
