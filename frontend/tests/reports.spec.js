import { test, expect } from '@playwright/test'

test('我的举报筛选、反馈、分页重试与移动页面', async ({ page }) => {
  await page.addInitScript(() => { sessionStorage.setItem('token', 'test'); sessionStorage.setItem('username', 'alice') })
  let failMore = true
  const record = (id, status = 'open', resolution = '', target = '/posts/1') => ({
    id, status, resolution, target, target_type: 'post', target_id: 1,
    reason: '广告内容，请核查', note: resolution === 'hide' ? '已核实为垃圾广告' : '未发现违规',
    created_at: '2026-10-03T00:00:00Z', resolved_at: status === 'resolved' ? '2026-10-03 01:00:00' : null,
  })
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url())
    const headers = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*' }
    const json = (data, status = 200) => route.fulfill({ headers, status, contentType: 'application/json', body: JSON.stringify(data) })
    if (route.request().method() === 'OPTIONS') return route.fulfill({ headers, status: 204 })
    if (url.pathname.endsWith('/auth/me')) return json({ id: 1, username: 'alice', role: 'user' })
    if (url.pathname.endsWith('/me/reports')) {
      if (url.searchParams.get('status') === 'open') return json({ items: [], next_cursor: null })
      if (url.searchParams.get('status') === 'resolved') return json({ items: [record(2, 'resolved', 'hide', null), record(1, 'resolved', 'dismiss')], next_cursor: null })
      if (url.searchParams.has('before')) {
        if (failMore) { failMore = false; return json({ detail: '暂时无法加载' }, 503) }
        return json({ items: [record(2, 'resolved', 'hide', null)], next_cursor: null })
      }
      return json({ items: [record(3)], next_cursor: 3 })
    }
    return json({ items: [], next_cursor: null, unread_count: 0, latest_id: 0 })
  })
  await page.goto('/#/reports')
  await expect(page.getByRole('heading', { name: '我的举报', exact: true })).toBeVisible()
  await expect(page.getByText('管理员尚未完成核查，请稍后刷新查看。')).toBeVisible()
  await page.getByRole('button', { name: '加载更多举报' }).click()
  await expect(page.getByRole('alert')).toContainText('暂时无法加载')
  await expect(page.locator('.report-card')).toHaveCount(1)
  await page.getByRole('button', { name: '重试加载' }).click()
  await expect(page.locator('.report-card')).toHaveCount(2)
  await expect(page.getByText('已核实为垃圾广告')).toBeVisible()
  const hidden = page.locator('.report-card').filter({ hasText: '帖子举报 #2' })
  await expect(hidden.getByRole('link')).toHaveCount(0)
  await page.getByRole('navigation', { name: '筛选举报' }).getByRole('link', { name: '已处理', exact: true }).click()
  await expect(page).toHaveURL(/status=resolved/)
  await expect(page.getByText('未采纳举报', { exact: true })).toBeVisible()
  await expect(page.locator('.report-card').filter({ hasText: '#1' }).getByRole('link')).toHaveAttribute('href', '#/posts/1')
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/reports-mobile.png', fullPage: true })
  await page.getByRole('navigation', { name: '筛选举报' }).getByRole('link', { name: '待处理', exact: true }).click()
  await expect(page.getByText('暂无这类举报记录')).toBeVisible()
  await page.goBack()
  await expect(page.getByText('未采纳举报', { exact: true })).toBeVisible()
})

test('游客查看举报需要登录并保留筛选地址', async ({ page }) => {
  await page.goto('/#/reports?status=resolved')
  await expect(page).toHaveURL(/login.*redirect=.*reports/)
})
