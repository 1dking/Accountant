import { api } from './client'
import type { ApiResponse } from '@/types/api'

export interface T2125Line {
  line: string
  label: string
  part: string
  amount: string
  allowable: string
  sources: { code: string; name: string; amount: string }[]
  computed: boolean
}

export interface T2125Statement {
  year: number
  period_start: string
  period_end: string
  fiscal_year_end_month: number
  gross_sales: string
  other_income: string
  gross_income: string
  cost_of_goods_sold: string
  gross_profit: string
  lines: T2125Line[]
  total_expenses: string
  net_income: string
  excluded_non_deductible: { code: string; name: string; amount: string }[]
  unmapped: { code: string; name: string; amount: string }[]
  gst_hst: null | {
    line_101_sales: string
    line_105_collected: string
    line_108_itc: string
    line_109_net_tax: string
    owes_cra: boolean
    has_recorded_tax: boolean
    provincial: { collected: string; paid: string; net: string }
  }
}

export interface T1Line {
  line: string
  label: string
  amount: string
  transaction_count: number
}

export interface T1Summary {
  year: number
  total_in: string
  total_out: string
  net_business_income_line_13500: string
  lines: T1Line[]
  uncategorized_out: string
}

export interface ReadinessItem {
  key: string
  status: 'ok' | 'warn' | 'todo' | 'info'
  label: string
  detail: string | null
  action_path: string | null
}

export interface FilingPackage {
  year: number
  business_name: string | null
  province: string | null
  business_number: string | null
  gst_hst_number: string | null
  generated_at: string
  personal_included: boolean
  t2125: T2125Statement
  t1: T1Summary | null
  readiness: ReadinessItem[]
}

export function getFilingPackage(year: number) {
  return api.get<ApiResponse<FilingPackage>>(`/filing/package?year=${year}`)
}

export async function downloadFilingPdf(year: number) {
  const blob = await api.download(`/filing/package/pdf?year=${year}`)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `tax-filing-${year}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
