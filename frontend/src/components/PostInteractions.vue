<script setup>
import { loadCurrentUser } from '../composables/useCurrentUser.js'

import AuthorLink from './AuthorLink.vue'
import BookmarkButton from './BookmarkButton.vue'
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { auth } from '../composables/useAuth.js'
import { community } from '../api/community.js'
import { toast } from '../composables/useToast.js'
const props = defineProps({ post: {type:Object,required:true} })
const route = useRoute(), router = useRouter()
const comments = ref([]), cursor = ref(null), loading = ref(false), error = ref(''), sending = ref(false)
const me = ref(null), body = ref(''), replying = ref(null), likeBusy = ref(false), actionBusy = ref(false)
const counts = ref({like_count:props.post.like_count || 0,comment_count:props.post.comment_count || 0,liked:false})
const reportTarget = ref(null), reportReason = ref(''), reportBusy = ref(false), reportError = ref('')
const initializing = ref(!!auth.token)
let requestKey = crypto.randomUUID()
function login() { router.push({name:'login',query:{redirect:route.fullPath}}) }
async function load(more=false) {
  loading.value = true; error.value = ''
  try {
    const data = await community(`/posts/${props.post.id}/comments${more && cursor.value ? '?after='+cursor.value : ''}`,{authenticated:false})
    comments.value = more ? [...comments.value,...data.items] : data.items; cursor.value = data.next_cursor
  } catch(e) { error.value = e.message }
  finally { loading.value = false }
}
async function refreshCounts() {
  if (auth.token) counts.value = await community(`/posts/${props.post.id}/interaction`)
}
onMounted(async () => {
  if (props.post.status !== 'published') return
  await load()
  if (auth.token) {
    try { me.value = await loadCurrentUser(); await refreshCounts() }
    catch(e) { error.value = e.message }
  }
  initializing.value = false
})
async function toggleLike() {
  if (!auth.token) return login()
  if (likeBusy.value || initializing.value) return
  likeBusy.value = true; error.value = ''
  try { counts.value = await community(`/posts/${props.post.id}/like`,{method:counts.value.liked ? 'DELETE' : 'PUT'}) }
  catch(e) { error.value = e.message }
  finally { likeBusy.value = false }
}
function reply(comment) {
  if (!auth.token) return login()
  replying.value = comment
  document.getElementById('comment-body')?.focus()
}
async function send() {
  if (!auth.token) return login()
  if (sending.value || !body.value.trim()) return
  sending.value = true; error.value = ''
  try {
    await community(`/posts/${props.post.id}/comments`, {method:'POST',body:JSON.stringify({body:body.value,reply_to:replying.value?.id || null,request_key:requestKey})})
    body.value = ''; replying.value = null; requestKey = crypto.randomUUID()
    toast('评论已发布'); await load(); await refreshCounts()
  } catch(e) { error.value = e.message }
  finally { sending.value = false }
}
async function remove(comment) {
  if (!window.confirm('确定删除这条评论？回复会保留，正文将不再公开展示。')) return
  actionBusy.value = true; error.value = ''
  try { await community(`/comments/${comment.id}`,{method:'DELETE'}); await load(); await refreshCounts() }
  catch(e) { error.value = e.message }
  finally { actionBusy.value = false }
}
function openReport(type,id) {
  if (!auth.token) return login()
  reportTarget.value = {target_type:type,target_id:id}; reportReason.value = ''; reportError.value = ''
}
async function report() {
  if (!reportReason.value.trim() || reportBusy.value) return
  reportBusy.value = true; reportError.value = ''
  try {
    await community('/reports',{method:'POST',body:JSON.stringify({...reportTarget.value,reason:reportReason.value})})
    reportTarget.value = null; toast('举报已记录，可在个人中心的“我的举报”查看处理进度')
  } catch(e) { reportError.value = e.message }
  finally { reportBusy.value = false }
}
</script>
<template>
  <section class="post-interactions" aria-label="帖子互动">
    <p v-if="post.status !== 'published'" class="hint">帖子未公开，暂不开放评论、点赞和举报。</p>
    <template v-else>
      <BookmarkButton :post-id="post.id" />
      <div class="interaction-bar"><button class="c-button" :class="{liked:counts.liked}" :aria-pressed="counts.liked" :disabled="likeBusy || initializing" @click="toggleLike">{{ counts.liked ? '♥ 已点赞' : '♡ 点赞' }} · {{ counts.like_count }}</button><span>{{ counts.comment_count }} 条评论</span><button class="report-link" @click="openReport('post',post.id)">举报帖子</button></div>
      <h2>聊聊这份日常</h2>
      <form v-if="auth.token" class="comment-form" @submit.prevent="send"><div v-if="replying" class="reply-target">回复 {{ replying.author.name }}<button type="button" :disabled="sending" @click="replying = null">取消回复</button></div><label class="hint" for="comment-body">{{ replying ? '写下回复' : '写下评论' }}</label><textarea id="comment-body" v-model="body" maxlength="1000" required :disabled="sending" placeholder="分享你的经验，也给彼此一点善意…"></textarea><div class="comment-form-footer"><span>{{ body.length }} / 1000</span><button class="c-button primary" :disabled="sending || !body.trim()">{{ sending ? '发送中…' : '发表评论' }}</button></div></form>
      <p v-else class="login-hint"><button @click="login">登录后参与讨论</button>，让每份分享都有回应。</p>
      <div v-if="error" role="alert" class="community-error">{{ error }} <button @click="load()">刷新评论</button></div>
      <p class="hint comment-order">按发布时间排列 · 回复注明对象</p>
      <div class="comment-list"><article v-for="comment in comments" :key="comment.id" class="comment" :class="{reply:comment.reply_to}">
        <template v-if="comment.status === 'published'"><header><AuthorLink :author="comment.author" /><time>{{ new Date(comment.created_at).toLocaleString('zh-CN') }}</time></header><p v-if="comment.reply_author" class="reply-label">回复 {{ comment.reply_author.name }}</p><p class="comment-body">{{ comment.body }}</p><footer><button :disabled="sending" @click="reply(comment)">回复</button><button @click="openReport('comment',comment.id)">举报</button><button v-if="me?.id === comment.author.id" :disabled="actionBusy" @click="remove(comment)">删除</button></footer></template>
        <p v-else class="hint">{{ comment.status === 'deleted' ? '这条评论已被作者删除' : '这条评论已被管理员下架' }}</p>
      </article></div>
      <p v-if="loading" role="status" class="hint">正在加载评论…</p><p v-else-if="!comments.length && !error" class="hint empty-comments">还没有评论，来聊聊吧。</p><button v-if="cursor" class="c-button" :disabled="loading" @click="load(true)">加载更多评论</button>
    </template>
    <div v-if="reportTarget" class="report-overlay" @keydown.esc="!reportBusy && (reportTarget = null)"><form class="report-dialog" v-focus-trap role="dialog" aria-modal="true" aria-labelledby="report-title" @submit.prevent="report"><h2 id="report-title">{{ reportTarget.target_type === 'post' ? '举报帖子' : '举报评论' }}</h2><p class="hint">请具体说明问题，帮助管理员核查。举报原因仅你和管理员可见。处理进度可在<RouterLink to="/reports">我的举报</RouterLink>查看。</p><label for="report-reason">举报原因</label><textarea id="report-reason" v-model="reportReason" required maxlength="500" :disabled="reportBusy" placeholder="例如：垃圾广告、辱骂攻击、内容不当…"></textarea><p v-if="reportError" class="community-error" role="alert">{{ reportError }}</p><footer><button type="button" class="c-button" :disabled="reportBusy" @click="reportTarget = null">取消</button><button class="c-button primary" :disabled="reportBusy || !reportReason.trim()">提交举报</button></footer></form></div>
  </section>
