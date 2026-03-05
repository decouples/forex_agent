<script setup lang="ts">
import { onMounted, computed, watch } from 'vue'
import SidebarPanel from './components/SidebarPanel.vue'
import StatsRow from './components/StatsRow.vue'
import ForexChart from './components/ForexChart.vue'
import ReportPanel from './components/ReportPanel.vue'
import TimingsBar from './components/TimingsBar.vue'
import { useForex } from './composables/useForex'
import { useLocale } from './composables/useLocale'

const {
  baseCurrency, targetCurrency, historyDays, forecastDays,
  analysisResult, realtimeQuote, loading, realtimeLoading,
  error, lastRunAt, pairLabel,
  loadRealtime, runAnalysis,
} = useForex()

const { t, locale, toggleLocale, isEn } = useLocale()

const realtimeRate = computed(() => realtimeQuote.value?.rate ?? null)
const realtimeDate = computed(() => {
  if (!realtimeQuote.value) return ''
  const localeStr = isEn.value ? 'en-US' : 'zh-CN'
  return `${realtimeQuote.value.date} ${new Date().toLocaleTimeString(localeStr)}`
})

const activeReport = computed(() => {
  if (!analysisResult.value) return ''
  return isEn.value
    ? (analysisResult.value.report_en || analysisResult.value.report)
    : analysisResult.value.report
})

// 动态更新页面标题和 HTML lang 属性
function updatePageTitle() {
  document.title = t('appTitle')
  document.documentElement.lang = isEn.value ? 'en' : 'zh-CN'
}

watch(locale, updatePageTitle, { immediate: true })

onMounted(async () => {
  updatePageTitle()
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
      :locale="locale"
      @analyze="runAnalysis"
      @toggle-locale="toggleLocale"
    />

    <main class="main-area">
      <div class="main-header">
        <h2>{{ pairLabel }} {{ t('rateAnalysis') }}</h2>
        <div class="header-meta">
          <span v-if="lastRunAt">
            {{ t('lastAnalysis') }}: {{ new Date(lastRunAt).toLocaleString(isEn ? 'en-US' : 'zh-CN') }}
          </span>
          <span v-if="analysisResult?.forecast?.model_used">
            {{ t('model') }}: {{ analysisResult.forecast.model_used }}
          </span>
        </div>
      </div>

      <div class="main-content">
        <Transition name="fade" mode="out-in">
          <div v-if="error && !analysisResult" key="error" class="empty-state">
            <div class="empty-icon">⚠️</div>
            <div class="empty-text">{{ error }}</div>
            <button class="analyze-btn" style="width:auto;padding:0 24px" @click="runAnalysis">
              {{ t('retry') }}
            </button>
          </div>

          <div v-else-if="!analysisResult && !loading" key="empty" class="empty-state">
            <div class="empty-icon">📊</div>
            <div class="empty-text">{{ t('emptyHint') }}</div>
            <div class="empty-hint">{{ t('emptySubHint') }}</div>
          </div>

          <div v-else key="content" style="display:contents">
            <Transition name="slide-up">
              <StatsRow v-if="analysisResult" :data="analysisResult" :locale="locale" />
            </Transition>

            <ForexChart
              v-if="analysisResult"
              :data="analysisResult"
              :loading="loading"
              :locale="locale"
            />

            <Transition name="slide-up">
              <div v-if="error" style="color:var(--accent-red);font-size:14px;padding:8px 0">
                ⚠️ {{ error }}
              </div>
            </Transition>

            <ReportPanel
              v-if="analysisResult"
              :report="activeReport"
              :loading="loading"
              :locale="locale"
            />

            <TimingsBar
              v-if="analysisResult?.node_timings"
              :timings="analysisResult.node_timings"
              :locale="locale"
            />
          </div>
        </Transition>

        <Transition name="fade">
          <div v-if="loading && !analysisResult" class="empty-state">
            <div class="spinner" />
            <div class="loading-text">{{ t('connecting') }}</div>
          </div>
        </Transition>

        <footer class="app-footer">
          <div class="footer-divider" />
          <div class="footer-content">
            <span>{{ t('copyright', { year: new Date().getFullYear() }) }}</span>
            <span class="footer-sep">|</span>
            <span>{{ t('poweredBy') }}</span>
          </div>
        </footer>
      </div>
    </main>
  </div>
</template>
