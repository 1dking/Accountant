import { api } from './client'
import type { ApiResponse } from '@/types/api'
import type { ProfitLossReport, TaxSummary, CashFlowReport, AccountsSummary } from '@/types/models'

export async function getProfitLoss(dateFrom: string, dateTo: string) {
  return api.get<ApiResponse<ProfitLossReport>>(`/reports/profit-loss?date_from=${dateFrom}&date_to=${dateTo}`)
}

export async function getTaxSummary(year: number) {
  return api.get<ApiResponse<TaxSummary>>(`/reports/tax-summary?year=${year}`)
}

export async function getCashFlow(dateFrom: string, dateTo: string) {
  return api.get<ApiResponse<CashFlowReport>>(`/reports/cash-flow?date_from=${dateFrom}&date_to=${dateTo}`)
}

export async function getAccountsSummary() {
  return api.get<ApiResponse<AccountsSummary>>('/reports/accounts-summary')
}

export function getProfitLossPdfUrl(dateFrom: string, dateTo: string) {
  return `/api/reports/profit-loss/pdf?date_from=${dateFrom}&date_to=${dateTo}`
}

export function getTaxSummaryPdfUrl(year: number) {
  return `/api/reports/tax-summary/pdf?year=${year}`
}
