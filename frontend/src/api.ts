import axios from 'axios'
import type { AnalysisResult, ApiResponse, RealtimeQuote } from './types'

const http = axios.create({ baseURL: '/', timeout: 120_000 })

export async function fetchRealtime(base: string, target: string): Promise<RealtimeQuote> {
  const { data } = await http.post<ApiResponse<RealtimeQuote>>('/v1/forex/realtime', {
    base_currency: base,
    target_currency: target,
    caller_agent: 'vue-ui',
    caller_task_id: `rt-${Date.now()}`,
  })
  if (!data.ok) throw new Error(data.error || '获取实时汇率失败')
  return data.data
}

export async function fetchAnalysis(
  base: string, target: string, historyDays: number, forecastDays: number,
): Promise<AnalysisResult> {
  const { data } = await http.post<ApiResponse<AnalysisResult>>('/v1/forex/analyze', {
    base_currency: base,
    target_currency: target,
    history_days: historyDays,
    forecast_days: forecastDays,
    caller_agent: 'vue-ui',
    caller_task_id: `ui-${Date.now()}`,
  })
  if (!data.ok) throw new Error(data.error || '分析失败')
  return data.data
}
