import test from 'node:test'
import assert from 'node:assert/strict'
import { effectScope, reactive } from 'vue'
import { useCursorList } from '../src/composables/useCursorList.js'
import {clearListCache,readListCache,writeListCache,listEpoch} from '../src/utils/listCache.js'
import {createAiDraft,takeAiDraft,clearAiDraft} from '../src/utils/aiDraft.js'

test('私人 AI 草稿只可由原会话消费一次，退出或换号后不可带入',()=>{
  let id=createAiDraft('alice','私人回答')
  assert.equal(takeAiDraft('bob',id),'')
  id=createAiDraft('alice','私人回答')
  assert.equal(takeAiDraft('alice',id),'私人回答')
  assert.equal(takeAiDraft('alice',id),'')
  id=createAiDraft('alice','私人回答');clearAiDraft()
  assert.equal(takeAiDraft('alice',id),'')
})

test('列表缓存按账号和查询隔离，失效后旧请求不能重新写入', async()=>{
  clearListCache()
  const epoch=listEpoch(),value={items:[{id:1}],cursor:1}
  writeListCache('alice:cat',value,epoch)
  value.items[0].id=9
  assert.equal(readListCache('alice:cat').items[0].id,1)
  assert.equal(readListCache('bob:cat'),null)
  assert.equal(readListCache('alice:dog'),null)
  clearListCache()
  writeListCache('alice:cat',value,epoch)
  assert.equal(readListCache('alice:cat'),null)
})

test('分页隔离过期响应、重复加载和失败重试', async () => {
  const requests = []
  const scope = effectScope()
  const list = scope.run(() => useCursorList((cursor) => new Promise((resolve, reject) => requests.push({ cursor, resolve, reject }))))
  const old = list.load(), fresh = list.load()
  requests[1].resolve({ items: [{ id: 2 }], next_cursor: 2 }); await fresh
  requests[0].resolve({ items: [{ id: 1 }], next_cursor: 1 }); await old
  assert.deepEqual(list.items.value, [{ id: 2 }])
  const more = list.load(true); await list.load(true)
  assert.equal(requests.length, 3)
  requests[2].reject(new Error('离线')); await more
  assert.equal(list.cursor.value, 2)
  const retry = list.load(true)
  requests[3].resolve({ items: [{ id: 2 }, { id: 3 }], next_cursor: null }); await retry
  assert.deepEqual(list.items.value.map(x => x.id), [2, 3])
  const disposed = list.load(); scope.stop()
  requests[4].resolve({ items: [{ id: 99 }], next_cursor: null }); await disposed
  assert.deepEqual(list.items.value, [])
})
import { createRenderer, nextTick, watch } from 'vue'

const storage = new Map()
globalThis.sessionStorage = {
  getItem: (key) => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, String(value)),
  removeItem: (key) => storage.delete(key),
}
globalThis.window = { APP_CONFIG: { apiBaseUrl: 'http://127.0.0.1:8001/' } }
const { auth, setAuth } = await import('../src/composables/useAuth.js')
const { apiFetch } = await import('../src/api/client.js')
const { loadCurrentUser } = await import('../src/composables/useCurrentUser.js')
const { notificationState, refreshNotifications, useNotificationPolling } = await import('../src/composables/useNotifications.js')

test('用户查询合并并发请求，旧会话 401 不清除新登录', async () => {
  setAuth({ access_token: 'old-session', username: 'old' })
  const pending = []
  globalThis.fetch = () => new Promise(resolve => pending.push(resolve))
  const first = loadCurrentUser(), duplicate = loadCurrentUser()
  assert.equal(first, duplicate)
  assert.equal(pending.length, 1)
  setAuth({ access_token: 'new-session', username: 'new' })
  const latest = loadCurrentUser()
  pending[0](new Response('{}', { status: 401 }))
  await assert.rejects(first)
  assert.equal(auth.token, 'new-session')
  pending[1](new Response(JSON.stringify({ id: 2, username: 'new' })))
  assert.equal((await latest).id, 2)
})
const { streamChat, uploadImage } = await import('../src/api/chat.js')
const { useChat } = await import('../src/composables/useChat.js')
const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })

// 最小 Vue 渲染器使组合式函数运行在真实组件生命周期中，无需下载浏览器。
const renderer = createRenderer({
  createComment: () => ({}), createText: () => ({}), createElement: () => ({}),
  insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {},
  parentNode: () => null, nextSibling: () => null,
})
function mountChat() {
  let chat
  setAuth({ access_token: 'test-token', username: 'test-user' })
  const app = renderer.createApp({ setup() { chat = useChat(); return () => null } })
  app.mount({})
  return { chat, unmount: () => app.unmount() }
}

