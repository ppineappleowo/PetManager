import {test,expect} from '@playwright/test'

test('资料治理、操作审计、社区指标与导入任务',async({page})=>{
  await page.addInitScript(()=>{sessionStorage.setItem('token','test');sessionStorage.setItem('username','admin')})
  let hidden=0,version=1,job=null
  await page.route('**/api/v1/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname
    const headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'*'}
    const json=data=>route.fulfill({headers,contentType:'application/json',body:JSON.stringify(data)})
    if(req.method()==='OPTIONS')return route.fulfill({headers,status:204})
    if(path.endsWith('/auth/me'))return json({id:1,username:'admin',role:'admin'})
    if(path.endsWith('/overview'))return json({users:2,knowledge:{document_count:1},config:{}})
    if(path.endsWith('/admin/users'))return json({items:[{id:2,username:'bob',nickname:'宠物家长',bio:'简介',profile_hidden:hidden,profile_version:version,avatar_id:''}],total:1})
    if(path.endsWith('/moderation')&&req.method()==='PATCH'){hidden=+req.postDataJSON().hidden;version++;return json({success:true})}
    if(path.endsWith('/governance'))return json({items:[{id:1,kind:'profile',target_id:2,actor_id:1,owner_id:2,reason:'资料不合适',before_state:{profile_hidden:0},after_state:{profile_hidden:1}}],next_cursor:null})
    if(path.endsWith('/community-metrics'))return json({published_posts:5,posting_users:2,reply_coverage:0.6,open_reports:1})
    if(path.endsWith('/knowledge-jobs')){
      if(req.method()==='POST'){job={id:'job1',source:req.postDataJSON().source,status:'queued'};return json(job)}
      return json({items:job?[job]:[],total:job?1:0})
    }
    if(path.endsWith('/run')){job.status='completed';return json({status:'completed'})}
    if(path.endsWith('/knowledge-versions'))return json({active:'v2',items:['v2','v1']})
    return json({items:[],total:0,next_cursor:null})
  })
  await page.goto('/#/admin')
  await page.getByRole('button',{name:'资料治理',exact:true}).click()
  await page.getByRole('button',{name:'隐藏资料',exact:true}).click()
  await page.getByLabel('处理原因',{exact:true}).fill('资料不合适')
  await page.getByRole('button',{name:'确认处理'}).click()
  await expect(page.getByRole('button',{name:'恢复资料',exact:true})).toBeVisible()
  await page.getByRole('button',{name:'操作审计',exact:true}).click()
  await expect(page.getByText('资料不合适')).toBeVisible()
  await page.getByRole('button',{name:'社区指标',exact:true}).click()
  await expect(page.getByText('60.0%')).toBeVisible()
  await page.getByRole('button',{name:'导入任务',exact:true}).click()
  await page.getByLabel('来源名称').fill('猫咪资料')
  await page.getByLabel('源文本',{exact:true}).fill('学习猫咪养护知识')
  await page.getByRole('button',{name:'创建导入任务'}).click()
  await page.getByRole('button',{name:'执行导入'}).click()
  await expect(page.getByText('已完成',{exact:false})).toBeVisible()
  await expect(page.getByText('当前版本')).toBeVisible()
  await page.setViewportSize({width:390,height:844})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await page.screenshot({path:'test-results/upgrades-admin-mobile.png',fullPage:true})
})

test('主动宠物上下文、检索来源、反馈和确认后编辑 AI 日常',async({page})=>{
  await page.addInitScript(()=>{sessionStorage.setItem('token','test');sessionStorage.setItem('username','alice')})
  let payload,feedback,posts=0
  await page.route('**/api/v1/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname
    const headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'*'}
    const json=data=>route.fulfill({headers,contentType:'application/json',body:JSON.stringify(data)})
    if(req.method()==='OPTIONS')return route.fulfill({headers,status:204})
    if(path.endsWith('/auth/me'))return json({id:1,username:'alice',role:'user'})
    if(path.endsWith('/me/pets'))return json({items:[{id:7,name:'奶糖'}]})
    if(path.endsWith('/threads'))return json({threads:[]})
    if(path.endsWith('/messages'))return json({messages:[]})
    if(path.endsWith('/stream')){
      payload=req.postDataJSON()
      const events=[['sources',{items:[{id:'doc1',source:'宠物知识',version:'v1',excerpt:'适量饮水'}]}],['delta',{text:'日常照顾需要适量饮水。'}],['done',{status:'completed'}]]
      return route.fulfill({headers,contentType:'text/event-stream',body:events.map(([event,data])=>`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join('')})
    }
    if(path.endsWith('/feedback')){feedback=req.postDataJSON();return json({success:true})}
    if(path.endsWith('/posts')&&req.method()==='POST'){posts++;return json({id:1})}
    return json({items:[],unread_count:0,latest_id:0,next_cursor:null})
  })
  await page.goto('/#/ai')
  await page.getByRole('combobox',{name:/本次咨询背景/}).selectOption('7')
  await page.getByLabel('宠物咨询内容').fill('它平时怎么护理？')
  await page.getByRole('button',{name:'发送消息',exact:true}).click()
  await expect(page.getByRole('button',{name:'有帮助',exact:true})).toBeVisible()
  expect(payload.pet_id).toBe(7)
  await page.getByText('检索参考资料 · 1').click()
  await expect(page.getByText('适量饮水',{exact:true})).toBeVisible()
  await page.getByRole('button',{name:'有帮助',exact:true}).click()
  await expect(page.getByRole('button',{name:'有帮助',exact:true})).toHaveAttribute('aria-pressed','true')
  expect(feedback.value).toBe('helpful')
  page.once('dialog',dialog=>dialog.accept())
  await page.getByRole('button',{name:'整理成日常'}).click()
  await expect(page.getByLabel('正文',{exact:false})).toHaveValue(/AI 辅助整理/)
  expect(posts).toBe(0)
})
