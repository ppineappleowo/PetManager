import {test,expect} from '@playwright/test'
import {spawn} from 'node:child_process'
import {resolve} from 'node:path'
import {randomUUID} from 'node:crypto'

test.describe('真实 API 联通',()=>{
  test.skip(process.env.RUN_API_E2E!=='1','设置 RUN_API_E2E=1 并启动 PostgreSQL/Redis 后运行')
  let server,shutdownKey,output=''
  test.beforeAll(async()=>{
    shutdownKey=randomUUID()
    const python=process.env.BACKEND_PYTHON || resolve('../backend/.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python')
    server=spawn(python,['tests/browser_server.py'],{cwd:resolve('../backend'),env:{...process.env,BROWSER_TEST_SHUTDOWN_KEY:shutdownKey},windowsHide:true})
    server.stdout.on('data',chunk=>{output+=chunk})
    server.stderr.on('data',chunk=>{output+=chunk})
    for(let attempt=0;attempt<100;attempt++){
      if(server.exitCode!==null)throw new Error('隔离后端启动失败：'+output.slice(-2000))
      try{if((await fetch('http://127.0.0.1:8013/health/database')).ok)return}catch{}
      await new Promise(resolve=>setTimeout(resolve,200))
    }
    throw new Error('隔离后端启动超时：'+output.slice(-2000))
  })
  test.afterAll(async()=>{
    if(!server || server.exitCode!==null)return
    const exited=new Promise(resolve=>server.once('exit',resolve))
    await fetch('http://127.0.0.1:8013/__test__/shutdown',{method:'POST',headers:{Authorization:'Bearer '+shutdownKey}}).catch(()=>{})
    await Promise.race([exited,new Promise(resolve=>setTimeout(resolve,10000))])
    if(server.exitCode===null){server.kill();throw new Error('测试后端未正常关闭，请检查隔离 schema 清理')}
  })
  test('真实登录、发布、搜索与独立历史读取',async({page,request})=>{
    await page.route('**/config.js',route=>route.fulfill({contentType:'application/javascript',body:"window.APP_CONFIG={apiBaseUrl:'http://127.0.0.1:8013'}"}))
    await page.goto('/#/login')
    await page.getByLabel('手机号或用户名',{exact:true}).fill('browser_user')
    await page.getByLabel('密码',{exact:true}).fill('BrowserTest123')
    await page.locator('form').getByRole('button',{name:'登 录',exact:true}).click()
    await expect(page).toHaveURL(/\/#\/$/)
    await page.goto('/#/publish')
    await page.getByLabel('标题',{exact:false}).fill('真实联通的宠物日常')
    await page.getByLabel('正文',{exact:false}).fill('浏览器提交到真实 API 并持久化到独立 PostgreSQL schema。')
    await page.getByRole('button',{name:'发布日常',exact:true}).click()
    await expect(page.getByRole('heading',{name:'真实联通的宠物日常',exact:true})).toBeVisible()
    const found=await request.get('http://127.0.0.1:8013/api/v1/community/posts?q=真实联通')
    expect((await found.json()).items).toHaveLength(1)
    const token=await page.evaluate(()=>sessionStorage.getItem('token'))
    const history=await request.get('http://127.0.0.1:8013/api/v1/chat/threads',{headers:{Authorization:'Bearer '+token}})
    expect(history.ok()).toBe(true)
    expect((await history.json()).threads).toEqual([])
    expect((await (await request.get('http://127.0.0.1:8013/health/ai')).json()).status).toBe('idle')
    expect(history.headers()['x-request-id']).toMatch(/^[a-f0-9-]{36}$/)
  })
})
