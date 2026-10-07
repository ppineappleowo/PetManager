import { test, expect } from '@playwright/test'

test('个人中心修改资料、保存会话入口、修改密码后退出', async ({ page }) => {
  let user = { id: 1, username: 'alice', nickname: '', bio: '', phone: '13800138000', role: 'user', created_at: '2026-09-18' }
  let saved
  await page.addInitScript(() => {
    sessionStorage.setItem('token', 'test-token')
    sessionStorage.setItem('username', 'alice')
    sessionStorage.setItem('pet_manager_thread_id:alice', 'existing-thread')
  })
  await page.route('**/api/v1/**', async route => {
    const request = route.request(), path = new URL(request.url()).pathname
    const headers = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*' }
    const json = value => route.fulfill({ headers, contentType: 'application/json', body: JSON.stringify(value) })
    if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers })
    if (path.endsWith('/auth/me')) {
      if (request.method() === 'PATCH') { saved = request.postDataJSON(); user = { ...user, ...saved } }
      return json(user)
    }
    if (path.endsWith('/auth/password')) return json({ success: true })
    return json({ threads: [], messages: [] })
  })
  await page.goto('/#/profile')
  await expect(page.getByRole('heading', { name: '个人资料', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '账号与安全', exact: true }).click()
  await expect(page.getByText('13800138000')).toBeVisible()
  await page.getByRole('button', { name: '个人资料', exact: true }).click()
  await page.getByLabel('用户名', { exact: true }).fill('alice_new')
  await page.getByLabel('昵称', { exact: true }).fill('猫家长')
  await page.getByLabel('个人简介').fill('养了两只猫')
  await page.getByRole('button', { name: '保存修改' }).click()
  await expect(page.getByRole('heading', { name: '猫家长' })).toBeVisible()
  expect(saved).toEqual({ username: 'alice_new', nickname: '猫家长', bio: '养了两只猫' })
  expect(await page.evaluate(() => sessionStorage.getItem('pet_manager_thread_id:alice_new'))).toBe('existing-thread')
  await page.screenshot({ path: 'test-results/profile-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/profile-mobile.png', fullPage: true })
  await page.getByRole('button', { name: '账号与安全', exact: true }).click()
  await page.getByRole('button', { name: '修改密码', exact: true }).click()
  await page.getByLabel('原密码', { exact: true }).fill('secret123')
  await page.getByLabel('新密码', { exact: true }).fill('newsecret123')
  await page.getByLabel('确认新密码').fill('newsecret123')
  await page.getByRole('button', { name: '确认修改' }).click()
  await expect(page).toHaveURL(/#\/login(?:\?|$)/)
  expect(await page.evaluate(() => sessionStorage.getItem('token'))).toBeNull()
})
