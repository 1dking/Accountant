import { api } from './client'
import type { ApiResponse, ApiListResponse } from '@/types/api'
import type {
  MatchResponse,
  ReconciliationSummary,
  Expense,
  CashbookEntry,
} from '@/types/models'

export async function findMatches(dateFrom?: string, dateTo?: string) {
  return api.post<ApiResponse<MatchResponse[]>>('/reconciliation/find-matches', {
    date_from: dateFrom || null,
    date_to: dateTo || null,
  })
}

export async function listMatches(
  status?: string,
  page = 1,
  pageSize = 50,
) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (status) params.set('status', status)
  return api.get<ApiListResponse<MatchResponse>>(`/reconciliation/matches?${params}`)
}

export async function confirmMatch(matchId: string) {
  return api.post<ApiResponse<MatchResponse>>(`/reconciliation/matches/${matchId}/confirm`)
}

export async function rejectMatch(matchId: string) {
  return api.post<ApiResponse<MatchResponse>>(`/reconciliation/matches/${matchId}/reject`)
}

export async function createManualMatch(receiptId: string, transactionId: string) {
  return api.post<ApiResponse<MatchResponse>>('/reconciliation/manual-match', {
    receipt_id: receiptId,
    transaction_id: transactionId,
  })
}

export async function getUnmatchedReceipts(page = 1, pageSize = 50) {
  return api.get<ApiListResponse<Expense>>(
    `/reconciliation/unmatched-receipts?page=${page}&page_size=${pageSize}`,
  )
}

export async function getUnmatchedTransactions(page = 1, pageSize = 50) {
  return api.get<ApiListResponse<CashbookEntry>>(
    `/reconciliation/unmatched-transactions?page=${page}&page_size=${pageSize}`,
  )
}

export async function getReconciliationSummary() {
  return api.get<ApiResponse<ReconciliationSummary>>('/reconciliation/summary')
}
