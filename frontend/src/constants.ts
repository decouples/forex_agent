import type { CurrencyOption } from './types'

export const CURRENCY_NAME_MAP: Record<string, string> = {
  USD: '美元', EUR: '欧元', GBP: '英镑', JPY: '日元', CHF: '瑞士法郎',
  CNY: '人民币', HKD: '港元', AUD: '澳元', CAD: '加元', SGD: '新加坡元',
  KRW: '韩元', NZD: '新西兰元', SEK: '瑞典克朗', NOK: '挪威克朗', DKK: '丹麦克朗',
  PLN: '波兰兹罗提', CZK: '捷克克朗', HUF: '匈牙利福林', RON: '罗马尼亚列伊', BGN: '保加利亚列弗',
  TRY: '土耳其里拉', RUB: '俄罗斯卢布', INR: '印度卢比', IDR: '印尼盾', THB: '泰铢',
  MYR: '马来西亚林吉特', PHP: '菲律宾比索', VND: '越南盾', ZAR: '南非兰特', BRL: '巴西雷亚尔',
  MXN: '墨西哥比索', ARS: '阿根廷比索', CLP: '智利比索', COP: '哥伦比亚比索', PEN: '秘鲁索尔',
  AED: '阿联酋迪拉姆', SAR: '沙特里亚尔', ILS: '以色列新谢克尔', EGP: '埃及镑', QAR: '卡塔尔里亚尔',
}

export const MAJOR_CURRENCIES: string[] = [
  'USD', 'EUR', 'GBP', 'JPY', 'CHF',
  'CNY', 'HKD', 'AUD', 'CAD', 'SGD',
  'KRW', 'NZD', 'SEK', 'NOK', 'DKK',
  'PLN', 'CZK', 'HUF', 'RON', 'BGN',
  'TRY', 'RUB', 'INR', 'IDR', 'THB',
  'MYR', 'PHP', 'VND', 'ZAR', 'BRL',
  'MXN', 'ARS', 'CLP', 'COP', 'PEN',
  'AED', 'SAR', 'ILS', 'EGP', 'QAR',
]

export const CURRENCY_OPTIONS: CurrencyOption[] = MAJOR_CURRENCIES.map(code => ({
  code,
  name: CURRENCY_NAME_MAP[code] ?? code,
}))
