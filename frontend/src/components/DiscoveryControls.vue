<script setup>
import { ref, watch, onScopeDispose } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { community } from '../api/community.js'

const route = useRoute(), router = useRouter(), draft = ref(''), topics = ref([]), error = ref('')
let generation = 0
watch(() => route.query.q, value => { draft.value = typeof value === 'string' ? value : '' }, { immediate: true })
function change(values) {
  const query = { ...route.query, ...values }
  for (const key of Object.keys(query)) if (!query[key]) delete query[key]
  router.push({ path: '/', query })
}
async function loadTopics() {
  const current = ++generation
  topics.value = []; error.value = ''
  const params = new URLSearchParams()
  if (route.query.category) params.set('category', route.query.category)
  try {
    const data = await community('/topics?' + params, { authenticated: false })
    if (current === generation) topics.value = data.items || []
  } catch (reason) { if (current === generation) error.value = reason.message }
}
watch(() => route.query.category, loadTopics, { immediate: true })
onScopeDispose(() => { generation++ })
</script>
<template>
  <section class="discovery" aria-label="搜索与话题">
    <RouterLink :to="{path:'/discover',query:{q:route.query.q}}">寻找宠友和宠物 ↗</RouterLink>
    <form class="search-form" @submit.prevent="change({q: draft.trim()})"><label class="search-input">搜索日常<input v-model="draft" type="search" maxlength="100" placeholder="搜索养宠经验、宠物日常或标签" /></label><button class="c-button primary">搜索</button><label class="sort-label">排序<select aria-label="排序" :value="route.query.sort || 'latest'" @change="change({sort: $event.target.value})"><option value="latest">最新发布</option><option value="oldest">最早发布</option></select></label></form>
    <div v-if="route.query.q || route.query.tag" class="active-filters"><span v-if="route.query.q">关键词：{{ route.query.q }}</span><span v-if="route.query.tag">话题：#{{ route.query.tag }}</span><button class="c-button" @click="change({q: '', tag: ''})">清除搜索和话题</button></div>
    <nav v-if="topics.length" class="topics" aria-label="热门话题"><span>大家在聊</span><RouterLink v-for="topic in topics" :key="topic.tag" :to="{path:'/',query:{...route.query,tag:topic.tag}}" :class="{active:route.query.tag === topic.tag}">#{{ topic.tag }} <small>{{ topic.post_count }}</small></RouterLink></nav>
    <p v-if="error" class="topic-error" role="alert">话题暂时不可用 <button @click="loadTopics">重试</button></p>
  </section>
</template>
<style scoped>
.discovery{margin-bottom:24px}.search-form{display:flex;align-items:flex-end;gap:12px}.search-input{flex:1;min-width:0}.search-form label{font-size:12px;color:var(--muted)}.search-form input,.search-form select{display:block;margin-top:7px;padding:12px;border:1px solid var(--line);border-radius:10px;background:white;color:var(--ink);font:inherit}.search-form input{width:100%;box-sizing:border-box;font-size:14px}.search-form select{max-width:100%}.topics,.active-filters{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-top:16px;font-size:12px}.topics>a{border:1px solid var(--line);border-radius:18px;padding:7px 12px;color:var(--accent);text-decoration:none;background:#fff}.topics>a.active{background:#e4efdf}.topics small{margin-left:4px;color:var(--muted)}.topic-error{font-size:12px;color:var(--muted)}@media(max-width:580px){.search-form{flex-wrap:wrap;gap:10px}.search-input{flex-basis:70%}.sort-label{display:flex;align-items:center;gap:10px}.search-form select{margin-top:0}.topics{gap:7px}}
</style>
