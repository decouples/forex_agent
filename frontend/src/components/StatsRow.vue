<script setup lang="ts">
import { computed } from 'vue'
import type { AnalysisResult } from '../types'
import type { Locale } from '../i18n'
import { useLocale } from '../composables/useLocale'

const props = defineProps<{ data: AnalysisResult; locale: Locale }>()

const { t, currencyName } = useLocale()

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
      label: `${currencyName(base)} → ${currencyName(target)}`,
      value: current.toFixed(6),
      sub: t('currentRate'),
      color: 'var(--accent-cyan)',
    },
    {
      label: t('histHigh'),
      value: high.toFixed(6),
      sub: `${t('recent')} ${hist.length} ${t('days')}`,
      color: 'var(--accent-green)',
    },
    {
      label: t('histLow'),
      value: low.toFixed(6),
      sub: `${t('recent')} ${hist.length} ${t('days')}`,
      color: 'var(--accent-red)',
    },
    {
      label: t('histAvg'),
      value: avg.toFixed(6),
      sub: `${t('recent')} ${hist.length} ${t('days')}`,
      color: 'var(--accent-amber)',
    },
    {
      label: t('predModel'),
      value: r.forecast?.model_used ?? '-',
      sub: `${t('trend')}: ${r.forecast?.trend ?? '-'}`,
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
