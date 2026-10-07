import { test, expect } from '@playwright/test'

async function setup(page, role = 'admin') {
  const mutations = []
  await page.addInitScript(() => { sessionStorage.setItem('token', 'test-token'); sessionStorage.setItem('username', 'alice') })
  const users = [{ id: 1, username: 'alice', role: 'admin', disabled: 0, created_at: '2026-09-17' }, { id: 2, username: 'bob', role: 'user', disabled: 0 }]
  const docs = [{ id: 'doc1', text: '猫咪养护知识', metadata: { source: '手动知识' } }]
  await page.route('**/api/v1/**', async route => {
    const req = route.request(), url = new URL(req.url())
    const headers = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*' }
    const json = data => route.fulfill({ headers, contentType: 'application/json', body: JSON.stringify(data) })
    if (req.method() === 'OPTIONS') return route.fulfill({ status: 204, headers })
    if (url.pathname.endsWith('/auth/me')) return json({ id: 1, username: 'alice', role })
    if (url.pathname.endsWith('/overview')) return json({ users: 2, admins: 1, disabled: 0, threads: 1, messages: 2, active: 0, knowledge: { document_count: 1 }, config: { llm_model: 'test-model' } })
    if (req.method() === 'PATCH') { mutations.push(req.postDataJSON()); Object.assign(users[1], req.postDataJSON()); return json({ success: true }) }
    if (url.pathname.endsWith('/admin/users')) return json({ items: users.filter(u => u.username.includes(url.searchParams.get('q') || '')), total: users.length })
    if (url.pathname.endsWith('/admin/knowledge') && req.method() === 'POST') { docs.push({ id: 'doc2', text: req.postDataJSON().text }); return json({ added: 1 }) }
    if (url.pathname.includes('/admin/knowledge/') && req.method() === 'DELETE') { docs.splice(docs.findIndex(d => url.pathname.endsWith(d.id)), 1); return json({ success: true }) }
    if (url.pathname.endsWith('/admin/knowledge')) return json({ items: docs, total: docs.length })
    if (url.pathname.endsWith('/threads')) return json({ threads: [], items: [], total: 0 })
    if (url.pathname.endsWith('/messages')) return json({ messages: [] })
    return json({ items: [], total: 0, next_cursor: null })
  })
  return mutations
}

test('管理员概览、用户操作确认、知识增删', async ({ page }) => {
  const mutations = await setup(page)
  await page.goto('/#/admin')
  await expect(page.getByText('test-model')).toBeVisible()
  await page.screenshot({ path: 'test-results/admin-desktop.png', fullPage: true })
  await page.getByRole('button', { name: '用户管理' }).click()
  const bob = page.getByRole('row').filter({ hasText: 'bob' })
  await bob.getByRole('button', { name: '禁用', exact: true }).click()
  expect(mutations).toHaveLength(0)
  await page.getByRole('dialog').getByRole('button', { name: '取消' }).click()
  await bob.getByRole('button', { name: '禁用', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: '确认', exact: true }).click()
  await expect(bob.getByText('已禁用')).toBeVisible()
  expect(mutations).toEqual([{ disabled: true }])
  await page.getByRole('button', { name: '知识库管理' }).click()
  await page.getByLabel('知识内容').fill('新增养护知识')
  await page.getByRole('button', { name: '添加到知识库' }).click()
  await expect(page.locator('.knowledge-list').getByText('新增养护知识')).toBeVisible()
  await page.locator('.knowledge-list article').filter({ hasText: '新增养护知识' }).getByRole('button', { name: '删除' }).click()
  await page.getByRole('dialog').getByRole('button', { name: '确认', exact: true }).click()
  await expect(page.locator('.knowledge-list').getByText('新增养护知识')).toHaveCount(0)
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole('button', { name: '知识库管理' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/admin-mobile.png', fullPage: true })
})

test('普通用户直接访问后台会返回社区页', async ({ page }) => {
  await setup(page, 'user')
  await page.goto('/#/admin')
  await expect(page).toHaveURL(/#\/$/)
  await expect(page.getByRole('button', { name: '管理后台', exact: true })).toHaveCount(0)
})
