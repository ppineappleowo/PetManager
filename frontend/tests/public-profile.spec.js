import { test, expect } from '@playwright/test'

test('头像更新与移除、公开主页及作者入口', async ({ page }) => {
  const user = { id: 1, username: 'alice', nickname: '小猫家长', bio: '和猫一起慢慢长大', avatar_id: '', phone: '13800138000' }
  const post = { id: 1, title: '午后的猫', body: '睡得真香', images: [], tags: ['日常'], category: 'cat', status: 'published', created_at: '2026-09-18T00:00:00Z', author: { id: 1, name: '小猫家长' } }
  await page.addInitScript(() => { sessionStorage.setItem('token', 'test'); sessionStorage.setItem('username', 'alice') })
  await page.route('**/api/v1/**', async route => {
    const req = route.request(), path = new URL(req.url()).pathname
    const headers = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*' }
    const json = data => route.fulfill({ headers, contentType: 'application/json', body: JSON.stringify(data) })
    if (req.method() === 'OPTIONS') return route.fulfill({ status: 204, headers })
    if (path.endsWith('/auth/me')) return json(user)
    if (path.endsWith('/me/avatar')) { user.avatar_id = req.method() === 'PUT' ? 'avatar123' : ''; return json({ avatar_id: user.avatar_id }) }
    if (path.includes('/avatar/')) return route.fulfill({ headers, contentType:'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1sAAAAASUVORK5CYII=', 'base64') })
    if (path.endsWith('/users/1')) return json({ id: 1, name: user.nickname, bio: user.bio, avatar_id: user.avatar_id, post_count: 1 })
    if (path.endsWith('/posts')) return json({ items: [post], next_cursor: null })
    return json({})
  })
  await page.goto('/#/profile')
  await page.getByLabel('上传头像').setInputFiles({ name:'avatar.png', mimeType:'image/png', buffer:Buffer.from('mock upload') })
  await expect(page.getByRole('button', { name: '移除头像' })).toBeVisible()
  await expect(page.locator('.profile-avatar img')).toBeVisible()
  await page.getByRole('link', { name: '查看我的公开主页' }).click()
  await expect(page.getByRole('heading', { name:'小猫家长' })).toBeVisible()
  await expect(page.getByText('13800138000')).toHaveCount(0)
  await expect(page.getByText('1 篇公开日常')).toBeVisible()
  await page.setViewportSize({ width:390, height:844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path:'test-results/public-profile-mobile.png', fullPage:true })
  await page.goto('/#/profile')
  await page.getByRole('button', { name:'移除头像' }).click()
  await expect(page.locator('.profile-avatar img')).toHaveCount(0)
  await page.goto('/#/')
  await page.getByRole('link', { name:'小猫家长', exact:true }).click()
  await expect(page).toHaveURL(/#\/users\/1$/)
})

test('游客可读主页、错误可重试、空主页正常展示', async ({ page }) => {
  let failed = true
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    const headers = { 'Access-Control-Allow-Origin':'*' }
    if (failed) return route.fulfill({ status:404, headers, contentType:'application/json', body:JSON.stringify({ detail:'用户主页不可用' }) })
    return route.fulfill({ headers, contentType:'application/json', body:JSON.stringify(path.endsWith('/posts') ? { items:[],next_cursor:null } : {id:2,name:'新宠友',bio:'',post_count:0}) })
  })
  await page.goto('/#/users/2')
  await expect(page.getByRole('alert')).toContainText('用户主页不可用')
  failed = false
  await page.getByRole('button', { name:'重新加载' }).click()
  await expect(page.getByText('还没有公开日常，期待下一次分享。')).toBeVisible()
})
