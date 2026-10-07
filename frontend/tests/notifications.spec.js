import { test, expect } from '@playwright/test'

test('消息分页、隐藏占位、已读范围与跳转', async ({ page }) => {
  await page.addInitScript(() => { sessionStorage.setItem('token', 'test'); sessionStorage.setItem('username', 'alice') })
  const items = [
    { id: 3, kind: 'reply', available: true, actor: { name: '宠友小白' }, target: '/posts/1', read: false, created_at: '2026-09-25T00:00:00Z' },
    { id: 2, kind: 'comment', available: false, actor: null, target: null, read: false, created_at: '2026-09-25T00:00:00Z' },
    { id: 1, kind: 'follow', available: true, actor: { name: '宠友小黑' }, target: '/users/2', read: false, created_at: '2026-09-25T00:00:00Z' },
  ]
  let failRead = true, through
  await page.route('**/api/v1/**', async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname
    const headers = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*' }
    const json = (data, status = 200) => route.fulfill({ headers, status, contentType: 'application/json', body: JSON.stringify(data) })
    if (request.method() === 'OPTIONS') return route.fulfill({ headers, status: 204 })
    if (path.endsWith('/auth/me')) return json({ id: 1, username: 'alice' })
    if (path.endsWith('/notifications/summary')) return json({ unread_count: items.filter(n => !n.read).length, latest_id: 3 })
    if (path.endsWith('/notifications/read-all')) {
      through = request.postDataJSON().through_id
      items.forEach(n => { if (n.id <= through) n.read = true })
      return json({ success: true })
    }
    if (/notifications\/\d+\/read$/.test(path)) {
      if (failRead) { failRead = false; return json({ detail: '暂时无法标记' }, 503) }
      items.find(n => n.id === Number(path.split('/').at(-2))).read = true
      return json({ success: true })
    }
    if (path.endsWith('/notifications')) return json({ items: url.searchParams.has('before') ? items.slice(2) : items.slice(0, 2), next_cursor: url.searchParams.has('before') ? null : 2 })
    if (path.endsWith('/users/2')) return json({ id: 2, name: '宠友小黑', bio: '', post_count: 0 })
    if (path.endsWith('/posts')) return json({ items: [], next_cursor: null })
    return json({})
  })
  await page.goto('/#/notifications')
  await expect(page.getByText('宠友小白 回复了你的评论')).toBeVisible()
  await expect(page.getByText('相关内容或用户已不可用')).toBeVisible()
  await page.getByRole('button', { name: '标为已读', exact: true }).first().click()
  await expect(page.getByRole('alert')).toContainText('暂时无法标记')
  await page.getByRole('button', { name: '标为已读', exact: true }).first().click()
  await page.getByRole('button', { name: '加载更多消息' }).click()
  await expect(page.getByText('宠友小黑 关注了你')).toBeVisible()
  await page.getByRole('button', { name: '全部标为已读', exact: true }).click()
  await expect(page.getByRole('button', { name: '标为已读', exact: true })).toHaveCount(0)
  expect(through).toBe(3)
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/notifications-mobile.png', fullPage: true })
  await page.getByRole('button', { name: '查看主页' }).click()
  await expect(page).toHaveURL(/#\/users\/2$/)
})

test('通知页面要求登录', async ({ page }) => {
  await page.goto('/#/notifications')
  await expect(page).toHaveURL(/login.*redirect=.*notifications/)
})
