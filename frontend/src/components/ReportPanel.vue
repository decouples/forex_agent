<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import type { Locale } from '../i18n'
import { useLocale } from '../composables/useLocale'

const props = defineProps<{
  report: string
  loading: boolean
  locale: Locale
}>()

const { t } = useLocale()

const renderedHtml = computed(() => {
  if (!props.report) return ''
  return marked.parse(props.report) as string
})
</script>

<template>
  <Transition name="slide-up">
    <div v-if="report" class="report-section" :class="{ muted: loading }">
      <div class="report-header">
        <span style="font-size:20px">🤖</span>
        <h3>{{ t('reportTitle') }}</h3>
      </div>
      <div class="report-body" v-html="renderedHtml" />
    </div>
  </Transition>
</template>
