<script setup>
import { watch } from 'vue'
import { useRoute } from 'vue-router'
import CommunityShell from '../components/CommunityShell.vue'
import PostCard from '../components/PostCard.vue'
import DiscoveryControls from '../components/DiscoveryControls.vue'
import { community, categories } from '../api/community.js'
import { useCursorList } from '../composables/useCursorList.js'
import {auth} from '../composables/useAuth.js'
const route = useRoute()
const { items: posts, cursor, loading, error, load } = useCursorList(async before => {
  const params = new URLSearchParams()
  if (before) params.set('before', before)
  if (route.query.category && !route.meta.mine) params.set('category', route.query.category)
  if (!route.meta.mine && !route.meta.following) {
    for (const key of ['q', 'tag', 'sort']) if (route.query[key]) params.set(key, route.query[key])
  }
  return community((route.meta.mine ? '/mine' : route.meta.following ? '/me/following/posts' : '/posts') + '?' + params, { authenticated: !!(route.meta.mine || route.meta.following) })
},()=>`${auth.token}:${route.fullPath}`)
watch(() => route.fullPath, () => load(), { immediate: true })
</script>
<template>
  <CommunityShell>
    <header class="community-heading"><div><p class="overline">{{ route.meta.mine ? 'MY STORIES' : 'LIFE WITH PETS' }}</p><h1>{{ route.meta.mine ? '我的宠爱日常' : route.meta.following ? '关注的宠友，最近在分享' : '每一种宠爱，都有同好。' }}</h1><p>{{ route.meta.mine ? '记录、分享，也珍藏每一个陪伴的瞬间。' : '看看大家的新鲜事，分享你和它的小日子。' }}</p></div><RouterLink class="c-button primary desktop-publish" to="/publish">＋ 分享日常</RouterLink></header>
    <nav v-if="!route.meta.mine" class="category-tabs" aria-label="信息流"><RouterLink to="/" :class="{active: !route.meta.following}">发现</RouterLink><RouterLink to="/following" :class="{active: route.meta.following}">关注</RouterLink></nav>
    <DiscoveryControls v-if="!route.meta.mine && !route.meta.following" />
    <nav v-if="!route.meta.mine" class="category-tabs" aria-label="宠物分类"><RouterLink :to="{path:route.meta.following ? '/following' : '/',query:{...route.query,category:undefined}}" :class="{active: !route.query.category}">全部</RouterLink><RouterLink v-for="(label, key) in categories" :key="key" :to="{path:route.meta.following ? '/following' : '/',query:{...route.query,category:key}}" :class="{active:route.query.category === key}">{{ label }}</RouterLink></nav>
    <button class="c-button" :disabled="loading" @click="load(false,true)">刷新动态</button><div class="feed-caption"><span>{{ route.meta.mine ? '我的全部帖子' : (categories[route.query.category] || (route.meta.following ? '我关注的宠友' : '全部宠物 · 全部作者')) }}</span><span>{{ !route.meta.mine && !route.meta.following && route.query.sort === 'oldest' ? '最早发布 ↑' : '最新发布 ↓' }}</span></div>
    <div v-if="error" class="community-error" role="alert">{{ error }} <button @click="load(posts.length > 0)">重新加载</button></div>
    <div class="post-grid">
      <PostCard v-for="post in posts" :key="post.id" :post="post" :mine="!!route.meta.mine" />
    </div>
    <div v-if="loading" class="community-empty" role="status">正在寻找新鲜日常…</div>
    <div v-else-if="!posts.length && !error" class="community-empty"><span class="empty-paw">♡</span><h2>{{ !route.meta.mine && !route.meta.following && (route.query.q || route.query.tag) ? '没有找到相关日常' : route.meta.mine ? '你的故事，从这里开始' : route.meta.following ? '还没有关注动态' : '这里，正等着第一份分享' }}</h2><p>{{ !route.meta.mine && !route.meta.following && (route.query.q || route.query.tag) ? '试试更短的关键词，或清除话题和分类筛选。' : route.meta.following ? '去社区关注喜欢的宠友，他们的新日常会出现在这里。' : '一张照片、一段文字，都值得被看见。' }}</p><RouterLink v-if="route.meta.following" class="c-button" to="/">发现同好</RouterLink><RouterLink v-if="!route.meta.following" class="c-button primary" to="/publish">发布第一篇日常</RouterLink></div>
    <footer v-if="posts.length" class="feed-footer"><button v-if="cursor" class="c-button" :disabled="loading" @click="load(true)">加载更多日常</button><span v-else>已经看完啦，去记录你的日常吧。</span></footer>
  </CommunityShell>
</template>
