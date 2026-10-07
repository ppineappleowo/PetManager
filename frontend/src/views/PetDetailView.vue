<script setup>
import { watch, ref } from 'vue'
import { useRoute } from 'vue-router'
import CommunityShell from '../components/CommunityShell.vue'
import CommunityImage from '../components/CommunityImage.vue'
import AuthorLink from '../components/AuthorLink.vue'
import { community,categories } from '../api/community.js'
import { baseUrl } from '../api/client.js'
import PostCard from '../components/PostCard.vue'
import { useCursorList } from '../composables/useCursorList.js'
const route = useRoute(), pet = ref(null)
const { items: posts, cursor, loading, error, load } = useCursorList(async (before, isCurrent) => {
  const id = route.params.id
  if (!before) {
    pet.value = null
    const profile = await community('/pets/' + id, { authenticated: false })
    if (!isCurrent()) return
    pet.value = profile
  }
  return community('/pets/' + id + '/posts' + (before ? '?before=' + before : ''), { authenticated: false })
})
watch(() => route.params.id, () => load(), { immediate: true })
</script>
<template><CommunityShell><RouterLink class="back-link" :to="pet ? `/users/${pet.owner.id}` : '/'">← {{ pet?'看看宠友主页':'返回社区' }}</RouterLink><section v-if="pet" class="pet-hero"><CommunityImage v-if="pet.photo_id" :src="`${baseUrl}/api/v1/community/pets/${pet.id}/photo/${pet.photo_id}`" :alt="pet.name" /><span v-else class="pet-symbol" aria-hidden="true">🐾</span><div><p class="overline">A LITTLE LIFE, A BIG LOVE</p><h1>{{ pet.name }}</h1><p class="pet-meta">{{ categories[pet.species] }} · {{ pet.breed || '品种未填写' }} · {{ {male:'公',female:'母',unknown:'性别未填写'}[pet.sex] }}</p><p v-if="pet.birthday" class="pet-meta">生日：{{ pet.birthday }}</p><p class="pet-bio">{{ pet.bio || '关于它的故事，正在慢慢记录。' }}</p><AuthorLink :author="pet.owner" /></div></section><h2 v-if="pet" class="pet-stories">它的日常 · {{ pet.post_count }} 篇</h2><p v-if="error" class="community-error" role="alert">{{ error }} <button @click="load(posts.length>0)">重新加载</button></p><div class="post-grid"><PostCard v-for="post in posts" :key="post.id" :post="post" :show-author="false" /></div><p v-if="loading" class="community-empty" role="status">正在加载宠物主页…</p><p v-else-if="pet&&!posts.length&&!error" class="community-empty">还没有关联日常，期待它的第一个故事。</p><footer v-if="cursor" class="feed-footer"><button class="c-button" :disabled="loading" @click="load(true)">加载更多日常</button></footer></CommunityShell></template>
<style scoped>.pet-hero{display:flex;align-items:center;gap:28px;padding:32px;margin:28px 0;border-radius:22px;background:linear-gradient(120deg,#e8eddf,#f4ecdf);border:1px solid #e0e5d7}.pet-hero>.community-image,.pet-symbol{width:150px;height:150px;flex-shrink:0;border-radius:24px}.pet-hero>.community-image :deep(img){height:150px}.pet-symbol{display:grid;place-items:center;font-size:52px;background:#ffffff90}.pet-hero>div{min-width:0}.pet-hero h1{font-size:30px;margin:12px 0;overflow-wrap:anywhere}.pet-meta{font-size:12px;color:var(--muted);margin:8px 0;overflow-wrap:anywhere}.pet-bio{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.8;font-size:14px;margin:16px 0}.pet-stories{font-size:18px;margin:24px 0}@media(max-width:580px){.pet-hero{padding:22px;gap:18px;flex-direction:column;align-items:flex-start}.pet-hero>.community-image,.pet-symbol{width:100px;height:100px}.pet-hero>.community-image :deep(img){height:100px}}</style>
