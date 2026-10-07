import { apiFetch, apiJson } from './client.js'

export const getThreads = (signal) => apiJson('/api/v1/chat/threads', { signal })
export const getMessages = (id, signal) => apiJson(`/api/v1/chat/messages?thread_id=${encodeURIComponent(id)}`, { signal })
export const deleteThread = (id, signal) => apiJson(`/api/v1/chat/messages?thread_id=${encodeURIComponent(id)}`, { method: 'DELETE', signal })
export const stopGeneration = (id, signal) => apiJson(`/api/v1/chat/requests/${id}/stop`, { method: 'POST', signal })

export async function uploadImage(file, signal) {
  const { uploadUrl, accessUrl, contentType } = await apiJson(
    `/api/v1/oss/presign?filename=${encodeURIComponent(file.name)}`, { signal },
  )
  const response = await fetch(uploadUrl, {
    method: 'PUT', body: file, signal,
    headers: { 'Content-Type': contentType || file.type || 'image/jpeg' },
  })
  if (!response.ok) throw new Error('上传图片失败')
  return accessUrl
}

// 按事件边界解析 SSE，支持跨网络分块、UTF-8、心跳和明确终态。
export async function streamChat(payload, onEvent, signal) {
  signal = AbortSignal.any([...(signal ? [signal] : []), AbortSignal.timeout(210000)])
  const response = await apiFetch('/api/v1/chat/stream', {
    method: 'POST', body: JSON.stringify(payload), signal,
  })
  if (!response.body) throw new Error('浏览器无法读取流式响应')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let terminal = null
  const consume = () => {
    let boundary
    while ((boundary = buffer.indexOf('\n\n')) >= 0) {
      const frame = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      let event = 'message'
      const data = []
      for (const line of frame.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
      }
      if (!data.length) continue
      let parsed
      try { parsed = JSON.parse(data.join('\n')) } catch { throw new Error('响应格式异常，请重试') }
      onEvent({ event, data: parsed })
      if (event === 'error') throw new Error(parsed.message || '生成失败，请重试')
      if (event === 'done') {
        if (!['completed', 'cancelled', 'failed'].includes(parsed.status)) throw new Error('响应缺少有效的完成状态')
        if (parsed.status === 'failed') throw new Error('生成失败，请重试')
        terminal = parsed.status
        return
      }
    }
  }
  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
      // CRLF 可能跨两次 read：保留尾部 CR，等下一块一起处理。
      buffer = buffer.replace(/\r\n/g, '\n')
      consume()
      if (terminal || done) break
    }
    if (!terminal) throw new Error('连接已中断，回答尚未完成，请重试')
    return terminal
  } finally {
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}
