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

async function handleResponse<T>(response: Response): Promise<T> {
  if (response.status === 401) {
    // Try to refresh token
    const refreshToken = localStorage.getItem('refresh_token')
    if (refreshToken) {
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
          // Caller should retry the original request
        }
      } catch {
        // Refresh failed, clear tokens
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/login'
      }
    } else {
      window.location.href = '/login'
    }
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
    const headers = await getAuthHeaders()
    const response = await fetch(`${BASE_URL}${path}`, { headers })
    return handleResponse<T>(response)
  },

  async post<T = unknown>(path: string, body?: unknown): Promise<T> {
    const headers = await getAuthHeaders()
    const response = await fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    return handleResponse<T>(response)
  },

  async put<T = unknown>(path: string, body?: unknown): Promise<T> {
    const headers = await getAuthHeaders()
    const response = await fetch(`${BASE_URL}${path}`, {
      method: 'PUT',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    return handleResponse<T>(response)
  },

  async delete<T = unknown>(path: string): Promise<T> {
    const headers = await getAuthHeaders()
    const response = await fetch(`${BASE_URL}${path}`, {
      method: 'DELETE',
      headers,
    })
    return handleResponse<T>(response)
  },

  async upload<T = unknown>(path: string, formData: FormData): Promise<T> {
    const headers = await getAuthHeaders()
    const response = await fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      headers,
      body: formData,
    })
    return handleResponse<T>(response)
  },
}