test('API 拼接地址、携带令牌，401 时清除登录状态', async () => {
  setAuth({ access_token: 'token', username: 'tester' })
  globalThis.fetch = async (url, options) => {
    assert.equal(url, 'http://127.0.0.1:8001/api/v1/chat/stream')
    assert.equal(options.headers.get('Authorization'), 'Bearer token')
    assert.equal(options.headers.get('Content-Type'), 'application/json')
    return json({ detail: '登录已过期' }, 401)
  }
  await assert.rejects(apiFetch('/api/v1/chat/stream', { method: 'POST', body: '{}' }), /登录已过期/)
  assert.equal(auth.token, '')
  assert.equal(sessionStorage.getItem('token'), null)
})

test('登录错误不会附带旧令牌，422 校验消息能被读取', async () => {
  setAuth({ access_token: 'old-token', username: 'tester' })
  globalThis.fetch = async (_, options) => {
    assert.equal(options.headers.has('Authorization'), false)
    return json({ detail: [{ msg: '用户名无效' }, { msg: '密码无效' }] }, 422)
  }
  await assert.rejects(apiFetch('/api/v1/auth/login', { authenticated: false, method: 'POST', body: '{}' }), /用户名无效；密码无效/)
  assert.equal(auth.token, 'old-token')
})

test('文本流跨字节解码中文和 emoji，输出多个增量', async () => {
  const bytes = new TextEncoder().encode(': heartbeat\n\nevent: delta\r\ndata: {"text":"猫咪🐱"}\r\n\r\nevent: delta\ndata: {"text":"养护"}\n\nevent: done\ndata: {"status":"completed"}\n\n')
  globalThis.fetch = async () => new Response(new ReadableStream({
    start(controller) {
      for (const byte of bytes) controller.enqueue(Uint8Array.of(byte))
      controller.close()
    },
  }))
  const chunks = []
  await streamChat({ message: 'test', thread_id: 'test' }, ({ event, data }) => { if (event === 'delta') chunks.push(data.text) })
  assert.equal(chunks.join(''), '猫咪🐱养护')
  assert.ok(chunks.length > 1)
})

test('OSS 使用签名返回的 MIME 类型且不泄漏 API 令牌', async () => {
  setAuth({ access_token: 'test-token', username: 'tester' })
  const file = new File(['image'], '猫.png', { type: 'image/jpeg' })
  globalThis.fetch = async (url, options) => {
    if (url.includes('/oss/presign')) {
      assert.ok(url.includes(encodeURIComponent('猫.png')))
      return json({ uploadUrl: 'https://oss.example/upload', accessUrl: 'https://oss.example/image', contentType: 'image/png' })
    }
    assert.equal(url, 'https://oss.example/upload')
    assert.equal(options.method, 'PUT')
    assert.equal(options.headers['Content-Type'], 'image/png')
    assert.equal(options.headers.Authorization, undefined)
    assert.equal(options.body, file)
    return new Response('', { status: 200 })
  }
  assert.equal(await uploadImage(file), 'https://oss.example/image')
})

test('快速切换会话时，迟到的历史响应不能覆盖当前会话', async () => {
  const pending = new Map()
  globalThis.fetch = (url) => new Promise((resolve) => pending.set(new URL(url).searchParams.get('thread_id'), resolve))
  const { chat, unmount } = mountChat()
  try {
    const first = chat.switchThread('first')
    const second = chat.switchThread('second')
    pending.get('second')(json({ messages: [{ role: 'user', content: [{ type: 'text', text: '第二个会话' }, { type: 'image', url: 'https://example.com/cat.png' }] }] }))
    await second
    pending.get('first')(json({ messages: [{ role: 'user', content: '过期内容' }] }))
    await first
    assert.equal(chat.threadId.value, 'second')
    assert.equal(chat.messages.value[0].content, '第二个会话')
    assert.equal(chat.messages.value[0].imageUrl, 'https://example.com/cat.png')
  } finally { unmount() }
})

