<script setup>
import { ref, watch } from 'vue'
import { apiJson } from '../api/client.js'
import { community } from '../api/community.js'
import CommunityImage from './CommunityImage.vue'
import { useCursorList } from '../composables/useCursorList.js'
const props = defineProps({ mode: String })
const kind = ref('community'), query = ref(''), offset = ref(0), selected = ref(null), reason = ref(''), busy = ref(false), actionError = ref(''), stats = ref(null),aiStats=ref(null)
const {items,cursor,loading,error,load} = useCursorList(before => props.mode === 'profiles'
  ? apiJson(`/api/v1/admin/users?q=${encodeURIComponent(query.value)}&offset=${offset.value}&limit=20`).then(data=>({items:data.items,next_cursor:offset.value+20<data.total?offset.value+20:null}))
  : apiJson(`/api/v1/admin/${props.mode === 'petGovernance' ? 'pets' : 'governance'}?kind=${kind.value}${before?'&before='+before:''}`))
async function refresh() {
  selected.value=null; actionError.value='';offset.value=0
  if(props.mode==='metrics') { try{stats.value=await apiJson('/api/v1/admin/community-metrics');aiStats.value=await apiJson('/api/v1/admin/ai-metrics')}catch(e){actionError.value=e.message} }
  else await load()
}
function next(){if(props.mode==='profiles'){offset.value=cursor.value;load()}else load(true)}
function open(row,field){selected.value={...row,field};reason.value='';actionError.value=''}
async function submit(){
  if(busy.value||!reason.value.trim())return
  busy.value=true;actionError.value=''
  try{
    const row=selected.value,isPet=props.mode==='petGovernance'
    await apiJson(`/api/v1/admin/${isPet?'pets':'users'}/${row.id}/moderation`,{method:'PATCH',body:JSON.stringify({field:row.field,hidden:!row[isPet?'hidden':row.field+'_hidden'],reason:reason.value,version:isPet?row.version:row.profile_version})})
    await refresh()
  }catch(e){actionError.value=e.message}finally{busy.value=false}
}
watch(()=>props.mode,refresh,{immediate:true})
const labels={published_posts:'公开帖子',posting_users:'发帖用户',published_comments:'公开评论',answered_posts:'获得他人回复的帖子',reply_coverage:'回复覆盖率',open_reports:'待处理举报',hidden_pets:'隐藏宠物档案'}
</script>
<template><section class="operations">
  <form v-if="mode==='profiles'" @submit.prevent="refresh"><input v-model="query" aria-label="搜索资料用户名" placeholder="搜索用户名"><button :disabled="busy||loading">搜索资料</button></form>
  <select v-if="mode==='audit'" v-model="kind" aria-label="审计范围" @change="refresh"><option value="community">帖子、评论与宠物</option><option value="users">资料与权限</option></select>
  <button :disabled="busy||loading" @click="refresh">刷新{{ mode==='metrics'?'指标':'记录' }}</button>
  <p v-if="error||actionError" role="alert">{{ error||actionError }}</p>
  <div v-if="mode==='metrics'&&stats" class="stats"><article v-for="(value,key) in stats" :key="key"><span>{{ labels[key] }}</span><strong>{{ key==='reply_coverage'?(value*100).toFixed(1)+'%':value }}</strong></article><p>当前状态统计；回复覆盖率只计公开帖中至少有一条他人公开评论的帖子。</p></div>
  <div v-if="mode==='metrics'&&aiStats" class="stats"><article v-for="(label,key) in {completed:'AI 完成回答',failed:'生成失败',cancelled:'用户停止',running:'正在生成',helpful:'有帮助反馈',unhelpful:'没帮助反馈'}" :key="key"><span>{{ label }}</span><strong>{{ aiStats[key]||0 }}</strong></article></div>
  <article v-for="row in items" :key="row.id" class="record">
    <template v-if="mode==='profiles'"><h2>{{ row.username }} #{{ row.id }}</h2><p>昵称：{{ row.nickname || '未填写' }} · 简介：{{ row.bio || '未填写' }}</p><CommunityImage v-if="row.avatar_id" :private-path="`/api/v1/admin/users/${row.id}/avatar`"/><button :disabled="busy" @click="open(row,'profile')">{{ row.profile_hidden?'恢复资料':'隐藏资料' }}</button><button :disabled="busy" @click="open(row,'avatar')">{{ row.avatar_hidden?'恢复头像':'隐藏头像' }}</button></template>
    <template v-else-if="mode==='petGovernance'"><h2>{{ row.name }} #{{ row.id }}</h2><p>家长 #{{ row.user_id }} · {{ row.species }} · {{ row.bio }}</p><CommunityImage v-if="row.photo_id" :private-path="`/api/v1/admin/pets/${row.id}/photo`"/><button :disabled="busy" @click="open(row,'profile')">{{ row.hidden?'恢复档案':'隐藏档案' }}</button></template>
    <template v-else><h2>{{ row.kind }} #{{ row.target_id }}</h2><p>管理员 #{{ row.actor_id }} · 用户 #{{ row.owner_id }} · {{ row.created_at }}</p><p>{{ row.reason }}</p><pre>处理前：{{ JSON.stringify(row.before_state,null,2) }}
处理后：{{ JSON.stringify(row.after_state,null,2) }}</pre></template>
  </article>
  <p v-if="loading" role="status">正在加载…</p><p v-else-if="mode!=='metrics'&&!items.length&&!error">暂无记录</p>
  <button v-if="cursor" :disabled="loading||busy" @click="next">{{ mode==='profiles'?'下一页资料':'加载更多记录' }}</button>
  <form v-if="selected" class="record" @submit.prevent="submit"><h2>处理 {{ selected.username||selected.name }}</h2><p>处理原因会展示给该用户。</p><label for="governance-reason">处理原因</label><textarea id="governance-reason" v-model="reason" maxlength="300" required :disabled="busy"></textarea><button type="button" :disabled="busy" @click="selected=null">取消</button><button :disabled="busy||!reason.trim()">确认处理</button></form>
</section></template>
<style scoped>.operations{line-height:1.8}.operations input,.operations select,.operations button,.operations textarea{font:inherit;padding:9px 12px;border:1px solid var(--line);border-radius:8px;background:white;color:var(--ink);margin:5px;max-width:100%}.operations button{cursor:pointer}.record{border:1px solid var(--line);border-radius:14px;padding:20px;margin:16px 0;background:white;overflow-wrap:anywhere}.record h2{font-size:17px}.record pre{white-space:pre-wrap;font-size:12px}.record :deep(img){max-height:140px;max-width:160px;object-fit:contain}.record textarea{display:block;width:95%;min-height:100px}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:16px;margin-top:20px}.stats article{background:white;border:1px solid var(--line);border-radius:14px;padding:20px}.stats strong{display:block;font-size:28px}.stats p{grid-column:1/-1}</style>
