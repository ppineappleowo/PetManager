<script setup>
import PetCards from '../components/PetCards.vue'
import { watch, ref } from 'vue'
import ProfileSocial from '../components/ProfileSocial.vue'
import { useRoute } from 'vue-router'
import CommunityShell from '../components/CommunityShell.vue'
import UserAvatar from '../components/UserAvatar.vue'
import { community } from '../api/community.js'
import PostCard from '../components/PostCard.vue'
import { useCursorList } from '../composables/useCursorList.js'
const route = useRoute(), user = ref(null)
const { items: posts, cursor, loading, error, load } = useCursorList(async (before, isCurrent) => {
  const id = route.params.id
  if (!before) {
    user.value = null
    const profile = await community('/users/' + id, { authenticated: false })
    if (!isCurrent()) return
    user.value = profile
  }
  return community('/users/' + id + '/posts' + (before ? '?before=' + before : ''), { authenticated: false })
})
watch(() => route.params.id, () => load(), { immediate: true })
</script>
<template><CommunityShell><RouterLink class="back-link" to="/">← 返回社区</RouterLink><section v-if="user" class="public-identity"><UserAvatar :user="user" /><div><p class="overline">在百宠集，遇见同好</p><h1>{{ user.name }}</h1><p class="public-bio">{{ user.bio || '这位宠友还没有填写简介。' }}</p><span class="public-count">{{ user.post_count }} 篇公开日常</span><ProfileSocial :user-id="user.id" /></div></section><template v-if="user?.pets?.length"><h2 class="stories-title">它们也是我的家人</h2><PetCards :pets="user.pets" /></template><h2 v-if="user" class="stories-title">宠爱日常</h2><p v-if="error" class="community-error" role="alert">{{ error }} <button @click="load(posts.length > 0)">重新加载</button></p><div class="post-grid"><PostCard v-for="post in posts" :key="post.id" :post="post" :show-author="false" /></div><p v-if="loading" class="community-empty" role="status">正在加载主页…</p><p v-else-if="user && !posts.length && !error" class="community-empty">还没有公开日常，期待下一次分享。</p><footer v-if="cursor" class="feed-footer"><button class="c-button" :disabled="loading" @click="load(true)">加载更多日常</button></footer></CommunityShell></template>
<style scoped>.public-identity{display:flex;gap:25px;align-items:center;margin:28px 0;padding:32px;border-radius:22px;background:linear-gradient(120deg,#e5efe3,#f4f1e4);border:1px solid #dce6d8}.public-identity .user-avatar{width:86px;height:86px;font-size:32px;border:4px solid white}.public-identity>div{min-width:0}.public-identity h1{font-size:28px;margin:8px 0;overflow-wrap:anywhere}.public-bio{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.8;color:var(--muted);font-size:14px}.public-count{display:block;margin-top:15px;font-size:13px;color:var(--accent)}.stories-title{font-size:18px;margin-bottom:22px}@media(max-width:580px){.public-identity{padding:22px 18px;gap:16px;align-items:flex-start}.public-identity .user-avatar{width:60px;height:60px}.public-identity h1{font-size:23px}}</style>
