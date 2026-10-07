import { ref } from 'vue'

export const toasts = ref([])
let nextId = 0

export function dismissToast(id) {
  toasts.value = toasts.value.filter((item) => item.id !== id)
}

export function toast(message, type = 'success') {
  const id = ++nextId
  toasts.value.push({ id, message, type })
  setTimeout(() => dismissToast(id), 3000)
}
