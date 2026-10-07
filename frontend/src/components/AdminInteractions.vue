<script setup>
import { ref, watch } from 'vue'
import { community, statusLabel } from '../api/community.js'
import CommunityImage from './CommunityImage.vue'
const props = defineProps({mode:String})
const rows=ref([]), total=ref(0), page=ref(0), status=ref('open'), postId=ref(''), loading=ref(false), busy=ref(false), error=ref('')
const selected=ref(null), note=ref('')
let generation=0
async function load() {
  const id=++generation; loading.value=true; error.value=''
  try {
    const params=new URLSearchParams({offset:page.value*20,status:status.value})
    if (props.mode==='comments' && postId.value) params.set('post_id',postId.value)
    const data=await community(`/admin/${props.mode}?${params}`)
    if(id!==generation) return
    rows.value=data.items; total.value=data.total
    if(page.value && !rows.value.length){ page.value--; return load() }
  } catch(e){if(id===generation) error.value=e.message}
  finally{if(id===generation) loading.value=false}
}
function open(row){selected.value=row; note.value=''; error.value=''}
async function submit(action){
  if(!note.value.trim() || busy.value) return
  busy.value=true; error.value=''
  try{
    const data=props.mode==='reports' ? {action,note:note.value} : {status:action,reason:note.value,version:selected.value.version}
    await community(`/admin/${props.mode}/${selected.value.id}`,{method:'PATCH',body:JSON.stringify(data)})
    selected.value=null; await load()
  }catch(e){error.value=e.message}finally{busy.value=false}
}
watch(()=>props.mode,()=>{page.value=0;selected.value=null;load()},{immediate:true})
</script>
<template><section class="interaction-admin">
  <form class="tools" @submit.prevent="page=0;load()"><select v-if="mode==='reports'" v-model="status" aria-label="举报状态" @change="page=0;load()"><option value="open">待处理举报</option><option value="resolved">已处理举报</option></select><input v-else v-model="postId" type="number" min="1" aria-label="按帖子编号筛选" placeholder="帖子编号（选填）"><button :disabled="loading || busy">刷新列表</button></form>
  <p v-if="error" class="error" role="alert">{{ error }}</p><p v-if="loading" role="status">正在加载…</p>
  <div v-else class="table-wrap"><table><thead><tr><th>内容</th><th>{{ mode==='reports' ? '举报情况' : '作者 / 状态' }}</th><th>操作</th></tr></thead><tbody><tr v-for="row in rows" :key="row.id"><td><b>{{ mode==='reports' ? (row.snapshot.title || row.snapshot.body).slice(0,100) : row.body.slice(0,100) }}</b><small>帖子 #{{ row.post_id }} · {{ row.created_at }} UTC</small></td><td v-if="mode==='reports'">{{ row.target_type==='post' ? '帖子' : '评论' }}举报 #{{ row.id }}<small>{{ row.reason }}</small><small>{{ row.status==='open' ? '待处理' : '已处理' }}</small></td><td v-else>{{ row.author.name }}<small>{{ statusLabel(row.status) }} · 评论 #{{ row.id }}</small></td><td><button :disabled="busy" @click="open(row)">查看处理</button></td></tr></tbody></table><p v-if="!rows.length" class="empty">暂无记录</p></div>
  <footer class="pagination"><span>共 {{ total }} 条</span><button :disabled="loading || busy || !page" @click="page--;load()">上一页</button><button :disabled="loading || busy || (page+1)*20>=total" @click="page++;load()">下一页</button></footer>
  <div v-if="selected" class="overlay"><section class="dialog" v-focus-trap role="dialog" aria-modal="true" aria-label="互动管理"><header><h2>{{ mode==='reports' ? '举报处理' : '评论管理' }}</h2><button :disabled="busy" @click="selected=null">关闭</button></header>
    <template v-if="mode==='reports'"><p><b>举报原因：</b>{{ selected.reason }}</p><small>举报人 #{{ selected.user_id }} · {{ selected.created_at }} UTC</small><h3>举报时的内容</h3><p v-if="selected.snapshot.title">{{ selected.snapshot.title }}</p><pre>{{ selected.snapshot.body }}</pre><h3>当前内容 · {{ statusLabel(selected.target.status) }}</h3><pre>{{ selected.target.body }}</pre><div class="images" v-if="selected.target_type==='post'"><CommunityImage v-for="id in selected.target.images" :key="id" :private-path="`/api/v1/community/admin/posts/${selected.post_id}/images/${id}`" /></div><p v-if="selected.status==='resolved'">{{ selected.resolution==='hide' ? '已处理违规内容（下架或已不可见）' : '已驳回举报' }}<br>处理人 #{{ selected.actor_id }} · {{ selected.resolved_at }} UTC<br>{{ selected.note }}</p></template>
    <template v-else><p>{{ selected.author.name }} · {{ statusLabel(selected.status) }}</p><pre>{{ selected.body }}</pre><h3>操作记录</h3><p v-if="!selected.audit.length">暂无管理操作</p><p v-for="(event,i) in selected.audit" :key="i"><small>管理员 #{{ event.actor_id }} · {{ event.created_at }} UTC · {{ statusLabel(event.action) }}</small>{{ event.reason }}</p></template>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <form v-if="mode==='reports' ? selected.status==='open' : selected.status!=='deleted'" @submit.prevent><p v-if="mode==='reports'">处理说明会展示给举报人，请说明核查结论，不要填写内部信息或他人隐私。</p><label for="interaction-note">处理说明</label><textarea id="interaction-note" v-model="note" :maxlength="mode==='reports' ? 500 : 300" required :disabled="busy"></textarea><footer><template v-if="mode==='reports'"><button :disabled="busy || !note.trim()" @click="submit('dismiss')">驳回举报</button><button :disabled="busy || !note.trim()" @click="submit('hide')">确认违规并处理</button></template><button v-else :disabled="busy || !note.trim()" @click="submit(selected.status==='hidden' ? 'published' : 'hidden')">{{ selected.status==='hidden' ? '恢复评论' : '下架评论' }}</button></footer></form>
  </section></div>
