/**
 * ShareFileDialog — the real Drive "Share" action.
 *
 * The Drive context menu used to fire `toast.info('Share link copied (coming
 * soon)')`: it claimed a link had been copied to the clipboard, copied nothing,
 * and shared nothing. These tests pin the actual behaviour — that picking a
 * contact and confirming calls the file-share endpoint with the right payload.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ShareFileDialog from '@/components/documents/ShareFileDialog'

const shareFile = vi.fn(async () => ({ data: { id: 'share-1' } }))
const listContacts = vi.fn(async () => ({
  data: [
    {
      id: 'contact-1',
      type: 'client',
      company_name: 'Acme Co',
      contact_name: 'Dana Buyer',
      email: 'dana@acme.com',
      phone: null,
      city: null,
      state: null,
      is_active: true,
      assigned_user_id: null,
      created_at: '2026-01-01T00:00:00Z',
    },
  ],
}))

vi.mock('@/api/contacts', () => ({
  shareFile: (...args: unknown[]) => shareFile(...(args as [])),
  listContacts: (...args: unknown[]) => listContacts(...(args as [])),
}))

const toastSuccess = vi.fn()
const toastError = vi.fn()
vi.mock('sonner', () => ({
  toast: {
    success: (...a: unknown[]) => toastSuccess(...(a as [])),
    error: (...a: unknown[]) => toastError(...(a as [])),
  },
}))

function renderDialog(props: Partial<React.ComponentProps<typeof ShareFileDialog>> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const onClose = vi.fn()
  const utils = render(
    <QueryClientProvider client={qc}>
      <ShareFileDialog
        isOpen
        fileId="file-1"
        fileName="Q4-contract.pdf"
        onClose={onClose}
        {...props}
      />
    </QueryClientProvider>,
  )
  return { ...utils, onClose }
}

describe('ShareFileDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shares the file with the selected contact', async () => {
    const { onClose } = renderDialog()

    // Contact loaded from the API, not hardcoded.
    const contact = await screen.findByText('Dana Buyer')
    await userEvent.click(contact)

    await userEvent.click(screen.getByRole('button', { name: /^share$/i }))

    await waitFor(() => {
      expect(shareFile).toHaveBeenCalledTimes(1)
    })
    expect(shareFile).toHaveBeenCalledWith({
      file_id: 'file-1',
      contact_id: 'contact-1',
      permission: 'view',
    })
    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(toastSuccess).toHaveBeenCalled()
  })

  it('sends the chosen permission level', async () => {
    renderDialog()

    await userEvent.click(await screen.findByText('Dana Buyer'))
    await userEvent.selectOptions(screen.getByRole('combobox'), 'download')
    await userEvent.click(screen.getByRole('button', { name: /^share$/i }))

    await waitFor(() => {
      expect(shareFile).toHaveBeenCalledWith(
        expect.objectContaining({ permission: 'download' }),
      )
    })
  })

  it('cannot share until a contact is picked', async () => {
    renderDialog()
    await screen.findByText('Dana Buyer')

    const shareButton = screen.getByRole('button', { name: /^share$/i })
    expect(shareButton).toBeDisabled()

    await userEvent.click(shareButton)
    expect(shareFile).not.toHaveBeenCalled()
  })

  it('surfaces a failure instead of silently closing', async () => {
    shareFile.mockRejectedValueOnce(new Error('contact has no portal account'))
    const { onClose } = renderDialog()

    await userEvent.click(await screen.findByText('Dana Buyer'))
    await userEvent.click(screen.getByRole('button', { name: /^share$/i }))

    await waitFor(() => {
      expect(toastError).toHaveBeenCalledWith(
        expect.stringContaining('contact has no portal account'),
      )
    })
    // Dialog stays open so the user can retry or pick someone else.
    expect(onClose).not.toHaveBeenCalled()
  })

  it('renders nothing when there is no file', () => {
    const { container } = renderDialog({ fileId: null })
    expect(container).toBeEmptyDOMElement()
  })
})
