<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import CommunityShell from '../components/CommunityShell.vue'
import { community } from '../api/community.js'
import { useCursorList } from '../composables/useCursorList.js'
import { notificationState, refreshNotifications } from '../composables/useNotifications.js'

const router = useRouter(), busy = ref(false), actionError = ref('')
const { items, cursor, loading, error, load } = useCursorList(before => community('/me/notifications' + (before ? '?before=' + before : '')))
const labels = { comment: '评论了你的日常', reply: '回复了你的评论', follow: '关注了你' }
async function refresh() {
  if (busy.value || loading.value) return
  actionError.value = ''
  await Promise.all([load(), refreshNotifications(true).catch(e => { actionError.value = e.message })])
}
async function read(item, navigate = false) {
  if (busy.value || loading.value) return
  busy.value = true; actionError.value = ''
  try {
    await community(`/me/notifications/${item.id}/read`, { method: 'PUT' })
    item.read = true
    await refreshNotifications(true)
    if (navigate && item.target) await router.push(item.target)
  } catch (reason) { actionError.value = reason.message }
  finally { busy.value = false }
}
async function readAll() {
  if (busy.value || loading.value) return
  const through = notificationState.latestId
  busy.value = true; actionError.value = ''
  try {
    await community('/me/notifications/read-all', { method: 'PUT', body: JSON.stringify({ through_id: through }) })
    items.value.forEach(item => { if (item.id <= through) item.read = true })
    await refreshNotifications(true)
  } catch (reason) { actionError.value = reason.message }
  finally { busy.value = false }
}
onMounted(refresh)
</script>
<template>
  <CommunityShell>
    <header class="community-heading"><div><p class="overline">YOUR COMMUNITY UPDATES</p><h1>消息通知</h1><p>看看宠友们的新回应 · {{ notificationState.unread }} 条未读</p></div></header>
    <div class="notification-tools"><button class="c-button" :disabled="busy || loading" @click="refresh">刷新消息</button><button class="c-button" :disabled="busy || loading || !notificationState.unread" @click="readAll">全部标为已读</button></div>
    <p v-if="error || actionError" role="alert" class="community-error">{{ error || actionError }}，请重试。</p>
    <div class="notifications"><article v-for="item in items" :key="item.id" :class="{unread: !item.read}">
      <div><span v-if="!item.read" class="unread-label">未读</span><p>{{ item.available ? `${item.actor.name} ${labels[item.kind]}` : '相关内容或用户已不可用' }}</p><time>{{ new Date(item.created_at).toLocaleString('zh-CN') }}</time></div>
      <div class="notification-actions"><button v-if="item.available" class="c-button" :disabled="busy || loading" @click="read(item, true)">查看{{ item.kind === 'follow' ? '主页' : '日常' }}</button><button v-if="!item.read" class="c-button" :disabled="busy || loading" @click="read(item)">标为已读</button></div>
    </article></div>
    <p v-if="loading" role="status" class="community-empty">正在加载消息…</p><p v-else-if="!items.length && !error" class="community-empty">暂时还没有消息，去社区聊聊吧。</p>
    <footer v-if="cursor" class="feed-footer"><button class="c-button" :disabled="busy || loading" @click="load(true)">加载更多消息</button></footer>
  </CommunityShell>
</template>
<style scoped>
.notification-tools,.notification-actions{display:flex;gap:10px;flex-wrap:wrap}.notification-tools{margin-bottom:20px}.notifications article{display:flex;align-items:center;justify-content:space-between;gap:16px;border:1px solid var(--line);border-radius:16px;padding:20px;margin:12px 0;background:#fff}.notifications article.unread{background:#f0f6eb;border-color:#c3d5b7}.notifications p{overflow-wrap:anywhere;margin:8px 0}.notifications time{font-size:12px;color:var(--muted)}.unread-label{font-size:11px;color:var(--accent)}.notification-actions{flex-shrink:0}@media(max-width:640px){.notifications article{align-items:flex-start;flex-direction:column}}
</style>
