const BASE_URL = '/api'

interface ApiError {
  code: string
  message: string
  details: unknown
}

export class ApiClientError extends Error {
  status: number
  error: ApiError
  constructor(status: number, error: ApiError) {
    super(error.message)
    this.name = 'ApiClientError'
    this.status = status
    this.error = error
  }
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  const token = localStorage.getItem('access_token')
  if (!token) return {}
  return { Authorization: `Bearer ${token}` }
}

async function tryRefreshToken(): Promise<boolean> {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) return false
  try {
    const refreshResponse = await fetch(`${BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (refreshResponse.ok) {
      const { data } = await refreshResponse.json()
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      return true
    }
  } catch {
    // Refresh failed
  }
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  window.location.href = '/login'
  return false
}

async function handleResponse<T>(response: Response, retryFn?: () => Promise<Response>): Promise<T> {
  if (response.status === 401 && retryFn) {
    const refreshed = await tryRefreshToken()
    if (refreshed) {
      const retryResponse = await retryFn()
      return handleResponse<T>(retryResponse)
    }
  }

  if (response.status === 401) {
    window.location.href = '/login'
  }

  let body: any
  try {
    body = await response.json()
  } catch {
    throw new ApiClientError(response.status, { code: 'UNKNOWN', message: `Server error (${response.status})`, details: null })
  }

  if (!response.ok) {
    throw new ApiClientError(response.status, body.error || { code: 'UNKNOWN', message: 'Request failed', details: null })
  }

  return body
}

export const api = {
  async get<T = unknown>(path: string): Promise<T> {
    const doFetch = async () => {
      const headers = await getAuthHeaders()
      return fetch(`${BASE_URL}${path}`, { headers })
    }
    const response = await doFetch()
    return handleResponse<T>(response, doFetch)
  },

  async post<T = unknown>(path: string, body?: unknown): Promise<T> {
    const doFetch = async () => {
      const headers = await getAuthHeaders()
      return fetch(`${BASE_URL}${path}`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      })
    }
    const response = await doFetch()
    return handleResponse<T>(response, doFetch)
  },

  async put<T = unknown>(path: string, body?: unknown): Promise<T> {
    const doFetch = async () => {
      const headers = await getAuthHeaders()
      return fetch(`${BASE_URL}${path}`, {
        method: 'PUT',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      })
    }
    const response = await doFetch()
    return handleResponse<T>(response, doFetch)
  },

  async delete<T = unknown>(path: string): Promise<T> {
    const doFetch = async () => {
      const headers = await getAuthHeaders()
      return fetch(`${BASE_URL}${path}`, {
        method: 'DELETE',
        headers: await getAuthHeaders(),
      })
    }
    const response = await doFetch()
    return handleResponse<T>(response, doFetch)
  },

  async upload<T = unknown>(path: string, formData: FormData): Promise<T> {
    const doFetch = async () => {
      const headers = await getAuthHeaders()
      return fetch(`${BASE_URL}${path}`, {
        method: 'POST',
        headers,
        body: formData,
      })
    }
    const response = await doFetch()
    return handleResponse<T>(response, doFetch)
  },
}
