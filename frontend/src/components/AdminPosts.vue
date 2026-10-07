<script setup>
import { onMounted, ref } from 'vue'
import { community, statusLabel, categories } from '../api/community.js'
import CommunityImage from './CommunityImage.vue'
const rows = ref([]), total = ref(0), page = ref(0), query = ref(''), loading = ref(false), error = ref(''), selected = ref(null), reason = ref(''), busy = ref(false)
async function load() {
  loading.value = true; error.value = ''
  try { const data = await community(`/admin/posts?offset=${page.value * 20}&q=${encodeURIComponent(query.value)}`); rows.value = data.items; total.value = data.total }
  catch (e) { error.value = e.message }
  finally { loading.value = false }
}
async function view(post) {
  busy.value = true; error.value = ''
  try { selected.value = await community(`/admin/posts/${post.id}`); reason.value = '' }
  catch(e) { error.value = e.message }
  finally { busy.value = false }
}
async function moderate(status) {
  if (!reason.value.trim()) { error.value = '请填写下架或恢复原因'; return }
  busy.value = true
  try {
    await community(`/admin/posts/${selected.value.id}`, {method:'PATCH',body:JSON.stringify({status,reason:reason.value,version:selected.value.version})})
    selected.value = null; await load()
  } catch(e) { error.value = e.message }
  finally { busy.value = false }
}
onMounted(load)
</script>
<template><section class="admin-posts"><form class="search" @submit.prevent="page = 0; load()"><input v-model="query" maxlength="100" aria-label="搜索帖子" placeholder="搜索标题或正文"><button :disabled="loading || busy">搜索</button></form><p v-if="error" class="error" role="alert">{{ error }}</p><p v-if="loading">正在加载帖子…</p><div v-else class="table-wrap"><table><thead><tr><th>帖子</th><th>作者 / 分类</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="post in rows" :key="post.id"><td><b>{{ post.title || post.body.slice(0,50) }}</b><small>#{{ post.id }} · {{ new Date(post.created_at).toLocaleString('zh-CN') }}</small></td><td>{{ post.author.name }}<small>{{ categories[post.category] }}</small></td><td>{{ statusLabel(post.status) }}</td><td><button :disabled="busy" @click="view(post)">查看与管理</button></td></tr></tbody></table><p v-if="!rows.length">暂无帖子</p></div><footer><span>共 {{ total }} 条</span><button :disabled="loading || page === 0" @click="page--; load()">上一页</button><button :disabled="loading || (page + 1) * 20 >= total" @click="page++; load()">下一页</button></footer><div v-if="selected" class="overlay"><section class="post-dialog" v-focus-trap role="dialog" aria-modal="true" aria-label="帖子管理"><header><h2>{{ selected.title || '无标题帖子' }}</h2><button :disabled="busy" @click="selected = null">关闭</button></header><p class="body">{{ selected.body }}</p><div class="images"><CommunityImage v-for="id in selected.images" :key="id" :private-path="`/api/v1/community/admin/posts/${selected.id}/images/${id}`" /></div><p>状态：{{ statusLabel(selected.status) }} {{ selected.reason }}</p><p v-if="error" class="error" role="alert">{{ error }}</p><template v-if="selected.status !== 'deleted'"><label for="moderation-reason">操作原因</label><textarea id="moderation-reason" v-model="reason" maxlength="300" :disabled="busy" placeholder="请填写下架或恢复的原因"></textarea><button :disabled="busy" @click="moderate(selected.status === 'hidden' ? 'published' : 'hidden')">{{ selected.status === 'hidden' ? '恢复公开' : '下架帖子' }}</button></template><h3>操作记录</h3><p v-if="!selected.audit.length">暂无管理操作</p><p v-for="(event,index) in selected.audit" :key="index" class="audit">{{ event.created_at }} UTC · 管理员 #{{ event.actor_id }} · {{ statusLabel(event.action) }}<br>{{ event.reason }}</p></section></div></section></template>
<style scoped>
.admin-posts{font-size:14px}.search{display:flex;gap:10px;margin-bottom:20px}input,textarea{border:1px solid var(--line);border-radius:8px;padding:12px;font:inherit}input{width:min(400px,100%)}button{background:white;color:#416847;border:1px solid var(--line);border-radius:8px;padding:9px 14px;cursor:pointer;white-space:nowrap;font-size:12px}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:12px;background:white}table{width:100%;border-collapse:collapse;text-align:left}td,th{padding:17px;border-bottom:1px solid var(--line);max-width:340px;overflow-wrap:anywhere}th{background:#f0f4ed;font-weight:500}small{display:block;color:#94a18a;margin-top:8px;font-size:11px}footer{display:flex;gap:12px;align-items:center;justify-content:flex-end;margin-top:20px}.error{padding:12px;color:#b05e42;background:#fff1e7;border-radius:8px;margin-bottom:18px}.overlay{position:fixed;inset:0;background:#1c33277a;z-index:100;display:grid;place-items:center;padding:20px}.post-dialog{background:white;border-radius:18px;padding:28px;width:min(780px,100%);max-height:90dvh;overflow:auto}.post-dialog header{display:flex;gap:20px;justify-content:space-between;align-items:center}h2{font-size:20px;overflow-wrap:anywhere}h3{font-size:14px;margin-top:25px}.body{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.9;margin:25px 0}.images{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.images :deep(img){height:160px;object-fit:contain}textarea{width:100%;margin:12px 0;min-height:85px}label{display:block;margin-top:18px}.post-dialog p:not(.body){line-height:1.8;margin-top:12px}.audit{font-size:12px;color:#8b9780}
</style>
