<script setup lang="ts">
import { CURRENCY_OPTIONS } from '../constants'

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
}>()

const emit = defineEmits<{
  'update:baseCurrency': [val: string]
  'update:targetCurrency': [val: string]
  'update:historyDays': [val: number]
  'update:forecastDays': [val: number]
  analyze: []
}>()

function filterCurrency(query: string, item: { value: string; label: string }) {
  const q = query.toLowerCase()
  return item.value.toLowerCase().includes(q) || item.label.toLowerCase().includes(q)
}
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="logo">
        <div class="logo-icon">💱</div>
        <h1>外汇智能体</h1>
      </div>
    </div>

    <div class="sidebar-body">
      <div class="param-section">
        <h3>参数设置</h3>
        <div class="param-group">
          <div class="param-item">
            <label>基准货币</label>
            <el-select
              :model-value="baseCurrency"
              filterable
              :filter-method="undefined"
              placeholder="选择基准货币"
              @update:model-value="emit('update:baseCurrency', $event)"
            >
              <el-option
                v-for="c in CURRENCY_OPTIONS"
                :key="c.code"
                :label="`${c.code} - ${c.name}`"
                :value="c.code"
              />
            </el-select>
          </div>

          <div class="param-item">
            <label>目标货币</label>
            <el-select
              :model-value="targetCurrency"
              filterable
              :filter-method="undefined"
              placeholder="选择目标货币"
              @update:model-value="emit('update:targetCurrency', $event)"
            >
              <el-option
                v-for="c in CURRENCY_OPTIONS"
                :key="c.code"
                :label="`${c.code} - ${c.name}`"
                :value="c.code"
              />
            </el-select>
          </div>

          <div class="param-item">
            <label>历史天数：{{ historyDays }} 天</label>
            <el-slider
              :model-value="historyDays"
              :min="30"
              :max="365"
              :step="5"
              @update:model-value="emit('update:historyDays', $event as number)"
            />
          </div>

          <div class="param-item">
            <label>预测天数：{{ forecastDays }} 天</label>
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
          分析中...
        </template>
        <template v-else>
          🔍 开始分析
        </template>
      </button>

      <div class="realtime-card">
        <div class="realtime-label">实时汇率 · {{ pairLabel }}</div>
        <Transition name="fade" mode="out-in">
          <div v-if="realtimeRate !== null" :key="realtimeRate" class="realtime-rate">
            {{ realtimeRate.toFixed(6) }}
          </div>
          <div v-else class="realtime-rate" style="opacity:0.3">
            --
          </div>
        </Transition>
        <div class="realtime-time">
          {{ realtimeDate || '等待数据...' }}
          <span v-if="realtimeLoading" style="margin-left:6px">🔄</span>
        </div>
      </div>
    </div>
  </aside>
</template>
