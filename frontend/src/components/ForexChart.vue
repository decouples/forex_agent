<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, DataZoomComponent, MarkLineComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { AnalysisResult } from '../types'

use([
  LineChart, TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, DataZoomComponent, MarkLineComponent, CanvasRenderer,
])

const props = defineProps<{
  data: AnalysisResult
  loading: boolean
}>()

const chartRef = ref()

const option = computed(() => {
  const r = props.data
  const hist = r.history_records ?? []
  const forecast = r.forecast?.predicted_rates ?? []
  const base = r.request.base_currency
  const target = r.request.target_currency

  const histDates = hist.map(h => h.date)
  const histRates = hist.map(h => h.rate)

  // MA 计算
  const ma7 = histRates.map((_, i) => {
    if (i < 6) return null
    const slice = histRates.slice(i - 6, i + 1)
    return slice.reduce((a, b) => a + b, 0) / slice.length
  })
  const ma30 = histRates.map((_, i) => {
    if (i < 29) return null
    const slice = histRates.slice(i - 29, i + 1)
    return slice.reduce((a, b) => a + b, 0) / slice.length
  })

  // 预测日期
  const lastDate = hist.length ? new Date(hist[hist.length - 1].date) : new Date()
  const forecastDates: string[] = []
  for (let i = 1; i <= forecast.length; i++) {
    const d = new Date(lastDate)
    d.setDate(d.getDate() + i)
    forecastDates.push(d.toISOString().slice(0, 10))
  }

  const allDates = [...histDates, ...forecastDates]

  // 预测线：从最后一个真实点接出
  const predLine: (number | null)[] = new Array(histRates.length).fill(null)
  if (histRates.length > 0) {
    predLine[predLine.length - 1] = histRates[histRates.length - 1]
  }
  predLine.push(...forecast)

  return {
    backgroundColor: 'transparent',
    title: {
      text: `${base}/${target} 汇率走势与预测`,
      left: 'center',
      top: 8,
      textStyle: { color: '#e8ecf4', fontSize: 16, fontWeight: 600 },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(26,34,54,0.95)',
      borderColor: '#2a3550',
      textStyle: { color: '#e8ecf4', fontSize: 12 },
      axisPointer: { type: 'cross', crossStyle: { color: '#3b82f6' } },
    },
    legend: {
      bottom: 8,
      textStyle: { color: '#8b95a8', fontSize: 12 },
      itemGap: 20,
    },
    grid: { left: 60, right: 40, top: 50, bottom: 80 },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      {
        type: 'slider', bottom: 36, height: 20,
        borderColor: '#2a3550', fillerColor: 'rgba(59,130,246,0.15)',
        handleStyle: { color: '#3b82f6' },
        textStyle: { color: '#8b95a8' },
      },
    ],
    xAxis: {
      type: 'category',
      data: allDates,
      axisLabel: {
        color: '#8b95a8', fontSize: 11, rotate: 30,
        formatter: (v: string) => {
          const d = new Date(v)
          return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
        },
      },
      axisLine: { lineStyle: { color: '#2a3550' } },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: { color: '#8b95a8', fontSize: 11, formatter: (v: number) => v.toFixed(4) },
      axisLine: { lineStyle: { color: '#2a3550' } },
      splitLine: { lineStyle: { color: '#1a2236', type: 'dashed' } },
    },
    series: [
      {
        name: '历史汇率',
        type: 'line',
        data: [...histRates, ...new Array(forecastDates.length).fill(null)],
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#3b82f6', width: 2 },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(59,130,246,0.25)' },
              { offset: 1, color: 'rgba(59,130,246,0)' },
            ],
          },
        },
      },
      {
        name: 'MA7',
        type: 'line',
        data: [...ma7, ...new Array(forecastDates.length).fill(null)],
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#f59e0b', width: 1, type: 'dotted' },
      },
      {
        name: 'MA30',
        type: 'line',
        data: [...ma30, ...new Array(forecastDates.length).fill(null)],
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#10b981', width: 1, type: 'dotted' },
      },
      {
        name: '预测汇率',
        type: 'line',
        data: predLine,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#ef4444', width: 2, type: 'dashed' },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(239,68,68,0.15)' },
              { offset: 1, color: 'rgba(239,68,68,0)' },
            ],
          },
        },
      },
    ],
    animationDuration: 1200,
    animationEasing: 'cubicInOut' as const,
  }
})

watch(() => props.data, () => {
  chartRef.value?.resize?.()
})
</script>

<template>
  <div class="chart-container" :class="{ muted: loading }">
    <VChart ref="chartRef" :option="option" autoresize style="width:100%;height:420px" />
    <Transition name="fade">
      <div v-if="loading" class="loading-overlay">
        <div class="spinner" />
        <div class="loading-text">正在获取数据并分析...</div>
      </div>
    </Transition>
  </div>
</template>
