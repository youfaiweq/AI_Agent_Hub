import axios from 'axios'

export const AUTH_TOKEN_KEY = 'agenthub.access_token'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '',
  timeout: 5000,
  headers: {
    Accept: 'application/json',
  },
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem(AUTH_TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'object' && detail !== null && 'message' in detail) {
      return String(detail.message)
    }
    if (typeof detail === 'string') {
      return detail
    }
  }
  return fallback
}

export default http
