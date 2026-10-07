import { test, expect } from '@playwright/test'

async function mockApi(page, { authenticated = true, rejectDelete = false, expire = false } = {}) {
  const state = { requests: [], uploads: [], threads: [{ thread_id: 'old-thread', title: '猫咪喂养', message_count: 2 }] }
  if (authenticated) await page.addInitScript(() => {
    sessionStorage.setItem('token', 'test-token')
    sessionStorage.setItem('username', '测试用户')
  })
  const headers = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*' }
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers })
    state.requests.push({ path: url.pathname, method: request.method(), body: request.postData(), headers: request.headers() })
    const json = (value, status = 200) => route.fulfill({ status, headers, contentType: 'application/json', body: JSON.stringify(value) })
    if (url.pathname.endsWith('/auth/register')) return json({ id: 1, username: '测试用户' }, 201)
    if (url.pathname.endsWith('/auth/login')) return json({ access_token: 'test-token', username: '测试用户' })
    if (url.pathname.endsWith('/auth/password')) return json({ success: true })
    if (url.pathname.endsWith('/community/posts')) return json({ items: [], total: 0, next_cursor: null })
    if (expire) return json({ detail: '认证令牌已过期，请重新登录' }, 401)
    if (url.pathname.endsWith('/auth/me')) return json({ id: 1, username: '测试用户', role: 'user' })
    if (url.pathname.endsWith('/chat/threads')) return json({ threads: state.threads })
    if (url.pathname.endsWith('/chat/messages') && request.method() === 'DELETE') {
      if (rejectDelete) return json({ detail: '删除失败，请重试' }, 500)
      state.threads = []
      return json({ success: true })
    }
    if (url.pathname.endsWith('/chat/messages')) return json({ messages: url.searchParams.get('thread_id') === 'old-thread' ? [
      { role: 'user', content: '猫咪怎么喂养？', image_url: 'https://images.example/pet.png' },
      { role: 'assistant', content: '历史养护建议' },
    ] : [] })
    if (url.pathname.endsWith('/oss/presign')) return json({ uploadUrl: 'https://oss.example/upload', accessUrl: 'https://images.example/uploaded.png', contentType: 'image/png' })
    if (url.pathname.endsWith('/chat/stream')) {
      const data = JSON.parse(request.postData())
      state.threads = [{ thread_id: data.thread_id, title: data.message || '图片咨询', message_count: 2 }, ...state.threads]
      const body = `event: delta\ndata: ${JSON.stringify({ text: '**养护建议**：少量多餐。\n\n<script>window.injected = true</script>' })}\n\nevent: done\ndata: {"status":"completed"}\n\n`
      return route.fulfill({ status: 200, headers, contentType: 'text/event-stream', body })
    }
    return json({ detail: 'Not found' }, 404)
  })
  await page.route('https://oss.example/**', (route) => {
    if (route.request().method() !== 'OPTIONS') state.uploads.push(route.request().headers())
    return route.fulfill({ status: 200, headers, body: '' })
  })
  await page.route('https://images.example/**', (route) => route.fulfill({ contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a6XcAAAAASUVORK5CYII=', 'base64') }))
  return state
}

test('登录守卫、注册校验、登录与退出', async ({ page }) => {
  const state = await mockApi(page, { authenticated: false })
  await page.goto('/#/ai')
  await expect(page).toHaveURL(/#\/login(?:\?|$)/)
  await page.getByRole('button', { name: '注 册', exact: true }).first().click()
  await expect(page.getByRole('button', { name: '获取验证码' })).toHaveCount(0)
  await page.getByLabel('手机号', { exact: true }).fill('13800138000')
  await page.getByLabel('密码', { exact: true }).fill('123456')
  await page.getByLabel('确认密码').fill('654321')
  await page.getByRole('button', { name: '注 册', exact: true }).last().click()
  await expect(page.getByText('两次输入的密码不一致')).toBeVisible()
  expect(state.requests.filter((request) => request.path.endsWith('/register'))).toHaveLength(0)
  await page.getByLabel('确认密码').fill('123456')
  await page.getByRole('button', { name: '注 册', exact: true }).last().click()
  await expect(page.getByText('注册成功！请登录')).toBeVisible()
  expect(JSON.parse(state.requests.find(request => request.path.endsWith('/register')).body)).toEqual({ phone: '13800138000', password: '123456' })
  await page.getByLabel('密码', { exact: true }).fill('123456')
  await page.getByRole('button', { name: '登 录', exact: true }).last().click()
  await expect(page.getByText('宠物养护咨询')).toBeVisible()
  await page.getByRole('button', { name: '个人中心', exact: true }).click()
  await page.getByRole('button', { name: '账号与安全', exact: true }).click()
  await expect(page.getByRole('button', { name: '修改密码', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '退出登录', exact: true }).click()
  await expect(page).toHaveURL(/#\/login(?:\?|$)/)
  expect(await page.evaluate(() => sessionStorage.getItem('token'))).toBeNull()
})

test('历史图文、发送回答、Markdown 清理、会话删除', async ({ page }) => {
  const state = await mockApi(page)
  const exceptions = []
  page.on('pageerror', (error) => exceptions.push(error.message))
  await page.goto('/#/ai')
  await page.locator('.thread-select').filter({ hasText: '猫咪喂养' }).click()
  await expect(page.getByText('历史养护建议')).toBeVisible()
  await expect(page.getByRole('img', { name: '上传的宠物照片' })).toBeVisible()
  await expect(page.getByText('猫咪怎么喂养？', { exact: true })).toBeVisible()
  await page.screenshot({ path: 'test-results/chat-desktop.png', fullPage: true })
  await page.getByRole('button', { name: /新建会话/ }).click()
  await page.getByLabel('宠物咨询内容').fill('幼猫如何喂养？')
  await page.getByRole('button', { name: '发送消息', exact: true }).click()
  await expect(page.locator('.markdown strong')).toHaveText('养护建议')
  await expect(page.getByRole('button', { name: /复制/ })).toBeVisible()
  expect(await page.evaluate(() => window.injected)).toBeUndefined()
  const chatRequest = state.requests.find((request) => request.path.endsWith('/chat/stream'))
  expect(chatRequest.headers.authorization).toBe('Bearer test-token')
  expect(JSON.parse(chatRequest.body).message).toBe('幼猫如何喂养？')
  await page.getByRole('button', { name: '删除会话 幼猫如何喂养？', exact: true }).click()
  await page.getByRole('button', { name: '确认删除', exact: true }).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(page.getByText('会话已删除')).toBeVisible()
  expect(exceptions).toEqual([])
})

test('上传图片使用签名类型，图片与文字同时显示', async ({ page }) => {
  const state = await mockApi(page)
  await page.goto('/#/ai')
  await expect(page.getByLabel('宠物咨询内容')).toBeEnabled()
  await page.locator('input[type=file]').setInputFiles({ name: '宠物.png', mimeType: 'image/png', buffer: Buffer.from('test-image') })
  await page.getByLabel('宠物咨询内容').fill('看看我的猫')
  await page.getByRole('button', { name: '发送消息', exact: true }).click()
  await expect(page.locator('.markdown strong')).toHaveText('养护建议')
  await expect(page.getByRole('img', { name: '上传的宠物照片' })).toBeVisible()
  await expect(page.getByRole('article', { name: '你的消息' }).getByText('看看我的猫', { exact: true })).toBeVisible()
  expect(state.uploads[0]['content-type']).toBe('image/png')
  expect(state.uploads[0].authorization).toBeUndefined()
  const body = JSON.parse(state.requests.find((request) => request.path.endsWith('/chat/stream')).body)
  expect(body.image_url).toBe('https://images.example/uploaded.png')
})

test('删除失败保留会话，过期认证跳回登录', async ({ page }) => {
  await mockApi(page, { rejectDelete: true })
  await page.goto('/#/ai')
  await page.getByRole('button', { name: '删除会话 猫咪喂养', exact: true }).click()
  await page.getByRole('button', { name: '确认删除', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('button', { name: /猫咪喂养/, exact: false }).first()).toBeVisible()
  await page.unrouteAll({ behavior: 'wait' })
  await mockApi(page, { expire: true })
  await page.reload()
  await expect(page).toHaveURL(/#\/login(?:\?|$)/)
})

test('移动端布局与旧登录链接', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockApi(page, { authenticated: false })
  await page.goto('/login.html')
  await expect(page).toHaveURL(/#\/login(?:\?|$)/)
  await page.screenshot({ path: 'test-results/login-mobile.png', fullPage: true })
  await page.getByLabel('手机号或用户名', { exact: true }).fill('测试用户')
  await page.getByLabel('密码', { exact: true }).fill('123456')
  await page.getByRole('button', { name: '登 录', exact: true }).last().click()
  await expect(page.getByRole('heading', { name: '每一种宠爱，都有同好。' })).toBeVisible()
  await page.getByRole('navigation', { name: '移动导航' }).getByRole('link', { name: 'AI 助手' }).click()
  await expect(page.getByText('宠物养护咨询')).toBeVisible()
  await page.getByRole('button', { name: '展开会话列表' }).click()
  await expect(page.locator('.sidebar')).toHaveClass(/open/)
  await page.locator('.thread-select').filter({ hasText: '猫咪喂养' }).click()
  await expect(page.getByText('历史养护建议')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/chat-mobile.png', fullPage: true })
})

test('文本流正确处理跨字节中文和分块回调', async ({ page }) => {
  await mockApi(page)
  await page.goto('/#/ai')
  await expect(page.getByLabel('宠物咨询内容')).toBeEnabled()
  const chunks = await page.evaluate(async () => {
    const { streamChat } = await import('/src/api/chat.js')
    const originalFetch = window.fetch
    const bytes = new TextEncoder().encode('event: delta\ndata: {"text":"猫咪🐱"}\n\nevent: delta\ndata: {"text":"养护"}\n\nevent: done\ndata: {"status":"completed"}\n\n')
    window.fetch = async () => new Response(new ReadableStream({
      start(controller) {
        controller.enqueue(bytes.slice(0, 2))
        controller.enqueue(bytes.slice(2, 7))
        controller.enqueue(bytes.slice(7))
        controller.close()
      },
    }))
    const received = []
    try { await streamChat({ message: 'test', thread_id: 'test' }, ({ event, data }) => { if (event === 'delta') received.push(data.text) }) }
    finally { window.fetch = originalFetch }
    return received
  })
  expect(chunks.join('')).toBe('猫咪🐱养护')
  expect(chunks.length).toBeGreaterThan(1)
})

test('回答逐块更新，生成期间禁用重复发送和会话切换', async ({ page }) => {
  await mockApi(page)
  await page.addInitScript(() => {
    const originalFetch = window.fetch
    window.fetch = (input, options) => {
      if (!String(input).endsWith('/chat/stream')) return originalFetch(input, options)
      return Promise.resolve(new Response(new ReadableStream({
        start(controller) {
          const encoder = new TextEncoder()
          controller.enqueue(encoder.encode('event: delta\ndata: {"text":"第一部分"}\n\n'))
          setTimeout(() => { controller.enqueue(encoder.encode('event: delta\ndata: {"text":"，第二部分"}\n\nevent: done\ndata: {"status":"completed"}\n\n')); controller.close() }, 1800)
        },
      })))
    }
  })
  await page.goto('/#/ai')
  await expect(page.getByLabel('宠物咨询内容')).toBeEnabled()
  await page.getByLabel('宠物咨询内容').fill('请给我一些建议')
  await page.getByRole('button', { name: '发送消息', exact: true }).click()
  await expect(page.locator('.markdown')).toHaveText('第一部分')
  await expect(page.getByRole('button', { name: '停止生成', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: /新建会话/ })).toBeDisabled()
  await expect(page.locator('.markdown')).toHaveText('第一部分，第二部分')
  await expect(page.getByRole('button', { name: /新建会话/ })).toBeEnabled()
})
