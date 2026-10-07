import {test,expect} from '@playwright/test'

async function setup(page, loggedIn=true, admin=false){
  if(loggedIn) await page.addInitScript(()=>{sessionStorage.setItem('token','test');sessionStorage.setItem('username','alice')})
  const post={id:1,body:'一起交流养宠日常',title:'今天的小猫',category:'cat',tags:[],images:[],status:'published',author:{id:2,name:'小猫家长'},created_at:'2026-09-18T08:00:00Z'}
  const state={liked:false,comments:[{id:1,post_id:1,body:'它多大啦？',status:'published',author:{id:2,name:'小猫家长'},reply_to:null,created_at:post.created_at,version:1,audit:[]}],reports:[]}
  await page.route('**/api/v1/**',async route=>{
    const req=route.request(),url=new URL(req.url()),path=url.pathname
    const headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'*'}
    const json=(data,status=200)=>route.fulfill({headers,status,contentType:'application/json',body:JSON.stringify(data)})
    if(req.method()==='OPTIONS') return route.fulfill({headers,status:204})
    if(path.endsWith('/auth/me')) return json({id:1,username:'alice',role:admin?'admin':'user'})
    if(path.endsWith('/overview')) return json({users:2,admins:1,threads:0,messages:0,active:0,knowledge:{document_count:0},config:{}})
    if(path.includes('/admin/reports')){
      if(req.method()==='PATCH') {Object.assign(state.reports[0],req.postDataJSON(),{status:'resolved'});state.comments[0].status='hidden';return json({success:true})}
      const items=state.reports.filter(r=>r.status===(url.searchParams.get('status')||'open'))
      return json({items,total:items.length})
    }
    if(path.includes('/admin/comments')){
      if(req.method()==='PATCH'){Object.assign(state.comments[0],req.postDataJSON());return json({success:true})}
      return json({items:state.comments,total:state.comments.length})
    }
    if(path.endsWith('/reports')){state.reports.push({...req.postDataJSON(),id:1,post_id:1,user_id:1,status:'open',snapshot:{body:'它多大啦？'},target:state.comments[0],created_at:post.created_at});return json({id:1,status:'open'},201)}
    const counts=()=>({liked:state.liked,like_count:Number(state.liked),comment_count:state.comments.filter(c=>c.status==='published').length})
    if(path.endsWith('/interaction')) return json(counts())
    if(path.endsWith('/like')){state.liked=req.method()==='PUT';return json(counts())}
    if(path.endsWith('/posts/1')) return json({...post,...counts()})
    if(path.endsWith('/posts/1/comments')){
      if(req.method()==='POST'){
        const data=req.postDataJSON(),comment={...data,id:state.comments.length+1,post_id:1,status:'published',author:{id:1,name:'alice'},reply_author:data.reply_to?{id:2,name:'小猫家长'}:null,created_at:post.created_at}
        state.comments.push(comment); return json(comment,201)
      }
      return json({items:state.comments.map(c=>c.status==='published'?c:{...c,body:'',author:null}),next_cursor:null})
    }
    if(path.includes('/comments/') && req.method()==='DELETE'){state.comments.at(-1).status='deleted';return json({success:true})}
    return json({items:[],total:0,next_cursor:null})
  })
  return state
}

test('用户点赞取消、回复、删除与举报，手机布局可用',async({page})=>{
  const state=await setup(page)
  await page.goto('/#/posts/1')
  await expect(page.getByText('它多大啦？',{exact:true})).toBeVisible()
  await page.getByRole('button',{name:/♡ 点赞/}).click()
  await expect(page.getByRole('button',{name:/♥ 已点赞/})).toHaveAttribute('aria-pressed','true')
  await page.getByRole('button',{name:/♥ 已点赞/}).click()
  expect(state.liked).toBe(false)
  await page.locator('.comment').first().getByRole('button',{name:'回复',exact:true}).click()
  await page.getByLabel('写下回复').fill('刚满两岁！<script>bad()</script>')
  await page.getByRole('button',{name:'发表评论'}).click()
  await expect(page.locator('.comment-body').last()).toHaveText('刚满两岁！<script>bad()</script>')
  expect(state.comments[1].reply_to).toBe(1)
  page.once('dialog',d=>d.accept())
  await page.locator('.comment').last().getByRole('button',{name:'删除',exact:true}).click()
  await expect(page.getByText('这条评论已被作者删除')).toBeVisible()
  await page.locator('.comment').first().getByRole('button',{name:'举报',exact:true}).click()
  await page.getByLabel('举报原因').fill('请管理员核查内容')
  await page.getByRole('button',{name:'提交举报'}).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  expect(state.reports[0].target_type).toBe('comment')
  await page.setViewportSize({width:390,height:844})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await page.screenshot({path:'test-results/interactions-mobile.png',fullPage:true})
})

test('游客可读评论，互动先登录并保留返回地址',async({page})=>{
  await setup(page,false)
  await page.goto('/#/posts/1')
  await expect(page.getByText('它多大啦？',{exact:true})).toBeVisible()
  await expect(page.locator('#comment-body')).toHaveCount(0)
  await page.getByRole('button',{name:/♡ 点赞/}).click()
  await expect(page).toHaveURL(/login\?redirect=/)
})

test('后台处理举报并恢复评论',async({page})=>{
  const state=await setup(page,true,true)
  state.reports.push({id:1,post_id:1,user_id:2,target_type:'comment',target_id:1,reason:'需要核查',status:'open',snapshot:{body:'它多大啦？'},target:state.comments[0],created_at:'2026-09-18'})
  await page.goto('/#/admin')
  await page.getByRole('button',{name:'举报处理',exact:true}).click()
  await page.getByRole('button',{name:'查看处理'}).click()
  await expect(page.getByRole('button',{name:'确认违规并处理'})).toBeDisabled()
  await page.getByLabel('处理说明').fill('核查违规，下架评论')
  await page.getByRole('button',{name:'确认违规并处理'}).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  expect(state.comments[0].status).toBe('hidden')
  await page.getByRole('button',{name:'评论管理',exact:true}).click()
  await page.getByRole('button',{name:'查看处理'}).click()
  await page.getByLabel('处理说明').fill('复核完成，恢复公开')
  await page.getByRole('button',{name:'恢复评论'}).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  expect(state.comments[0].status).toBe('published')
})