</section></template>
<style scoped>
.interaction-admin{font-size:13px}.tools{display:flex;gap:12px;margin-bottom:20px}input,select,textarea{font:inherit;padding:10px;border:1px solid var(--line);border-radius:8px;background:white;color:var(--ink);max-width:100%}button{font:inherit;font-size:12px;color:#416c49;border:1px solid var(--line);border-radius:8px;padding:9px 13px;background:white;cursor:pointer;white-space:nowrap}.table-wrap{overflow:auto;background:white;border:1px solid var(--line);border-radius:12px}table{width:100%;border-collapse:collapse;text-align:left}th,td{padding:16px;border-bottom:1px solid var(--line);max-width:420px;overflow-wrap:anywhere}th{background:#f1f5ed}small{display:block;font-size:11px;color:#919e86;line-height:1.8;margin-top:8px}.pagination,footer{display:flex;gap:12px;align-items:center;justify-content:flex-end;margin-top:20px}.error{background:#fff0e8;color:#af6d50;padding:12px;border-radius:8px;margin:14px 0}.empty{padding:30px;color:#89997d}.overlay{position:fixed;inset:0;background:#263f2a77;z-index:100;display:grid;place-items:center;padding:18px}.dialog{background:white;border-radius:18px;padding:28px;width:min(740px,100%);max-height:90dvh;overflow:auto}header{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}h2{font-size:21px}h3{font-size:14px;margin:22px 0 10px}p,pre{line-height:1.8;overflow-wrap:anywhere}pre{white-space:pre-wrap;font:inherit;line-height:1.9;background:#f8faf5;padding:15px;border-radius:8px}.dialog p{margin:15px 0}textarea{display:block;width:100%;min-height:100px;margin-top:10px}.images{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.images :deep(img){height:150px;object-fit:contain}.dialog label{display:block;margin-top:20px}@media(max-width:650px){.dialog{padding:20px}.tools input{min-width:0}footer{flex-wrap:wrap}}
</style>
