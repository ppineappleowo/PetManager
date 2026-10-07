import { test, expect } from '@playwright/test'

test('收藏状态、失败重试、私人列表分页和取消', async ({ page }) => {
  await page.addInitScript(() => { sessionStorage.setItem('token', 'test'); sessionStorage.setItem('username', 'alice') })
  const post = id => ({ id, title: `宠物日常${id}`, body: '今天很开心', category: 'cat', tags: [], images: [], author: { id: 1, name: 'alice' }, created_at: '2026-09-24', status: 'published' })
  let saved = false, fail = true
  await page.route('**/api/v1/**', async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname
    const headers = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*' }
    const json = (data, status = 200) => route.fulfill({ headers, status, contentType: 'application/json', body: JSON.stringify(data) })
    if (request.method() === 'OPTIONS') return route.fulfill({ headers, status: 204 })
    if (path.endsWith('/auth/me')) return json({ id: 1, username: 'alice', role: 'user' })
    if (path.endsWith('/bookmark')) {
      if (request.method() === 'PUT') { if (fail) { fail = false; return json({ detail: '暂时无法收藏' }, 503) }; saved = true }
      if (request.method() === 'DELETE') saved = false
      return json({ bookmarked: saved })
    }
    if (path.endsWith('/me/bookmarks')) return json({ items: url.searchParams.has('before') ? [post(2)] : saved ? [post(1)] : [], next_cursor: !url.searchParams.has('before') && saved ? 10 : null })
    if (path.endsWith('/comments')) return json({ items: [], next_cursor: null })
    if (path.endsWith('/interaction')) return json({ liked: false, like_count: 0, comment_count: 0 })
    if (path.endsWith('/posts/1')) return json(post(1))
    return json({})
  })
  await page.goto('/#/posts/1')
  await page.getByRole('button', { name: '☆ 收藏', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('暂时无法收藏')
  await page.getByRole('button', { name: '☆ 收藏', exact: true }).click()
  await expect(page.getByRole('button', { name: '★ 已收藏' })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('link', { name: '我的收藏' }).click()
  await expect(page.getByText('收藏列表仅你可见。', { exact: false })).toBeVisible()
  await expect(page.getByRole('heading', { name: '宠物日常1' })).toBeVisible()
  await page.getByRole('button', { name: '加载更多收藏' }).click()
  await expect(page.locator('.post-card')).toHaveCount(2)
  await page.getByRole('button', { name: '取消收藏：宠物日常1', exact: true }).click()
  await expect(page.locator('.post-card')).toHaveCount(1)
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('游客收藏需登录且保留目标地址', async ({ page }) => {
  await page.goto('/#/bookmarks')
  await expect(page).toHaveURL(/login.*redirect=.*bookmarks/)
})
