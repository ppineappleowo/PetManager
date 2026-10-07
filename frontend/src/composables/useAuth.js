import { reactive } from 'vue'
import {clearListCache} from '../utils/listCache.js'
import {clearAiDraft} from '../utils/aiDraft.js'

export const auth = reactive({
  token: sessionStorage.getItem('token') || '',
  username: sessionStorage.getItem('username') || '',
})

export function setAuth(data) {
  clearListCache()
  clearAiDraft()
  auth.token = data.access_token
  auth.username = data.username
  sessionStorage.setItem('token', auth.token)
  sessionStorage.setItem('username', auth.username)
}

export function clearAuth() {
  clearListCache()
  clearAiDraft()
  auth.token = ''
  auth.username = ''
  sessionStorage.removeItem('token')
  sessionStorage.removeItem('username')
  sessionStorage.removeItem('pet_manager_thread_id')
}
