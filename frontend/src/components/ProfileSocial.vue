<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { auth } from '../composables/useAuth.js'
import { community } from '../api/community.js'
const props = defineProps({ userId: { type: Number, required: true } })
const route = useRoute(), router = useRouter()
const state = ref(null), busy = ref(false), error = ref('')
let generation = 0
async function load() {
  const current = ++generation
  state.value = null; error.value = ''; busy.value = false
  try {
    const data = await community(`/users/${props.userId}/${auth.token ? 'follow' : 'social'}`, { authenticated: !!auth.token })
    if (current === generation) state.value = data
  } catch (reason) { if (current === generation) error.value = reason.message }
}
async function toggle() {
  if (!auth.token) return router.push({ name: 'login', query: { redirect: route.fullPath } })
  if (busy.value || !state.value) return
  const current = generation
  busy.value = true; error.value = ''
  try {
    const data = await community(`/users/${props.userId}/follow`, { method: state.value.following ? 'DELETE' : 'PUT' })
    if (current === generation) state.value = data
  } catch (reason) { if (current === generation) error.value = reason.message }
  finally { if (current === generation) busy.value = false }
}
watch(() => [props.userId, auth.token], load, { immediate: true })
</script>
<template>
  <div class="profile-social">
    <template v-if="state">
      <span>{{ state.following_count || 0 }} 关注 · {{ state.follower_count || 0 }} 粉丝</span>
      <RouterLink v-if="state.is_self" class="c-button" to="/connections">管理我的关注</RouterLink>
      <button v-else class="c-button" :class="{primary: !state.following}" :disabled="busy" :aria-pressed="!!state.following" @click="toggle">{{ busy ? '处理中…' : state.following ? '已关注 · 取消关注' : '＋ 关注' }}</button>
    </template>
    <span v-else-if="!error" role="status">正在加载关注信息…</span>
    <p v-if="error" role="alert">{{ error }} <button class="c-button" :disabled="busy" @click="state ? toggle() : load()">重试</button></p>
  </div>
</template>
<style scoped>.profile-social{display:flex;flex-wrap:wrap;align-items:center;gap:14px;margin-top:18px;font-size:13px;color:var(--accent)}.profile-social p{flex-basis:100%;color:#a4433b}.c-button{font-size:13px}</style>
