<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiJson } from '../api/client.js'
import { auth } from '../composables/useAuth.js'
import AdminInteractions from '../components/AdminInteractions.vue'
import AdminPosts from '../components/AdminPosts.vue'
import AdminOperations from '../components/AdminOperations.vue'
import KnowledgeJobs from '../components/KnowledgeJobs.vue'
import { toast } from '../composables/useToast.js'

const router = useRouter()
const tabs = { overview: '运行概览', posts: '社区帖子', comments: '评论管理', reports: '举报处理', users: '用户管理', profiles:'资料治理',petGovernance:'宠物治理',audit:'操作审计',metrics:'社区指标',threads: '会话管理', knowledge: '知识库管理',jobs:'导入任务' }
const tab = ref('overview'), overview = ref(null), rows = ref([]), total = ref(0), page = ref(0), query = ref('')
const busy = ref(false), loading = ref(false), error = ref(''), detail = ref(null), text = ref(''), pending = ref(null)
const lifetime = new AbortController()
let version = 0
const pages = computed(() => Math.max(1, Math.ceil(total.value / 20)))
const configLabels = { llm_model: '回答模型', embedding_model: '向量模型', rerank_model: '重排模型', chat_timeout_seconds: '生成超时（秒）', login_max_attempts: '账号登录次数上限', login_ip_max_attempts: 'IP 登录次数上限', login_window_seconds: '限流窗口（秒）' }
const request = (path, options = {}) => apiJson('/api/v1/admin' + path, { signal: lifetime.signal, ...options })
function failure(reason) {
  if (reason.name === 'AbortError') return
  error.value = reason.message
  if (reason.status === 403) { toast('管理员权限已失效', 'error'); router.replace('/') }
}
async function load() {
  if (['posts','comments','reports','profiles','petGovernance','audit','metrics','jobs'].includes(tab.value)) return
  const id = ++version
  loading.value = true; error.value = ''; rows.value = []
  try {
    const data = await request(tab.value === 'overview' ? '/overview' : `/${tab.value}?offset=${page.value * 20}&limit=20&q=${encodeURIComponent(query.value)}`)
    if (id !== version) return
    if (tab.value === 'overview') overview.value = data
    else {
      total.value = data.total
      if (page.value > 0 && page.value * 20 >= data.total) { page.value--; return await load() }
      rows.value = data.items
    }
  } catch (reason) { if (id === version) failure(reason) }
  finally { if (id === version) loading.value = false }
}
function select(name) { if (busy.value) return; tab.value = name; page.value = 0; query.value = ''; detail.value = null; load() }
function paginate(delta) { page.value += delta; load() }
function ask(title, action) { pending.value = { title, action } }
async function execute(action) {
  if (busy.value) return
  busy.value = true; error.value = ''
  try { await action(); pending.value = null; toast('操作成功'); await load() }
  catch (reason) { failure(reason) }
  finally { busy.value = false }
}
function update(user, values, label) {
  ask(`${label}「${user.username}」？`, () => request(`/users/${user.id}`, { method: 'PATCH', body: JSON.stringify(values) }))
}
function threadPath(thread, suffix) { return `/users/${thread.user_id}/${suffix}?thread_id=${encodeURIComponent(thread.thread_id)}` }
async function viewThread(thread) {
  busy.value = true; error.value = ''
  try { detail.value = { title: `${thread.username} · ${thread.title}`, messages: (await request(threadPath(thread, 'messages'))).messages } }
  catch (reason) { failure(reason) } finally { busy.value = false }
}
function addKnowledge() {
  if (!text.value.trim()) return
  execute(async () => { await request('/knowledge', { method: 'POST', body: JSON.stringify({ text: text.value }) }); text.value = ''; page.value = 0 })
}
onMounted(load)
onBeforeUnmount(() => { version++; lifetime.abort() })
</script>

