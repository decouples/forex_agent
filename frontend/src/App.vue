<script setup lang="ts">
import { onMounted, computed } from 'vue'
import SidebarPanel from './components/SidebarPanel.vue'
import StatsRow from './components/StatsRow.vue'
import ForexChart from './components/ForexChart.vue'
import ReportPanel from './components/ReportPanel.vue'
import TimingsBar from './components/TimingsBar.vue'
import { useForex } from './composables/useForex'

const {
  baseCurrency, targetCurrency, historyDays, forecastDays,
  analysisResult, realtimeQuote, loading, realtimeLoading,
  error, lastRunAt, pairLabel,
  loadRealtime, runAnalysis,
} = useForex()

const realtimeRate = computed(() => realtimeQuote.value?.rate ?? null)
const realtimeDate = computed(() => {
  if (!realtimeQuote.value) return ''
  return `${realtimeQuote.value.date} ${new Date().toLocaleTimeString('zh-CN')}`
})

onMounted(async () => {
  loadRealtime()
  runAnalysis()
})
</script>

<template>
  <div class="app-layout">
    <SidebarPanel
      v-model:base-currency="baseCurrency"
      v-model:target-currency="targetCurrency"
      v-model:history-days="historyDays"
      v-model:forecast-days="forecastDays"
      :loading="loading"
      :realtime-rate="realtimeRate"
      :realtime-date="realtimeDate"
      :realtime-loading="realtimeLoading"
      :pair-label="pairLabel"
      @analyze="runAnalysis"
    />

    <main class="main-area">
      <div class="main-header">
        <h2>{{ pairLabel }} 汇率分析</h2>
        <div class="header-meta">
          <span v-if="lastRunAt">
            上次分析: {{ new Date(lastRunAt).toLocaleString('zh-CN') }}
          </span>
          <span v-if="analysisResult?.forecast?.model_used">
            模型: {{ analysisResult.forecast.model_used }}
          </span>
        </div>
      </div>

      <div class="main-content">
        <Transition name="fade" mode="out-in">
          <div v-if="error && !analysisResult" key="error" class="empty-state">
            <div class="empty-icon">⚠️</div>
            <div class="empty-text">{{ error }}</div>
            <button class="analyze-btn" style="width:auto;padding:0 24px" @click="runAnalysis">
              重试
            </button>
          </div>

          <div v-else-if="!analysisResult && !loading" key="empty" class="empty-state">
            <div class="empty-icon">📊</div>
            <div class="empty-text">点击左侧「开始分析」查看汇率走势</div>
            <div class="empty-hint">支持 40 种主流货币 · 多数据源自动降级 · LLM 智能决策</div>
          </div>

          <div v-else key="content" style="display:contents">
            <Transition name="slide-up">
              <StatsRow v-if="analysisResult" :data="analysisResult" />
            </Transition>

            <ForexChart
              v-if="analysisResult"
              :data="analysisResult"
              :loading="loading"
            />

            <Transition name="slide-up">
              <div v-if="error" style="color:var(--accent-red);font-size:14px;padding:8px 0">
                ⚠️ {{ error }}
              </div>
            </Transition>

            <ReportPanel
              v-if="analysisResult"
              :report="analysisResult.report ?? ''"
              :loading="loading"
            />

            <TimingsBar
              v-if="analysisResult?.node_timings"
              :timings="analysisResult.node_timings"
            />
          </div>
        </Transition>

        <Transition name="fade">
          <div v-if="loading && !analysisResult" class="empty-state">
            <div class="spinner" />
            <div class="loading-text">正在连接分析服务...</div>
          </div>
        </Transition>

        <footer class="app-footer">
          <div class="footer-divider" />
          <div class="footer-content">
            <span>© {{ new Date().getFullYear() }} Lin Li. All Rights Reserved.</span>
            <span class="footer-sep">|</span>
            <span>Forex Intelligent Agent · Powered by LangGraph & Multi-LLM</span>
          </div>
        </footer>
      </div>
    </main>
  </div>
</template>
