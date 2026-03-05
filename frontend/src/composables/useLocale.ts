import { ref, computed } from 'vue'
import { useUrlSearchParams } from '@vueuse/core'
import { messages, CURRENCY_NAME_EN, type Locale } from '../i18n'
import { CURRENCY_NAME_MAP } from '../constants'

const params = useUrlSearchParams('history')
const locale = ref<Locale>((params.lang as Locale) === 'en' ? 'en' : 'zh')

export function useLocale() {
  function t(key: string, vars?: Record<string, string | number>): string {
    let text = messages[locale.value]?.[key] ?? messages.zh[key] ?? key
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        text = text.replace(`{${k}}`, String(v))
      }
    }
    return text
  }

  function toggleLocale() {
    locale.value = locale.value === 'zh' ? 'en' : 'zh'
    params.lang = locale.value
  }

  const isEn = computed(() => locale.value === 'en')

  function currencyName(code: string): string {
    return locale.value === 'en'
      ? (CURRENCY_NAME_EN[code] ?? code)
      : (CURRENCY_NAME_MAP[code] ?? code)
  }

  function currencyLabel(code: string): string {
    return `${code} - ${currencyName(code)}`
  }

  function formatDate(dateStr: string): string {
    if (!dateStr) return ''
    const d = new Date(dateStr)
    if (locale.value === 'en') {
      return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
    }
    return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
  }

  return { locale, t, toggleLocale, isEn, currencyName, currencyLabel, formatDate }
}