<template>
  <div class="admin-shell">
    <aside class="admin-nav">
      <div class="brand">🐾 <span>百宠集<small>ADMIN CONSOLE</small></span></div>
      <nav aria-label="后台导航"><button v-for="(label, key) in tabs" :key="key" :class="{ selected: tab === key }" :disabled="busy" @click="select(key)">{{ label }} <span aria-hidden="true">›</span></button></nav>
      <div class="nav-bottom"><span>{{ auth.username }} · 管理员</span><button :disabled="busy" @click="router.push('/')">← 返回社区</button></div>
    </aside>
    <main class="admin-main">
      <header><div><p class="eyebrow">AI PET MANAGER / ADMIN</p><h1>{{ tabs[tab] }}</h1><p class="muted">集中查看和管理用户、会话与知识内容</p></div><button :disabled="busy || loading" @click="load">刷新数据</button></header>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p v-if="loading" role="status" class="empty">正在加载…</p>
      <template v-else-if="tab === 'overview' && overview">
        <p v-if="overview.ai_status && overview.ai_status !== 'ready'" class="muted" role="status">AI 尚未就绪，会话、消息和知识统计暂未加载；进入会话或知识管理后会尝试初始化。社区与用户管理可正常使用。</p>
        <div class="metrics"><article v-for="(label, key) in { users: '注册用户', threads: '历史会话', messages: '消息总数', active: '正在生成' }" :key="key"><span>{{ label }}</span><strong>{{ overview[key] }}</strong></article></div>
        <div class="overview-grid"><section class="panel"><h2>知识与账号</h2><dl><div><dt>知识片段</dt><dd>{{ overview.knowledge.document_count ?? 'AI 尚未就绪' }}</dd></div><div><dt>管理员</dt><dd>{{ overview.admins }}</dd></div><div><dt>已禁用账号</dt><dd>{{ overview.disabled }}</dd></div></dl></section><section class="panel"><h2>当前运行配置 <small>只读</small></h2><dl><div v-for="(value, key) in overview.config" :key="key"><dt>{{ configLabels[key] }}</dt><dd>{{ value }}</dd></div></dl></section></div>
      </template>
      <AdminPosts v-else-if="tab === 'posts'" /><AdminInteractions v-else-if="tab === 'comments' || tab === 'reports'" :mode="tab" />
      <AdminOperations v-else-if="['profiles','petGovernance','audit','metrics'].includes(tab)" :mode="tab" />
      <KnowledgeJobs v-else-if="tab==='jobs'" />
      <template v-else-if="tab !== 'overview'">
        <form v-if="tab !== 'knowledge'" class="toolbar" @submit.prevent="page = 0; load()"><input v-model="query" :placeholder="tab === 'users' ? '搜索用户名' : '搜索用户名或会话标题'" aria-label="搜索" /><button :disabled="busy || loading">搜索</button></form>
        <section v-if="tab === 'knowledge'" class="panel knowledge-form"><h2>添加知识文本</h2><p class="muted">内容将写入当前 Chroma 知识索引。这里管理的是知识片段；本地原始文件发生变化时，启动重建索引可能覆盖这些修改。</p><form @submit.prevent="addKnowledge"><textarea v-model="text" maxlength="50000" required aria-label="知识内容" placeholder="粘贴需要用于问答的宠物养护知识…" :disabled="busy"></textarea><button class="primary" :disabled="busy || !text.trim()">{{ busy ? '处理中…' : '添加到知识库' }}</button></form></section>
        <div class="panel table-wrap" v-if="tab === 'users'"><table><thead><tr><th>用户</th><th>角色</th><th>状态</th><th>注册时间</th><th>操作</th></tr></thead><tbody><tr v-for="user in rows" :key="user.id"><td><b>{{ user.username }}</b><small>#{{ user.id }}</small></td><td>{{ user.role === 'admin' ? '管理员' : '普通用户' }}</td><td><span class="badge" :class="{ danger: user.disabled }">{{ user.disabled ? '已禁用' : '正常' }}</span></td><td>{{ user.created_at }}</td><td class="actions"><button :disabled="busy || user.username === auth.username" @click="update(user, { role: user.role === 'admin' ? 'user' : 'admin' }, user.role === 'admin' ? '降为普通用户' : '设为管理员')">{{ user.role === 'admin' ? '降级' : '设为管理员' }}</button><button :disabled="busy || user.username === auth.username" @click="update(user, { disabled: !user.disabled }, user.disabled ? '启用' : '禁用')">{{ user.disabled ? '启用' : '禁用' }}</button><button :disabled="busy" @click="update(user, { revoke: true }, '使全部登录失效并停止生成')">强制退出</button></td></tr></tbody></table></div>
        <div class="panel table-wrap" v-if="tab === 'threads'"><table><thead><tr><th>会话</th><th>用户</th><th>消息</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="thread in rows" :key="`${thread.user_id}:${thread.thread_id}`"><td><b>{{ thread.title || '图片咨询' }}</b><small>{{ thread.thread_id }}</small></td><td>{{ thread.username }}</td><td>{{ thread.message_count }}</td><td>{{ thread.running ? '生成中' : '空闲' }}</td><td class="actions"><button :disabled="busy" @click="viewThread(thread)">查看</button><button v-if="thread.running" :disabled="busy" @click="ask('停止此会话的生成？', () => request(threadPath(thread, 'stop'), { method: 'POST' }))">停止</button><button class="danger" :disabled="busy || thread.running" @click="ask('永久删除此会话及全部消息？此操作无法撤销。', () => request(threadPath(thread, 'messages'), { method: 'DELETE' }))">删除</button></td></tr></tbody></table></div>
        <section v-if="tab === 'knowledge'" class="knowledge-list"><article class="panel" v-for="doc in rows" :key="doc.id"><div class="doc-head"><small>{{ doc.metadata?.source || '手动知识' }} · {{ doc.id }}</small><button class="danger" :disabled="busy" @click="ask('删除此知识片段？此操作无法撤销。', () => request(`/knowledge/${encodeURIComponent(doc.id)}`, { method: 'DELETE' }))">删除</button></div><pre>{{ doc.text }}</pre></article></section>
        <p v-if="!rows.length && !loading" class="empty">暂无符合条件的数据</p>
        <footer class="pagination"><span>共 {{ total }} 条 · 第 {{ page + 1 }} / {{ pages }} 页</span><button :disabled="busy || loading || page === 0" @click="paginate(-1)">上一页</button><button :disabled="busy || loading || page + 1 >= pages" @click="paginate(1)">下一页</button></footer>
      </template>
    </main>
    <div v-if="pending" class="modal-overlay"><section class="dialog" v-focus-trap role="dialog" aria-modal="true" aria-labelledby="confirm-title"><h2 id="confirm-title">确认操作</h2><p>{{ pending.title }}</p><p v-if="error" class="error">{{ error }}</p><div class="actions"><button :disabled="busy" @click="pending = null">取消</button><button class="primary" :disabled="busy" @click="execute(pending.action)">{{ busy ? '处理中…' : '确认' }}</button></div></section></div>
    <div v-if="detail" class="modal-overlay"><section class="dialog history" v-focus-trap role="dialog" aria-modal="true" aria-labelledby="history-title"><header><h2 id="history-title">{{ detail.title }}</h2><button @click="detail = null">关闭</button></header><p v-if="!detail.messages.length">暂无消息</p><article v-for="(message, index) in detail.messages" :key="index"><b>{{ message.role === 'user' ? '用户' : 'AI' }} · {{ message.status || 'completed' }}</b><pre>{{ typeof message.content === 'string' ? message.content : JSON.stringify(message.content, null, 2) }}</pre><a v-if="/^https?:\/\//i.test(message.image_url || '')" :href="message.image_url" target="_blank" rel="noopener noreferrer">查看图片</a><p v-if="message.error" class="error">{{ message.error }}</p></article></section></div>
  </div>
