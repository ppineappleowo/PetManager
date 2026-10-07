<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import CommunityShell from '../components/CommunityShell.vue'
import UserAvatar from '../components/UserAvatar.vue'
import { community } from '../api/community.js'
const route = useRoute(), items = ref([]), cursor = ref(null), loading = ref(false), error = ref('')
const pending = ref(new Set())
let generation = 0
async function load(more = false) {
  const current = ++generation
  loading.value = true; error.value = ''
  if (!more) { items.value = []; cursor.value = null; pending.value = new Set() }
  const params = new URLSearchParams({ kind: route.query.kind === 'followers' ? 'followers' : 'following' })
  if (more && cursor.value) params.set('before', cursor.value)
  try {
    const data = await community(`/me/connections?${params}`)
    if (current !== generation) return
    items.value = more ? [...items.value, ...data.items] : data.items
    cursor.value = data.next_cursor
  } catch (reason) { if (current === generation) error.value = reason.message }
  finally { if (current === generation) loading.value = false }
}
async function toggle(user) {
  if (loading.value || pending.value.has(user.id)) return
  const current = generation
  pending.value.add(user.id); error.value = ''
  try {
    const data = await community(`/users/${user.id}/follow`, { method: user.following ? 'DELETE' : 'PUT' })
    if (current === generation) {
      user.following = data.following
      if (!data.following && route.query.kind !== 'followers') items.value = items.value.filter(item => item.id !== user.id)
    }
  } catch (reason) { if (current === generation) error.value = reason.message }
  finally { if (current === generation) pending.value.delete(user.id) }
}
watch(() => route.fullPath, () => load(), { immediate: true })
</script>
<template><CommunityShell>
  <header class="community-heading"><div><p class="overline">PET FRIENDS</p><h1>我的同好</h1><p>关注喜欢的宠友，让每一份分享都有回应。</p></div><RouterLink class="c-button" to="/following">查看关注动态 →</RouterLink></header>
  <nav class="category-tabs" aria-label="关注与粉丝"><RouterLink to="/connections" :class="{active: route.query.kind !== 'followers'}">我的关注</RouterLink><RouterLink to="/connections?kind=followers" :class="{active: route.query.kind === 'followers'}">我的粉丝</RouterLink></nav>
  <p v-if="error" class="community-error" role="alert">{{ error }} <button :disabled="loading || pending.size > 0" @click="load()">重新加载</button></p>
  <div class="connection-list"><article v-for="user in items" :key="user.id" class="connection-card">
    <RouterLink class="person" :to="`/users/${user.id}`"><UserAvatar :user="user" /><div><h2>{{ user.name }}</h2><p>{{ user.bio || '去看看这位宠友的日常吧。' }}</p></div></RouterLink>
    <button class="c-button" :disabled="loading || pending.has(user.id)" :aria-pressed="user.following" @click="toggle(user)">{{ pending.has(user.id) ? '处理中…' : user.following ? '取消关注' : '关注' }}</button>
  </article></div>
  <p v-if="loading" class="community-empty" role="status">正在寻找同好…</p>
  <div v-else-if="!items.length && !error" class="community-empty"><h2>{{ route.query.kind === 'followers' ? '还没有粉丝' : '还没有关注的宠友' }}</h2><p>去社区分享日常、发现同好吧。</p><RouterLink class="c-button" to="/">逛逛社区</RouterLink></div>
  <footer v-if="cursor" class="feed-footer"><button class="c-button" :disabled="loading || pending.size > 0" @click="load(true)">加载更多宠友</button></footer>
</CommunityShell></template>
<style scoped>.connection-list{display:grid;gap:14px}.connection-card{display:flex;align-items:center;justify-content:space-between;gap:16px;border:1px solid var(--line);background:white;border-radius:16px;padding:22px}.person{display:flex;gap:16px;align-items:center;text-decoration:none;color:var(--ink);min-width:0;flex:1}.person .user-avatar{width:50px;height:50px;font-size:22px}.person>div{min-width:0}.person h2{font-size:16px;overflow-wrap:anywhere}.person p{margin-top:7px;font-size:13px;color:var(--muted);overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.connection-card button{flex-shrink:0}@media(max-width:500px){.connection-card{padding:16px;gap:10px}.person{gap:10px}.person .user-avatar{width:40px;height:40px}.connection-card button{padding:9px 12px;font-size:12px}}</style>