</template>
<style scoped>
.post-interactions{margin-top:30px;padding-top:24px;border-top:1px solid var(--line)}.interaction-bar{display:flex;align-items:center;gap:16px;font-size:12px;color:#839079;margin-bottom:28px}.interaction-bar .liked{background:#f9eee9;color:#b46e62;border-color:#e7cac1}.report-link{margin-left:auto}h2{font-size:18px;margin:16px 0}.hint{font-size:12px;color:#8d9982;line-height:1.8}textarea{width:100%;min-height:100px;resize:vertical;border:1px solid var(--line);border-radius:10px;background:#fafbf7;padding:12px;font:inherit;font-size:14px;line-height:1.8;color:var(--ink);margin-top:8px}.comment-form-footer{display:flex;justify-content:space-between;align-items:center;margin-top:10px;color:#9ba58d;font-size:11px}.reply-target{font-size:12px;background:#f0f4eb;padding:10px;border-radius:8px;margin-bottom:10px}.reply-target button{float:right}.comment-order{margin:22px 0 0}.comment{padding:22px 0;border-bottom:1px solid var(--line)}.comment.reply{margin-left:20px;padding-left:14px;border-left:2px solid #e5eddf}.comment header{display:flex;gap:8px;align-items:center;font-size:12px}.comment time{margin-left:auto;color:#9ba58d;font-size:10px}.comment-body{white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px;line-height:1.8;margin-top:12px}.reply-label{font-size:11px;color:#8b9c7b;margin-top:10px}.comment footer{display:flex;gap:18px;margin-top:12px}.comment footer button,.report-link,.reply-target button,.login-hint button{background:transparent;border:0;font:inherit;font-size:12px;color:#738765;cursor:pointer}.login-hint{font-size:12px;padding:20px;background:#f5f7ef;border-radius:10px;color:#98a38c}.login-hint button{text-decoration:underline}.empty-comments{padding:28px 0}.report-overlay{position:fixed;inset:0;background:#243e2b70;z-index:100;display:grid;place-items:center;padding:20px}.report-dialog{background:white;padding:26px;border-radius:18px;width:min(480px,100%)}.report-dialog label{display:block;font-size:13px;margin-top:16px}.report-dialog footer{display:flex;justify-content:flex-end;gap:12px;margin-top:16px}@media(max-width:600px){.interaction-bar{gap:10px}.interaction-bar .c-button{padding:10px 12px}.comment header{flex-wrap:wrap}.comment time{font-size:9px}.comment.reply{margin-left:8px;padding-left:10px}}
</style>