</template>

<style scoped>
.admin-shell{min-height:100dvh;background:#f5f7f9;color:#20332c;display:flex;font-family:inherit}.admin-nav{width:230px;flex-shrink:0;background:#102e27;color:#e7f4ed;padding:30px 20px;display:flex;flex-direction:column;min-height:100dvh}.brand{display:flex;gap:12px;font-size:22px;font-weight:700;margin-bottom:48px}.brand small{font-size:10px;letter-spacing:2px;color:#9cbab0;margin-top:7px}small{display:block;font-size:12px;color:#718078;font-weight:400;overflow-wrap:anywhere}nav{display:grid;gap:10px}nav button{display:flex;justify-content:space-between;color:#bfd6cd;background:transparent;border:0;text-align:left;padding:14px}nav button.selected{background:#245546;color:white}.nav-bottom{margin-top:auto;padding-top:40px;display:grid;gap:15px;font-size:13px}.admin-main{padding:40px;flex:1;min-width:0;max-width:1500px}header{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:28px}h1{font-size:28px;margin:8px 0}h2{font-size:17px;margin-bottom:18px}.eyebrow{font-size:11px;letter-spacing:2px;color:#638675}.muted{color:#76847c;font-size:13px;line-height:1.8}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin-bottom:24px}.metrics article,.panel{background:white;border:1px solid #e2e9e5;border-radius:14px;padding:24px}.metrics span{color:#738479;font-size:13px}.metrics strong{display:block;font-size:34px;margin-top:18px}.overview-grid{display:grid;grid-template-columns:1fr 1.5fr;gap:24px}dl>div{display:flex;justify-content:space-between;gap:20px;border-bottom:1px solid #eef2ef;padding:14px 0;font-size:13px}dt{color:#76847c}dd{overflow-wrap:anywhere;text-align:right}button{border:1px solid #d8e4dd;background:white;color:#315746;border-radius:8px;padding:9px 13px;cursor:pointer;font:inherit;font-size:13px}button:disabled{opacity:.45;cursor:not-allowed}button.primary{background:#187655;color:white;border-color:#187655}.danger{color:#bc3b43}.badge{background:#e8f6ee;color:#21734d;border-radius:20px;padding:4px 10px;font-size:12px}.badge.danger{background:#ffeded;color:#bc3b43}.toolbar{display:flex;gap:10px;margin-bottom:20px}input,textarea{border:1px solid #d8e4dd;border-radius:8px;padding:11px;font:inherit;background:white}input{width:min(400px,100%)}textarea{width:100%;min-height:120px;margin:14px 0;resize:vertical}.knowledge-form{margin-bottom:24px}.table-wrap{overflow-x:auto;padding:0}table{width:100%;border-collapse:collapse;text-align:left;font-size:13px}th{background:#f9fbfa;color:#75847c;font-weight:500}td,th{padding:16px;border-bottom:1px solid #edf1ee}td{max-width:290px;overflow-wrap:anywhere}td small{margin-top:7px}.actions{display:flex;gap:8px;flex-wrap:wrap}.pagination{display:flex;justify-content:flex-end;align-items:center;gap:12px;margin-top:22px;font-size:13px;color:#718078}.knowledge-list{display:grid;gap:14px}.doc-head{display:flex;justify-content:space-between;gap:16px;margin-bottom:14px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;font-size:14px;line-height:1.8;max-height:300px;overflow:auto}.error{background:#fff0ef;color:#b33236;padding:12px;border-radius:8px;margin-bottom:16px}.empty{text-align:center;color:#76847c;padding:35px}.modal-overlay{position:fixed;inset:0;background:#10251d80;display:grid;place-items:center;padding:20px;z-index:100}.dialog{background:white;padding:28px;border-radius:16px;width:min(460px,100%);max-height:85dvh;overflow:auto}.dialog p{margin:18px 0}.dialog.history{width:min(850px,100%)}.history article{border-top:1px solid #e4ebe7;padding:20px 0}.history h2{margin:0}button:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid #80c8af;outline-offset:2px}@media(max-width:1000px){.admin-main{padding:24px}.admin-nav{width:180px}.metrics{grid-template-columns:repeat(2,1fr)}.overview-grid{grid-template-columns:1fr}}@media(max-width:650px){.admin-shell{display:block}.admin-nav{width:100%;min-height:auto;padding:16px}.brand{margin-bottom:16px}.brand small{display:none}nav{grid-template-columns:repeat(4,1fr);gap:4px}nav button{padding:10px 4px;font-size:12px}nav button span{display:none}.nav-bottom{padding-top:15px;display:flex;justify-content:space-between;align-items:center}.admin-main{padding:20px 14px}header{align-items:flex-start}h1{font-size:24px}.metrics{gap:10px}.metrics article,.panel{padding:16px}.table-wrap{padding:0}.pagination{flex-wrap:wrap}}

.admin-shell{background:var(--app-bg);color:var(--ink)}.admin-nav{background:#243f32}.panel,.metrics article{border-color:var(--line);box-shadow:0 3px 15px #283b2c03}.metrics strong{color:#386a50}button.primary{background:#386a50;border-color:#386a50}.selected{border-radius:10px}.eyebrow{color:#7c927c}
</style>
