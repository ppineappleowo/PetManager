<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { auth } from '../composables/useAuth.js'
import { community } from '../api/community.js'

const props = defineProps({ postId: { type: Number, required: true } })
const router = useRouter(), route = useRoute()
const saved = ref(false), busy = ref(false), ready = ref(false), error = ref('')
let generation = 0
async function load() {
  const current = ++generation
  saved.value = false; ready.value = !auth.token; error.value = ''; busy.value = !!auth.token
  if (!auth.token) return
  try {
    const data = await community(`/posts/${props.postId}/bookmark`)
    if (current === generation) { saved.value = data.bookmarked; ready.value = true }
  } catch (reason) { if (current === generation) error.value = reason.message }
  finally { if (current === generation) busy.value = false }
}
async function toggle() {
  if (!auth.token) return router.push({ name: 'login', query: { redirect: route.fullPath } })
  if (busy.value || !ready.value) return
  const current = generation
  busy.value = true; error.value = ''
  try {
    const data = await community(`/posts/${props.postId}/bookmark`, { method: saved.value ? 'DELETE' : 'PUT' })
    if (current === generation) saved.value = data.bookmarked
  } catch (reason) { if (current === generation) error.value = reason.message }
  finally { if (current === generation) busy.value = false }
}
watch(() => [props.postId, auth.token], load, { immediate: true })
</script>
<template>
  <div class="bookmark-action">
    <button class="c-button" :aria-pressed="saved" :disabled="busy || !ready" @click="toggle">{{ saved ? '★ 已收藏' : '☆ 收藏' }}</button>
    <p v-if="error" role="alert">{{ error }} <button class="c-button" :disabled="busy" @click="load">重新读取收藏状态</button></p>
  </div>
</template>
<style scoped>
.bookmark-action p{font-size:12px;color:#9a4e42}.bookmark-action button[aria-pressed=true]{background:#edf3e7;color:var(--accent)}
</style>
