import { test, expect } from '@playwright/test'

test('游客搜索、分类与话题组合、排序分页和返回恢复', async ({ page }) => {
  const posts = [1,2,3].map(id => ({ id, title:`猫粮经验${id}`, body:'新手养宠', category: id === 3 ? 'dog' : 'cat', tags:['饮食'], images:[], author:{id:1,name:'小白'}, status:'published', created_at:'2026-09-25' }))
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url()), params = url.searchParams
    const json = data => route.fulfill({ headers:{'Access-Control-Allow-Origin':'*'}, contentType:'application/json', body:JSON.stringify(data) })
    if (url.pathname.endsWith('/topics')) return json({items:[{tag:'饮食',post_count:3}]})
    if (url.pathname.endsWith('/posts')) {
      let items = posts.filter(p => (!params.get('q') || p.title.includes(params.get('q'))) && (!params.get('category') || p.category === params.get('category')) && (!params.get('tag') || p.tags.includes(params.get('tag'))))
      const oldest = params.get('sort') === 'oldest'
      items.sort((a,b) => oldest ? a.id-b.id : b.id-a.id)
      if (params.has('before')) items = items.filter(p => oldest ? p.id > Number(params.get('before')) : p.id < Number(params.get('before')))
      return json({items:items.slice(0,1),next_cursor:items.length > 1 ? items[0].id : null})
    }
    if (/\/posts\/\d+$/.test(url.pathname)) return json(posts.find(p => p.id === Number(url.pathname.split('/').at(-1))))
    return json({items:[]})
  })
  await page.goto('/#/')
  await page.getByRole('searchbox', {name:'搜索日常'}).fill('猫粮')
  await page.getByRole('button', {name:'搜索',exact:true}).click()
  await page.getByRole('navigation', {name:'宠物分类'}).getByRole('link', {name:'猫咪',exact:true}).click()
  await page.getByRole('navigation', {name:'热门话题'}).getByRole('link').click()
  await expect(page).toHaveURL(/q=.*category=cat.*tag=/)
  await page.getByLabel('排序', {exact:true}).selectOption('oldest')
  await expect(page.locator('.post-card h2')).toHaveText('猫粮经验1')
  await page.getByRole('button', {name:'加载更多日常'}).click()
  await expect(page.locator('.post-card')).toHaveCount(2)
  await page.locator('.post-card h2').first().click()
  await expect(page).toHaveURL(/#\/posts\/1$/)
  await page.goBack()
  await expect(page.getByRole('searchbox', {name:'搜索日常'})).toHaveValue('猫粮')
  await page.getByRole('searchbox', {name:'搜索日常'}).fill('没有匹配')
  await page.getByRole('button', {name:'搜索',exact:true}).click()
  await expect(page.getByRole('heading', {name:'没有找到相关日常'})).toBeVisible()
  await page.getByRole('button', {name:'清除搜索和话题'}).click()
  await expect(page.locator('.post-card')).toHaveCount(1)
  await page.setViewportSize({width:390,height:844})
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({path:'test-results/discovery-mobile.png',fullPage:true})
})
