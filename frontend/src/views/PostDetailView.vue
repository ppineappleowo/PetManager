<script setup>
import TopicTags from '../components/TopicTags.vue'
import PetCards from '../components/PetCards.vue'
import AuthorLink from '../components/AuthorLink.vue'
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PostInteractions from '../components/PostInteractions.vue'
import CommunityShell from '../components/CommunityShell.vue'
import CommunityImage from '../components/CommunityImage.vue'
import { community, categories, imageUrl, statusLabel } from '../api/community.js'
const route = useRoute(), router = useRouter()
const post = ref(null), error = ref(''), loading = ref(false), busy = ref(false)
async function load() {
  loading.value = true; error.value = ''; post.value = null
  try { post.value = await community(`/${route.meta.mine ? 'mine' : 'posts'}/${route.params.id}`, { authenticated: !!route.meta.mine }) }
  catch (reason) { error.value = reason.message }
  finally { loading.value = false }
}
async function remove() {
  if (!window.confirm('确定删除这篇帖子？删除后将不再公开展示。')) return
  busy.value = true
  try { await community(`/posts/${post.value.id}`, { method: 'DELETE' }); router.replace('/my-posts') }
  catch (reason) { error.value = reason.message }
  finally { busy.value = false }
}
watch(() => route.fullPath, load, { immediate: true })
</script>
<template><CommunityShell><div class="detail-wrap"><RouterLink class="back-link" :to="route.meta.mine ? '/my-posts' : '/'">← {{ route.meta.mine ? '我的帖子' : '返回社区' }}</RouterLink><p v-if="loading" class="community-empty">正在打开日常…</p><div v-if="error" role="alert" class="community-error">{{ error }} <button @click="load">重试</button></div><article v-if="post" class="post-detail"><header class="detail-author"><div><AuthorLink :author="post.author" /><p>{{ new Date(post.created_at).toLocaleString('zh-CN') }} · {{ categories[post.category] }}</p></div><span v-if="route.meta.mine" class="post-status" :class="post.status">{{ statusLabel(post.status) }}</span></header><div v-if="post.status === 'hidden'" class="community-error">下架原因：{{ post.reason }}。编辑不会自动恢复公开展示。</div><h1 v-if="post.title">{{ post.title }}</h1><p class="post-body">{{ post.body }}</p><div class="detail-images"><CommunityImage v-for="(image, index) in post.images" :key="image" :src="post.status === 'published' ? imageUrl(post.id,image) : undefined" :private-path="post.status !== 'published' ? `/api/v1/community/media/${image}` : undefined" :alt="`帖子图片 ${index + 1}`" /></div><span v-if="post.ai_generated" class="ai-label">AI 辅助整理 · 请核实</span><TopicTags :tags="post.tags" /><footer v-if="route.meta.mine" class="detail-actions"><RouterLink class="c-button" :to="`/posts/${post.id}/edit`">编辑帖子</RouterLink><button class="c-button danger" :disabled="busy" @click="remove">删除帖子</button></footer><section v-if="post.pets?.length"><h2 class="pet-section-title">这篇日常里的小伙伴</h2><PetCards :pets="post.pets" /></section><PostInteractions :post="post" /></article></div></CommunityShell></template>

<style scoped>.pet-section-title{font-size:16px;margin-top:24px}</style>
