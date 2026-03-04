import { ref, computed, watch } from 'vue'
import { useUrlSearchParams, useIntervalFn } from '@vueuse/core'
import { fetchRealtime, fetchAnalysis } from '../api'
import type { AnalysisResult, RealtimeQuote } from '../types'

const params = useUrlSearchParams('history')

export function useForex() {
  const baseCurrency = ref((params.base as string) || 'USD')
  const targetCurrency = ref((params.target as string) || 'JPY')
  const historyDays = ref(Number(params.hdays) || 90)
  const forecastDays = ref(Number(params.fdays) || 30)

  const analysisResult = ref<AnalysisResult | null>(null)
  const realtimeQuote = ref<RealtimeQuote | null>(null)
  const loading = ref(false)
  const realtimeLoading = ref(false)
  const error = ref('')
  const lastRunAt = ref('')

  const pairLabel = computed(() => `${baseCurrency.value}/${targetCurrency.value}`)

  watch([baseCurrency, targetCurrency, historyDays, forecastDays], () => {
    params.base = baseCurrency.value
    params.target = targetCurrency.value
    params.hdays = String(historyDays.value)
    params.fdays = String(forecastDays.value)
  })

  // 货币对变更时立即刷新实时汇率
  watch([baseCurrency, targetCurrency], () => {
    loadRealtime()
  })

  async function loadRealtime() {
    realtimeLoading.value = true
    try {
      realtimeQuote.value = await fetchRealtime(baseCurrency.value, targetCurrency.value)
    } catch {
      // 静默失败，不影响主流程
    } finally {
      realtimeLoading.value = false
    }
  }

  async function runAnalysis() {
    loading.value = true
    error.value = ''
    try {
      const result = await fetchAnalysis(
        baseCurrency.value,
        targetCurrency.value,
        historyDays.value,
        forecastDays.value,
      )
      analysisResult.value = result
      lastRunAt.value = new Date().toISOString()
      if (result.realtime?.rate) {
        realtimeQuote.value = result.realtime
      }
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  // 自动定时刷新实时汇率（60 分钟）
  useIntervalFn(loadRealtime, 3600_000)

  return {
    baseCurrency,
    targetCurrency,
    historyDays,
    forecastDays,
    analysisResult,
    realtimeQuote,
    loading,
    realtimeLoading,
    error,
    lastRunAt,
    pairLabel,
    loadRealtime,
    runAnalysis,
  }
}
