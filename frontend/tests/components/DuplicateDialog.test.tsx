/**
 * Confirm-duplicate dialog for Plaid categorization.
 *
 * When categorizing a Plaid transaction returns 409 PLAID_POSSIBLE_DUPLICATE,
 * the user must see the bank transaction next to the matching manual entry and
 * choose: Skip (same transaction, post nothing) or Add anyway (separate charge).
 * These tests pin that contract so a categorize can never silently double-post.
 */
import { describe, it, expect, vi } from 'vitest'
import type React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DuplicateDialog } from '@/pages/BankTransactionsPage'
import type { PlaidTransaction } from '@/types/models'

const getPlaidPossibleDuplicates = vi.fn(async () => ({
  data: {
    possible_duplicates: [
      { kind: 'expense', id: 'exp-1', amount: '50.00', date: '2026-03-15', description: 'Acme Coffee (manual)' },
    ],
  },
}))

// The dialog only touches this one helper; the rest of the module's imports
// resolve to undefined but are never called in these tests.
vi.mock('@/api/integrations', () => ({
  getPlaidPossibleDuplicates: (...a: unknown[]) => getPlaidPossibleDuplicates(...(a as [])),
}))

const txn = {
  id: 'txn-1',
  name: 'Acme Coffee',
  merchant_name: 'Acme Coffee',
  date: '2026-03-15',
  amount: 50,
  is_income: false,
  is_categorized: false,
} as unknown as PlaidTransaction

function renderDialog(over: Partial<React.ComponentProps<typeof DuplicateDialog>> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const onSkip = vi.fn()
  const onConfirm = vi.fn()
  render(
    <QueryClientProvider client={qc}>
      <DuplicateDialog txn={txn} asType="expense" onSkip={onSkip} onConfirm={onConfirm} confirming={false} {...over} />
    </QueryClientProvider>,
  )
  return { onSkip, onConfirm }
}

describe('DuplicateDialog', () => {
  it('shows the bank transaction next to the matching manual entry', async () => {
    renderDialog()
    expect(screen.getByText('Possible duplicate')).toBeInTheDocument()
    expect(screen.getAllByText('Acme Coffee').length).toBeGreaterThan(0) // the bank side
    await waitFor(() =>
      expect(screen.getByText('Acme Coffee (manual)')).toBeInTheDocument(), // fetched from the endpoint
    )
    expect(getPlaidPossibleDuplicates).toHaveBeenCalledWith('txn-1')
  })

  it('Skip posts nothing — calls onSkip, never onConfirm', async () => {
    const { onSkip, onConfirm } = renderDialog()
    await userEvent.click(screen.getByRole('button', { name: /skip/i }))
    expect(onSkip).toHaveBeenCalledTimes(1)
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('Add anyway posts — calls onConfirm', async () => {
    const { onConfirm } = renderDialog()
    await userEvent.click(screen.getByRole('button', { name: /add anyway/i }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })
})
