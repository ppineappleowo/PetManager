import { test, expect } from '@playwright/test'

async function setup(page, { loggedIn = false, role = 'user' } = {}) {
  const posts = [
    {id:2,title:'窗边的午后，是它的小小世界',body:'今天晒了很久的太阳。\n平凡的陪伴，也很珍贵。',category:'cat',tags:['晒宠日常'],images:[],author:{id:1,name:'小林与猫'},created_at:'2026-09-18T08:00:00Z',status:'published',version:1},
    {id:1,title:'第一次一起去散步',body:'走过熟悉的小路，发现不一样的风景。',category:'dog',tags:['出游'],images:[],author:{id:2,name:'山间晚风'},created_at:'2026-09-18T07:00:00Z',status:'published',version:1},
  ]
  const requests = []
  if (loggedIn) await page.addInitScript(() => { sessionStorage.setItem('token','test-token'); sessionStorage.setItem('username','alice') })
  await page.route('**/api/v1/**', async route => {
    const req = route.request(), url = new URL(req.url()), path = url.pathname
    const headers = {'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'*'}
    if (req.method() === 'OPTIONS') return route.fulfill({status:204,headers})
    requests.push({path,method:req.method(),data:req.postData()})
    const json = (data, status=200) => route.fulfill({status,headers,contentType:'application/json',body:JSON.stringify(data)})
    if (path.endsWith('/auth/me')) return json({id:1,username:'alice',nickname:'小林与猫',role})
    if (path.endsWith('/auth/login')) return json({access_token:'test-token',username:'alice'})
    if (path.endsWith('/comments')) return json({items:[],next_cursor:null})
    if (path.endsWith('/interaction')) return json({like_count:0,comment_count:0,liked:false})
    if (path.endsWith('/overview')) return json({users:2,admins:1,threads:0,messages:0,active:0,knowledge:{document_count:0},config:{}})
    if (path.endsWith('/media') && req.method() === 'POST') return json({id:'a'.repeat(32)},201)
    if (path.includes('/images/') || /\/media\/[a-f0-9]+$/.test(path)) return route.fulfill({headers,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jZXkAAAAASUVORK5CYII=','base64')})
    const id = Number(path.match(/\/(?:posts|mine)\/(\d+)$/)?.[1])
    if (id) {
      const post = posts.find(p => p.id === id)
      if (!post) return json({detail:'帖子不可用'},404)
      if (req.method() === 'PUT' || req.method() === 'PATCH') Object.assign(post,req.postDataJSON(),{version:post.version+1})
      if (req.method() === 'DELETE') posts.splice(posts.indexOf(post),1)
      return json({...post,audit:[]})
    }
    if (req.method() === 'POST' && path.endsWith('/posts')) {
      const post = {...req.postDataJSON(),id:3,author:{id:1,name:'小林与猫'},created_at:new Date().toISOString(),status:'published',version:1}
      posts.unshift(post); return json(post,201)
    }
    if (path.endsWith('/posts') || path.endsWith('/mine')) {
      const items = posts.filter(p => (!path.endsWith('/mine') || p.author.id === 1) && (!url.searchParams.get('category') || p.category === url.searchParams.get('category')))
      return json({items,total:items.length,next_cursor:null})
    }
    return json({threads:[],messages:[]})
  })
  return {posts,requests}
}

test('游客浏览全部和分类、纯文本详情、手机双列与登录返回发布页', async ({page}) => {
  await setup(page)
  await page.goto('/')
  await expect(page.locator('.post-card')).toHaveCount(2)
  await page.screenshot({path:'test-results/community-desktop.png',fullPage:true})
  await page.getByRole('navigation',{name:'宠物分类'}).getByRole('link',{name:'狗狗'}).click()
  await expect(page.locator('.post-card')).toHaveCount(1)
  await page.locator('.post-card').click()
  await expect(page.locator('.post-body')).toHaveText('走过熟悉的小路，发现不一样的风景。')
  await page.goto('/')
  await page.setViewportSize({width:390,height:844})
  await expect(page.locator('.post-card')).toHaveCount(2)
  const cards = await page.locator('.post-card').evaluateAll(nodes => nodes.map(n => n.getBoundingClientRect().x))
  expect(cards[0]).not.toBe(cards[1])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({path:'test-results/community-mobile.png',fullPage:true})
  await page.getByRole('link',{name:'发布帖子',exact:true}).click()
  await expect(page).toHaveURL(/login\?redirect=/)
  await page.getByLabel('手机号或用户名',{exact:true}).fill('alice')
  await page.getByLabel('密码',{exact:true}).fill('secret123')
  await page.getByRole('button',{name:'登 录',exact:true}).last().click()
  await expect(page).toHaveURL(/#\/publish$/)
  await expect(page.getByLabel('正文')).toBeVisible()
})

test('图文发布、编辑、离开提醒和删除完整流程', async ({page}) => {
  const state = await setup(page,{loggedIn:true})
  const errors=[]; page.on('pageerror',e => errors.push(e.message))
  await page.goto('/#/publish')
  await page.getByLabel('标题',{exact:false}).fill('我的第一篇日常')
  await page.getByLabel('正文',{exact:false}).fill('这是正文\n<script>window.bad = true</script>')
  await page.getByLabel('宠物分类',{exact:true}).selectOption('cat')
  await page.getByLabel('添加标签',{exact:false}).fill('晒宠日常')
  await page.getByRole('button',{name:'添加',exact:true}).click()
  await page.getByLabel('添加照片',{exact:true}).setInputFiles({name:'pet.png',mimeType:'image/png',buffer:Buffer.from('photo')})
  await expect(page.getByRole('button',{name:'发布日常',exact:true})).toBeEnabled()
  page.once('dialog',d => d.dismiss())
  await page.getByRole('navigation',{name:'平台导航'}).getByRole('link',{name:'社区',exact:true}).click()
  await expect(page).toHaveURL(/#\/publish$/)
  await page.screenshot({path:'test-results/community-editor.png',fullPage:true})
  await page.getByRole('button',{name:'发布日常',exact:true}).click()
  await expect(page).toHaveURL(/#\/my-posts\/3$/)
  await expect(page.locator('.post-body')).toContainText('<script>')
  expect(await page.evaluate(() => window.bad)).toBeUndefined()
  expect(state.requests.filter(r => r.method === 'POST' && r.path.endsWith('/posts'))).toHaveLength(1)
  await page.getByRole('link',{name:'编辑帖子'}).click()
  await page.getByLabel('正文',{exact:false}).fill('编辑后的日常')
  await page.getByRole('button',{name:'保存修改'}).click()
  await expect(page.locator('.post-body')).toHaveText('编辑后的日常')
  page.once('dialog',d => d.accept())
  await page.getByRole('button',{name:'删除帖子'}).click()
  await expect(page).toHaveURL(/#\/my-posts$/)
  expect(state.posts.some(p => p.id === 3)).toBe(false)
  expect(errors).toEqual([])
})

test('管理员下架必须填写原因，并可恢复公开', async ({page}) => {
  const state = await setup(page,{loggedIn:true,role:'admin'})
  await page.goto('/#/admin')
  await page.getByRole('button',{name:'社区帖子'}).click()
  await page.getByRole('button',{name:'查看与管理'}).first().click()
  await page.getByRole('button',{name:'下架帖子'}).click()
  expect(state.posts[0].status).toBe('published')
  await page.getByLabel('操作原因').fill('需要核实内容')
  await page.getByRole('button',{name:'下架帖子'}).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  expect(state.posts[0].status).toBe('hidden')
  await page.getByRole('button',{name:'查看与管理'}).first().click()
  await page.getByLabel('操作原因').fill('已完成核实')
  await page.getByRole('button',{name:'恢复公开'}).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  expect(state.posts[0].status).toBe('published')
})