test('流式回答逐步更新响应式状态，阻止重复发送并记录完成状态', async () => {
  let controller
  let requestSignal
  let chatCalls = 0
  globalThis.fetch = async (url, options) => {
    if (url.endsWith('/chat/threads')) return json({ threads: [] })
    chatCalls++
    requestSignal = options.signal
    return new Response(new ReadableStream({ start(value) { controller = value } }))
  }
  const { chat, unmount } = mountChat()
  try {
    const updates = []
    const stop = watch(() => chat.messages.value.at(-1)?.content, (text) => updates.push(text), { flush: 'sync' })
    chat.draft.value = '你好'
    const sendPromise = chat.send()
    assert.equal(chat.sending.value, true)
    assert.equal(chat.canSend.value, false)
    await chat.send()
    controller.enqueue(new TextEncoder().encode('event: delta\ndata: {"text":"第一段"}\n\n'))
    await new Promise((resolve) => setImmediate(resolve))
    assert.equal(chat.messages.value.at(-1).content, '第一段')
    controller.enqueue(new TextEncoder().encode('event: delta\ndata: {"text":"第二段"}\n\nevent: done\ndata: {"status":"completed"}\n\n'))
    controller.close()
    await sendPromise
    await nextTick()
    assert.ok(updates.includes('第一段'))
    assert.equal(chat.messages.value.at(-1).content, '第一段第二段')
    assert.equal(chat.sending.value, false)
    assert.equal(chatCalls, 1)
    stop()
  } finally { unmount() }
  assert.equal(requestSignal.aborted, false)
})

test('删除失败时保留会话，成功时移除并重置当前会话', async () => {
  const { chat, unmount } = mountChat()
  try {
    chat.threads.value = [{ thread_id: chat.threadId.value, title: '原有会话' }]
    const id = chat.threadId.value
    globalThis.fetch = async () => json({ detail: '删除失败' }, 500)
    assert.equal(await chat.removeThread(id), false)
    assert.equal(chat.threads.value.length, 1)
    assert.equal(chat.threadId.value, id)
    globalThis.fetch = async () => json({ success: true })
    assert.equal(await chat.removeThread(id), true)
    assert.equal(chat.threads.value.length, 0)
    assert.notEqual(chat.threadId.value, id)
  } finally { unmount() }
})

test('流式连接无 done 即断开、错误事件和损坏 JSON 都标记失败', async () => {
  for (const [body, pattern] of [
    ['event: delta\ndata: {"text":"半段回答"}\n\n', /连接已中断/],
    ['event: error\ndata: {"message":"模型暂时不可用"}\n\n', /模型暂时不可用/],
    ['event: delta\ndata: not-json\n\n', /响应格式异常/],
  ]) {
    globalThis.fetch = async () => new Response(body)
    await assert.rejects(streamChat({}, () => {}), pattern)
  }
})

test('失败重试复用 request_id 和用户气泡，替换部分回答', async () => {
  let attempts = 0
  const payloads = []
  globalThis.fetch = async (url, options) => {
    if (url.endsWith('/chat/threads')) return json({ threads: [] })
    payloads.push(JSON.parse(options.body))
    attempts++
    return new Response(attempts === 1
      ? 'event: delta\ndata: {"text":"半段"}\n\n'
      : 'event: delta\ndata: {"text":"完整回答"}\n\nevent: done\ndata: {"status":"completed"}\n\n')
  }
  const { chat, unmount } = mountChat()
  try {
    chat.draft.value = '请给建议'
    await chat.send()
    assert.equal(chat.messages.value[0].state, 'failed')
    assert.equal(chat.messages.value[1].content, '半段')
    await chat.retry(chat.messages.value[0].requestId)
    assert.equal(chat.messages.value.length, 2)
    assert.equal(chat.messages.value[1].content, '完整回答')
    assert.equal(chat.messages.value[0].state, 'completed')
    assert.equal(payloads[0].request_id, payloads[1].request_id)
  } finally { unmount() }
})

test('停止生成调用后端停止接口，并保留部分回答', async () => {
  let controller
  let signal
  let stopped = false
  globalThis.fetch = async (url, options) => {
    if (url.endsWith('/chat/threads')) return json({ threads: [] })
    if (url.endsWith('/stop')) { stopped = true; return json({ status: 'cancelled' }) }
    signal = options.signal
    return new Response(new ReadableStream({ start(value) {
      controller = value
      value.enqueue(new TextEncoder().encode('event: delta\ndata: {"text":"部分回答"}\n\n'))
      options.signal.addEventListener('abort', () => value.error(new DOMException('Stopped', 'AbortError')), { once: true })
    } }))
  }
  const { chat, unmount } = mountChat()
  try {
    chat.draft.value = '问题'
    const running = chat.send()
    await new Promise((resolve) => setImmediate(resolve))
    assert.equal(chat.messages.value[1].content, '部分回答')
    await chat.stop()
    await running
    assert.ok(stopped)
    assert.ok(signal.aborted)
    assert.equal(chat.messages.value[1].state, 'cancelled')
    assert.equal(chat.messages.value[1].content, '部分回答')
    assert.equal(chat.sending.value, false)
  } finally { unmount() }
})

