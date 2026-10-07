import { reactive, watch, onMounted, onUnmounted } from 'vue'
import { auth } from './useAuth.js'
import { community } from '../api/community.js'

export const notificationState = reactive({ unread: 0, latestId: 0 })
let generation = 0, pending = null
watch(() => auth.token, () => {
  generation++; pending = null
  notificationState.unread = 0; notificationState.latestId = 0
}, { flush: 'sync' })

export function refreshNotifications(force = false) {
  if (!auth.token) return Promise.resolve()
  if (pending && !force) return pending
  const current = ++generation
  pending = community('/me/notifications/summary').then(data => {
    if (current === generation) {
      notificationState.unread = data.unread_count || 0
      notificationState.latestId = data.latest_id || 0
    }
  }).finally(() => { if (current === generation) pending = null })
  return pending
}

export function useNotificationPolling(route) {
  let timer, stopped = false, epoch = 0, delay = 30000
  const enabled = () => !!auth.token && document.visibilityState === 'visible' && !route.meta.admin
  async function tick(current) {
    if (stopped || current !== epoch || !enabled()) return
    try { await refreshNotifications(); delay = 30000 }
    catch { delay = Math.min(delay * 2, 300000) }
    if (!stopped && current === epoch && enabled()) timer = setTimeout(() => tick(current), delay)
  }
  function restart() { clearTimeout(timer); epoch++; delay = 30000; tick(epoch) }
  const stopWatch = watch(() => [auth.token, !!route.meta.admin], restart)
  onMounted(() => { document.addEventListener('visibilitychange', restart); restart() })
  onUnmounted(() => { stopped = true; epoch++; stopWatch(); clearTimeout(timer); document.removeEventListener('visibilitychange', restart) })
}
