<script setup lang="ts">
import { computed } from 'vue'
import type { AnalysisResult } from '../types'
import { CURRENCY_NAME_MAP } from '../constants'

const props = defineProps<{ data: AnalysisResult }>()

const stats = computed(() => {
  const r = props.data
  const hist = r.history_records ?? []
  const rates = hist.map(h => h.rate)
  const high = rates.length ? Math.max(...rates) : 0
  const low = rates.length ? Math.min(...rates) : 0
  const avg = rates.length ? rates.reduce((a, b) => a + b, 0) / rates.length : 0
  const current = r.realtime?.rate ?? 0
  const base = r.request.base_currency
  const target = r.request.target_currency

  return [
    {
      label: `${CURRENCY_NAME_MAP[base] ?? base} → ${CURRENCY_NAME_MAP[target] ?? target}`,
      value: current.toFixed(6),
      sub: '当前汇率',
      color: 'var(--accent-cyan)',
    },
    {
      label: '历史最高',
      value: high.toFixed(6),
      sub: `近 ${hist.length} 天`,
      color: 'var(--accent-green)',
    },
    {
      label: '历史最低',
      value: low.toFixed(6),
      sub: `近 ${hist.length} 天`,
      color: 'var(--accent-red)',
    },
    {
      label: '历史均值',
      value: avg.toFixed(6),
      sub: `近 ${hist.length} 天`,
      color: 'var(--accent-amber)',
    },
    {
      label: '预测模型',
      value: r.forecast?.model_used ?? '-',
      sub: `趋势: ${r.forecast?.trend ?? '-'}`,
      color: 'var(--accent-purple)',
    },
  ]
})
</script>

<template>
  <TransitionGroup name="slide-up" tag="div" class="stats-row">
    <div v-for="(s, i) in stats" :key="i" class="stat-card">
      <div class="stat-label">
        <span :style="{ color: s.color }">●</span>
        {{ s.label }}
      </div>
      <div class="stat-value" :style="{ color: s.color }">{{ s.value }}</div>
      <div class="stat-sub">{{ s.sub }}</div>
    </div>
  </TransitionGroup>
</template>
