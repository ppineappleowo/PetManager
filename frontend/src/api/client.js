import { auth, clearAuth } from '../composables/useAuth.js'
import {clearListCache} from '../utils/listCache.js'

export const baseUrl = (window.APP_CONFIG?.apiBaseUrl ?? 'http://127.0.0.1:8001').replace(/\/+$/, '')

export async function apiFetch(path, { authenticated = true, ...options } = {}) {
  const headers = new Headers(options.headers)
  const requestToken = auth.token
  if (authenticated && auth.token) headers.set('Authorization', `Bearer ${auth.token}`)
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const response = await fetch(baseUrl + path, { ...options, headers })
  if (response.status === 401 && authenticated && auth.token === requestToken) clearAuth()
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item) => item.msg).join('；')
      : data.detail
    const error = new Error(detail || `请求失败 (${response.status})`)
    error.status = response.status
    error.retryAfter = Number(response.headers.get('Retry-After') || 0)
    error.fields = Array.isArray(data.detail)
      ? Object.fromEntries(data.detail.map((item) => [item.loc?.at(-1), item.msg.replace(/^Value error, /, '')]))
      : {}
    throw error
  }
  if(options.method && !['GET','HEAD'].includes(options.method.toUpperCase()))clearListCache()
  return response
}

export async function apiJson(path, options) {
  return (await apiFetch(path, options)).json()
}
