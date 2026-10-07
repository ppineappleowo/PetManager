import { test, expect } from '@playwright/test'

async function mock(page, loggedIn = true) {
  let following = false, fail = true
  const friend = { id: 2, name: '小狗家长', bio: '一起散步', avatar_id: '' }
  const post = { id: 9, title: '散步日常', body: '今天也很开心', category: 'dog', tags: [], images: [], status: 'published', author: friend, created_at: '2026-09-22' }
  if (loggedIn) await page.addInitScript(() => { sessionStorage.setItem('token', 'test'); sessionStorage.setItem('username', 'alice') })
  await page.route('**/api/v1/**', async route => {
    const req = route.request(), url = new URL(req.url()), path = url.pathname
    const headers = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*' }
    const json = (data, status = 200) => route.fulfill({ status, headers, contentType: 'application/json', body: JSON.stringify(data) })
    if (req.method() === 'OPTIONS') return route.fulfill({ status: 204, headers })
    if (path.endsWith('/auth/me')) return json({ id: 1, username: 'alice', role: 'user' })
    if (path.endsWith('/users/2')) return json({ ...friend, post_count: 1 })
    if (path.endsWith('/users/2/follow') || path.endsWith('/users/2/social')) {
      if (req.method() === 'PUT') {
        if (fail) { fail = false; return json({ detail: '暂时无法关注，请重试' }, 503) }
        following = true
      }
      if (req.method() === 'DELETE') following = false
      return json({ following, is_self: false, follower_count: following ? 1 : 0, following_count: 0 })
    }
    if (path.endsWith('/me/connections')) return json({ items: following || url.searchParams.get('kind') === 'followers' ? [{ ...friend, following }] : [], next_cursor: null })
    if (path.endsWith('/me/following/posts')) return json({ items: following ? [post] : [], next_cursor: null })
    if (path.endsWith('/posts')) return json({ items: [post], next_cursor: null })
    return json({})
  })
}

test('关注失败可重试、关注动态、取消与粉丝回关', async ({ page }) => {
  await mock(page)
  await page.goto('/#/users/2')
  await page.getByRole('button', { name: '＋ 关注', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('暂时无法关注')
  await expect(page.getByRole('button', { name: '＋ 关注', exact: true })).toHaveAttribute('aria-pressed', 'false')
  await page.getByRole('button', { name: '重试', exact: true }).click()
  await expect(page.getByRole('button', { name: '已关注 · 取消关注' })).toBeVisible()
  await expect(page.getByText('0 关注 · 1 粉丝')).toBeVisible()
  await page.getByRole('link', { name: '关注动态', exact: true }).click()
  await expect(page.getByRole('heading', { name: '散步日常' })).toBeVisible()
  await page.getByRole('link', { name: '我的同好', exact: true }).click()
  await expect(page.getByRole('heading', { name: '小狗家长' })).toBeVisible()
  await page.screenshot({ path: 'test-results/connections-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/connections-mobile.png', fullPage: true })
  await page.getByRole('button', { name: '取消关注', exact: true }).click()
  await expect(page.getByRole('heading', { name: '还没有关注的宠友' })).toBeVisible()
  await page.getByRole('link', { name: '我的粉丝', exact: true }).click()
  await page.getByRole('button', { name: '关注', exact: true }).click()
  await expect(page.getByRole('button', { name: '取消关注', exact: true })).toBeVisible()
})

test('游客关注跳转登录并保留目标主页', async ({ page }) => {
  await mock(page, false)
  await page.goto('/#/users/2')
  await page.getByRole('button', { name: '＋ 关注', exact: true }).click()
  await expect(page).toHaveURL(/#\/login\?redirect=\/users\/2/)
})
