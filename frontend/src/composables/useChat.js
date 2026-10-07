import { computed, onBeforeUnmount, ref, watch } from 'vue'
import * as chatApi from '../api/chat.js'
import { auth } from './useAuth.js'
import { toast } from './useToast.js'

const newId = () => `thread_${Date.now()}_${crypto.randomUUID()}`

function normalizeMessage(message, threadId) {
  let imageUrl = message.image_url || ''
  let content = message.content || ''
  if (Array.isArray(content)) {
    content = content.map((part) => {
      if (typeof part === 'string') return part
      if (part.type === 'image') imageUrl ||= part.url || ''
      if (part.type === 'image_url') imageUrl ||= part.image_url?.url || ''
      return part.type === 'text' ? part.text || '' : ''
    }).filter(Boolean).join(' ')
  }
  const state = message.status === 'running' ? 'failed' : message.status || 'completed'
  const result = { id: crypto.randomUUID(), role: message.role, content: String(content), imageUrl,
    requestId: message.request_id, state, error: message.error || '', pending: false }
  result.sources=message.sources||[];result.feedback=message.feedback||''
  if (message.role === 'user' && message.request_id) result.retryPayload = {
    request_id: message.request_id, thread_id: threadId, message: String(content), image_url: imageUrl,pet_id:message.context?.id||null,
  }
  return result
}

export function useChat() {
  const storageKey = `pet_manager_thread_id:${auth.username}`
  const threadId = ref(sessionStorage.getItem(storageKey) || newId())
  const threads = ref([])
  const messages = ref([])
  const draft = ref('')
  const selectedFile = ref(null)
  const selectedPet = ref(null)
  const sending = ref(false)
  const stopping = ref(false)
  const loading = ref(false)
  const status = ref('')
  const error = ref('')
  const lifetime = new AbortController()
  let historyRequest
  let currentRun
  let generation = 0
  const canSend = computed(() => !sending.value && !loading.value && (!!draft.value.trim() || !!selectedFile.value))
  const lastRequestId = computed(() => messages.value.filter((message) => message.role === 'user').at(-1)?.requestId)
  watch(threadId, (value) => sessionStorage.setItem(storageKey, value), { immediate: true })

  function showError(reason) {
    if (reason.name !== 'AbortError') {
      error.value = reason.message
      toast(reason.message, 'error')
    }
  }
  async function refreshThreads() {
    const data = await chatApi.getThreads(lifetime.signal)
    threads.value = data.threads || []
  }
  async function loadMessages() {
    historyRequest?.abort()
    historyRequest = new AbortController()
    const requestNumber = ++generation
    loading.value = true
    error.value = ''
    messages.value = []
    try {
      const data = await chatApi.getMessages(threadId.value, historyRequest.signal)
      if (requestNumber === generation) messages.value = (data.messages || []).map((message) => normalizeMessage(message, threadId.value))
    } catch (reason) {
      if (requestNumber === generation) showError(reason)
    } finally {
      if (requestNumber === generation) loading.value = false
    }
  }
  async function initialize() {
    await Promise.all([refreshThreads().catch(showError), loadMessages()])
  }
  async function switchThread(id) {
    if (sending.value || id === threadId.value) return
    threadId.value = id
    draft.value = ''
    selectedFile.value = null
    await loadMessages()
  }
  function newThread() {
    if (sending.value) return
    historyRequest?.abort()
    generation++
    loading.value = false
    threadId.value = newId()
    messages.value = []
    draft.value = ''
    selectedFile.value = null
    error.value = ''
  }
  async function removeThread(id) {
    if (sending.value) return false
    try {
      await chatApi.deleteThread(id, lifetime.signal)
      if (id === threadId.value) newThread()
      threads.value = threads.value.filter((thread) => thread.thread_id !== id)
      toast('会话已删除')
      return true
    } catch (reason) { showError(reason); return false }
  }

  async function execute(userMessage, answer) {
    const controller = new AbortController()
    const run = { controller, requestId: userMessage.requestId, phase: 'uploading', stopped: false }
    currentRun = run
    sending.value = true
    stopping.value = false
    error.value = ''
    userMessage.state = 'sending'
    userMessage.error = ''
    answer.state = 'running'
    answer.pending = true
    answer.error = ''
    // 用户重试时用同一个气泡展示新结果，不重复追加用户消息。
    answer.content = ''
    answer.sources=[]
    const payload = userMessage.retryPayload
    try {
      if (payload.file && !payload.image_url) {
        status.value = '正在上传图片…'
        payload.image_url = await chatApi.uploadImage(payload.file, controller.signal)
        userMessage.imageUrl = payload.image_url
        delete payload.file
      }
      controller.signal.throwIfAborted()
      run.phase = 'streaming'
      status.value = '正在连接…'
      const outcome = await chatApi.streamChat({
        message: payload.message, image_url: payload.image_url || '',
        thread_id: payload.thread_id, request_id: payload.request_id,
        pet_id:payload.pet_id||null,
      }, ({ event, data }) => {
        if (event === 'status') status.value = data.message || ''
        if (event === 'delta') answer.content += data.text || ''
        if (event === 'sources') answer.sources=data.items||[]
      }, controller.signal)
      userMessage.state = answer.state = outcome
    } catch (reason) {
      if (run.stopped || reason.name === 'AbortError') {
        userMessage.state = answer.state = 'cancelled'
      } else {
        userMessage.state = answer.state = 'failed'
        userMessage.error = answer.error = reason.message
        showError(reason)
      }
    } finally {
      answer.pending = false
      sending.value = false
      stopping.value = false
      status.value = ''
      currentRun = null
      if (!lifetime.signal.aborted) await refreshThreads().catch(showError)
    }
  }

  async function send() {
    if (!canSend.value) return
    const requestId = crypto.randomUUID()
    const text = draft.value.trim()
    messages.value.push({ id: crypto.randomUUID(), requestId, role: 'user', content: text || '（查看图片）', imageUrl: '',
      retryPayload: { request_id: requestId, thread_id: threadId.value, message: text, image_url: '', file: selectedFile.value,pet_id:selectedPet.value } })
    const userMessage = messages.value.at(-1)
    messages.value.push({ id: crypto.randomUUID(), requestId, role: 'assistant', content: '' })
    const answer = messages.value.at(-1)
    draft.value = ''
    selectedFile.value = null
    await execute(userMessage, answer)
  }

  async function retry(requestId) {
    if (sending.value || loading.value || requestId !== lastRequestId.value) return
    const userMessage = messages.value.find((item) => item.role === 'user' && item.requestId === requestId)
    const answer = messages.value.find((item) => item.role === 'assistant' && item.requestId === requestId)
    if (!userMessage?.retryPayload || !answer || !['failed', 'cancelled'].includes(userMessage.state)) return
    await execute(userMessage, answer)
  }

  async function stop() {
    const run = currentRun
    if (!run || stopping.value) return
    stopping.value = true
    run.stopped = true
    try {
      if (run.phase === 'streaming') await chatApi.stopGeneration(run.requestId, AbortSignal.timeout(8000))
    } catch (reason) {
      // 服务端可能尚未收到请求；关闭连接也会触发取消。其他失败明确提示。
      if (reason.status !== 404) toast('停止确认失败，已断开本次连接', 'error')
    } finally { run.controller.abort() }
  }

  onBeforeUnmount(() => {
    lifetime.abort()
    currentRun?.controller.abort()
    historyRequest?.abort()
  })
  return { threadId, threads, messages, draft, selectedFile, selectedPet,sending, stopping, loading, status, error, canSend,
    lastRequestId, initialize, switchThread, newThread, removeThread, send, stop, retry }
}
