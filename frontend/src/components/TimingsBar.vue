<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ timings: Record<string, number> }>()

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
      节点耗时
    </div>
    <div class="timing-bar-list">
      <div v-for="t in items" :key="t.name" class="timing-item">
        <span class="timing-name">{{ t.name }}</span>
        <div class="timing-bar-bg">
          <div class="timing-bar-fill" :style="{ width: t.pct + '%' }" />
        </div>
        <span class="timing-value">{{ t.display }}</span>
      </div>
    </div>
  </div>
</template>
