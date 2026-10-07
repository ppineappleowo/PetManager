import { watch } from 'vue'
import { auth } from './useAuth.js'
import { apiJson } from '../api/client.js'

let pending = null
let generation = 0
watch(() => auth.token, () => { generation++; pending = null }, { flush: 'sync' })

// Share concurrent checks, but revalidate on later navigation (roles can change).
export function loadCurrentUser() {
  if (!auth.token) return Promise.resolve(null)
  if (pending) return pending
  const current = generation
  pending = apiJson('/api/v1/auth/me').then(user => {
    if (current !== generation) throw new Error('登录状态已变化，请重新加载')
    return user
  }).finally(() => { if (current === generation) pending = null })
  return pending
}
