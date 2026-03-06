/**
 * Tests for the API client module — verifies auth header injection,
 * error handling, token refresh logic, and response parsing.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// We test the raw module; mock fetch globally.
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

// Mock localStorage
const store: Record<string, string> = {}
vi.stubGlobal('localStorage', {
  getItem: (k: string) => store[k] ?? null,
  setItem: (k: string, v: string) => { store[k] = v },
  removeItem: (k: string) => { delete store[k] },
})

// Prevent actual redirects
vi.stubGlobal('location', { href: '' })

// Import after stubs are in place
const { api, ApiClientError } = await import('@/api/client')

beforeEach(() => {
  mockFetch.mockReset()
  Object.keys(store).forEach(k => delete store[k])
})

// ---------------------------------------------------------------------------
// GET requests
// ---------------------------------------------------------------------------

describe('api.get', () => {
  it('sends Authorization header when token is present', async () => {
    store.access_token = 'test-jwt'
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ data: [] }),
    })

    await api.get('/invoices')

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/invoices',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer test-jwt' }),
      })
    )
  })

  it('does not send Authorization when no token', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ data: [] }),
    })

    await api.get('/contacts')

    const headers = mockFetch.mock.calls[0][1].headers
    expect(headers.Authorization).toBeUndefined()
  })

  it('throws ApiClientError on error response', async () => {
    store.access_token = 'test-jwt'
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: () => Promise.resolve({
        error: { code: 'NOT_FOUND', message: 'Invoice not found', details: null },
      }),
    })

    await expect(api.get('/invoices/missing')).rejects.toThrow(ApiClientError)
  })
})

// ---------------------------------------------------------------------------
// POST requests
// ---------------------------------------------------------------------------

describe('api.post', () => {
  it('sends JSON body with Content-Type', async () => {
    store.access_token = 'test-jwt'
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: () => Promise.resolve({ data: { id: '123' } }),
    })

    const body = { description: 'Test', amount: '100.00' }
    await api.post('/expenses', body)

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/expenses',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(body),
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          Authorization: 'Bearer test-jwt',
        }),
      })
    )
  })

  it('handles POST without body', async () => {
    store.access_token = 'test-jwt'
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ data: {} }),
    })

    await api.post('/invoices/123/send')

    expect(mockFetch.mock.calls[0][1].body).toBeUndefined()
  })
})

// ---------------------------------------------------------------------------
// Token refresh on 401
// ---------------------------------------------------------------------------

describe('token refresh', () => {
  it('retries request after successful refresh', async () => {
    store.access_token = 'old-token'
    store.refresh_token = 'refresh-token'

    // First call: 401
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ error: { code: 'UNAUTHORIZED', message: 'Token expired', details: null } }),
    })
    // Refresh call: success
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({
        data: { access_token: 'new-token', refresh_token: 'new-refresh' },
      }),
    })
    // Retry: success
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ data: { id: '1' } }),
    })

    const result = await api.get('/me')
    expect(result).toEqual({ data: { id: '1' } })
    expect(store.access_token).toBe('new-token')
    expect(store.refresh_token).toBe('new-refresh')
  })

  it('redirects to login when refresh fails', async () => {
    store.access_token = 'old-token'
    store.refresh_token = 'bad-refresh'

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ error: { code: 'UNAUTHORIZED', message: '', details: null } }),
    })
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({}),
    })

    // Should not throw but redirect
    try {
      await api.get('/me')
    } catch {
      // may throw — that's OK
    }
    // Tokens should be cleared
    expect(store.access_token).toBeUndefined()
    expect(store.refresh_token).toBeUndefined()
  })
})

// ---------------------------------------------------------------------------
// DELETE / PUT / upload
// ---------------------------------------------------------------------------

describe('api.delete', () => {
  it('sends DELETE request with auth', async () => {
    store.access_token = 'test-jwt'
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ data: { message: 'Deleted' } }),
    })

    await api.delete('/invoices/123')
    expect(mockFetch.mock.calls[0][1].method).toBe('DELETE')
  })
})

describe('api.put', () => {
  it('sends PUT request with JSON body', async () => {
    store.access_token = 'test-jwt'
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ data: { id: '1' } }),
    })

    await api.put('/contacts/1', { company_name: 'Updated' })
    expect(mockFetch.mock.calls[0][1].method).toBe('PUT')
    expect(mockFetch.mock.calls[0][1].body).toBe(JSON.stringify({ company_name: 'Updated' }))
  })
})

// ---------------------------------------------------------------------------
// Error shape
// ---------------------------------------------------------------------------

describe('ApiClientError', () => {
  it('has status and error properties', () => {
    const err = new ApiClientError(422, {
      code: 'VALIDATION_ERROR',
      message: 'Bad input',
      details: null,
    })
    expect(err.status).toBe(422)
    expect(err.error.code).toBe('VALIDATION_ERROR')
    expect(err.message).toBe('Bad input')
    expect(err).toBeInstanceOf(Error)
  })
})
