<script setup lang="ts">
import { CURRENCY_OPTIONS } from '../constants'
import { useLocale } from '../composables/useLocale'
import type { Locale } from '../i18n'

defineProps<{
  baseCurrency: string
  targetCurrency: string
  historyDays: number
  forecastDays: number
  loading: boolean
  realtimeRate: number | null
  realtimeDate: string
  realtimeLoading: boolean
  pairLabel: string
  locale: Locale
}>()

const emit = defineEmits<{
  'update:baseCurrency': [val: string]
  'update:targetCurrency': [val: string]
  'update:historyDays': [val: number]
  'update:forecastDays': [val: number]
  analyze: []
  toggleLocale: []
}>()

const { t, isEn, currencyLabel } = useLocale()
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="logo">
        <div class="logo-icon">💱</div>
        <h1>{{ t('appTitle') }}</h1>
      </div>
      <button class="locale-toggle" @click="emit('toggleLocale')" :title="isEn ? '切换中文' : 'Switch to English'">
        {{ isEn ? '中' : 'EN' }}
      </button>
    </div>

    <div class="sidebar-body">
      <div class="param-section">
        <!--- <h3>{{ t('paramSettings') }}</h3> --->
        <div class="param-group">
          <div class="param-item">
            <label>{{ t('baseCurrency') }}</label>
            <el-select
              :model-value="baseCurrency"
              filterable
              :filter-method="undefined"
              :placeholder="t('selectBaseCurrency')"
              @update:model-value="emit('update:baseCurrency', $event)"
            >
              <el-option
                v-for="c in CURRENCY_OPTIONS"
                :key="c.code"
                :label="currencyLabel(c.code)"
                :value="c.code"
              />
            </el-select>
          </div>

          <div class="param-item">
            <label>{{ t('targetCurrency') }}</label>
            <el-select
              :model-value="targetCurrency"
              filterable
              :filter-method="undefined"
              :placeholder="t('selectTargetCurrency')"
              @update:model-value="emit('update:targetCurrency', $event)"
            >
              <el-option
                v-for="c in CURRENCY_OPTIONS"
                :key="c.code"
                :label="currencyLabel(c.code)"
                :value="c.code"
              />
            </el-select>
          </div>

          <div class="param-item">
            <label>{{ t('historyDays') }}{{ isEn ? ': ' : '：' }}{{ historyDays }}{{ t('days') }}</label>
            <el-slider
              :model-value="historyDays"
              :min="30"
              :max="365"
              :step="5"
              @update:model-value="emit('update:historyDays', $event as number)"
            />
          </div>

          <div class="param-item">
            <label>{{ t('forecastDays') }}{{ isEn ? ': ' : '：' }}{{ forecastDays }}{{ t('days') }}</label>
            <el-slider
              :model-value="forecastDays"
              :min="7"
              :max="90"
              :step="1"
              @update:model-value="emit('update:forecastDays', $event as number)"
            />
          </div>
        </div>
      </div>

      <button
        class="analyze-btn"
        :disabled="loading"
        @click="emit('analyze')"
      >
        <template v-if="loading">
          <span class="spinner" style="width:18px;height:18px;border-width:2px" />
          {{ t('analyzing') }}
        </template>
        <template v-else>
          🔍 {{ t('analyze') }}
        </template>
      </button>

      <div class="realtime-card">
        <div class="realtime-label">{{ t('realtimeRate') }} · {{ pairLabel }}</div>
        <Transition name="fade" mode="out-in">
          <div v-if="realtimeRate !== null" :key="realtimeRate" class="realtime-rate">
            {{ realtimeRate.toFixed(6) }}
          </div>
          <div v-else class="realtime-rate" style="opacity:0.3">
            --
          </div>
        </Transition>
        <div class="realtime-time">
          {{ realtimeDate || t('waitingData') }}
          <span v-if="realtimeLoading" style="margin-left:6px">🔄</span>
        </div>
      </div>
    </div>
  </aside>
</template>