test('上传失败保留原文件，重试后只发送一条用户消息', async () => {
  let uploadCount = 0
  globalThis.fetch = async (url) => {
    if (url.endsWith('/chat/threads')) return json({ threads: [] })
    if (url.includes('/oss/presign')) return json({ uploadUrl: 'https://oss.example/upload', accessUrl: 'https://oss.example/image', contentType: 'image/png' })
    if (url.startsWith('https://oss.example')) {
      uploadCount++
      return new Response('', { status: uploadCount === 1 ? 500 : 200 })
    }
    return new Response('event: delta\ndata: {"text":"完成"}\n\nevent: done\ndata: {"status":"completed"}\n\n')
  }
  const { chat, unmount } = mountChat()
  try {
    chat.selectedFile.value = new File(['image'], 'cat.png', { type: 'image/png' })
    await chat.send()
    assert.equal(chat.messages.value[0].state, 'failed')
    assert.ok(chat.messages.value[0].retryPayload.file)
    await chat.retry(chat.messages.value[0].requestId)
    assert.equal(chat.messages.value.length, 2)
    assert.equal(chat.messages.value[0].imageUrl, 'https://oss.example/image')
    assert.equal(chat.messages.value[1].state, 'completed')
  } finally { unmount() }
})

test('登录限流信息含 Retry-After，前后端共用校验规则', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: '请稍后重试' }), { status: 429, headers: { 'Retry-After': '60' } })
  await assert.rejects(apiFetch('/api/v1/auth/login', { authenticated: false }), (error) => error.status === 429 && error.retryAfter === 60)
  const { usernameError, passwordError } = await import('../src/utils/validation.js')
  assert.ok(usernameError('a'))
  assert.ok(usernameError('bad name'))
  assert.equal(usernameError('猫主人_01'), '')
  assert.ok(passwordError('      '))
  assert.equal(passwordError('password123'), '')
})

test('通知摘要合并请求，切换账号丢弃旧结果', async () => {
  setAuth({ access_token: 'notice-old', username: 'old' })
  const requests = []
  globalThis.fetch = () => new Promise(resolve => requests.push(resolve))
  const old = refreshNotifications()
  assert.equal(refreshNotifications(), old)
  setAuth({ access_token: 'notice-new', username: 'new' })
  const current = refreshNotifications()
  requests[1](json({ unread_count: 2, latest_id: 7 })); await current
  requests[0](json({ unread_count: 99, latest_id: 99 })); await old
  assert.equal(notificationState.unread, 2)
  assert.equal(notificationState.latestId, 7)
})

test('通知轮询在隐藏和后台页暂停，失败退避，卸载清理', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const original = globalThis.document
  const listeners = new Map()
  globalThis.document = { visibilityState: 'visible', addEventListener: (name, fn) => listeners.set(name, fn), removeEventListener: name => listeners.delete(name) }
  const route = reactive({ meta: { admin: false } })
  let calls = 0, fail = false
  globalThis.fetch = async () => { calls++; return json(fail ? {} : { unread_count: 1, latest_id: 1 }, fail ? 503 : 200) }
  setAuth({ access_token: 'poll', username: 'alice' })
  const app = renderer.createApp({ setup() { useNotificationPolling(route); return () => null } })
  try {
    app.mount({}); await refreshNotifications()
    assert.equal(calls, 1)
    document.visibilityState = 'hidden'; listeners.get('visibilitychange')()
    t.mock.timers.tick(60000); assert.equal(calls, 1)
    document.visibilityState = 'visible'; listeners.get('visibilitychange')(); await refreshNotifications()
    assert.equal(calls, 2)
    route.meta.admin = true; await nextTick(); t.mock.timers.tick(60000); assert.equal(calls, 2)
    route.meta.admin = false; await nextTick(); await refreshNotifications(); assert.equal(calls, 3)
    fail = true; t.mock.timers.tick(30000); await assert.rejects(refreshNotifications()); await nextTick()
    assert.equal(calls, 4)
    t.mock.timers.tick(30000); assert.equal(calls, 4)
    fail = false; t.mock.timers.tick(30000); await refreshNotifications(); assert.equal(calls, 5)
    app.unmount(); t.mock.timers.tick(300000); assert.equal(calls, 5)
    assert.equal(listeners.size, 0)
  } finally { globalThis.document = original; t.mock.timers.reset() }
})
