export interface RealtimeQuote {
  base: string
  target: string
  rate: number
  date: string
}

export interface HistoryRecord {
  date: string
  rate: number
}

export interface ForecastResult {
  predicted_rates: number[]
  model_used: string
  trend: string
}

export interface AnalysisResult {
  request: {
    base_currency: string
    target_currency: string
    history_days: number
    forecast_days: number
  }
  realtime: RealtimeQuote
  history_records: HistoryRecord[]
  analysis: Record<string, unknown>
  forecast: ForecastResult
  report: string
  report_en: string
  node_timings: Record<string, number>
}

export interface ApiResponse<T = Record<string, unknown>> {
  ok: boolean
  trace_id: string
  data: T
  error: string
}

export interface CurrencyOption {
  code: string
  name: string
}
