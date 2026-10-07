<script setup>
import { onMounted, ref } from 'vue'
import CommunityShell from '../components/CommunityShell.vue'
import PostCard from '../components/PostCard.vue'
import { community } from '../api/community.js'
import { useCursorList } from '../composables/useCursorList.js'

const { items: posts, cursor, loading, error, load } = useCursorList(before => community('/me/bookmarks' + (before ? '?before=' + before : '')))
const removing = ref(null), removeError = ref('')
async function remove(post) {
  if (removing.value !== null || loading.value) return
  removing.value = post.id; removeError.value = ''
  try {
    await community(`/posts/${post.id}/bookmark`, { method: 'DELETE' })
    posts.value = posts.value.filter(item => item.id !== post.id)
  } catch (reason) { removeError.value = reason.message }
  finally { removing.value = null }
}
onMounted(() => load())
</script>
<template>
  <CommunityShell>
    <header class="community-heading"><div><p class="overline">SAVED STORIES</p><h1>我的收藏</h1><p>留住喜欢的日常，随时回来看看。收藏列表仅你可见。</p></div></header>
    <div class="feed-caption"><span>已下架或删除的帖子不展示</span><span>最近收藏 ↓</span></div>
    <p v-if="error" class="community-error" role="alert">{{ error }} <button :disabled="removing !== null" @click="load(!!cursor)">重新加载</button></p>
    <p v-if="removeError" class="community-error" role="alert">{{ removeError }}，可再次点击取消收藏重试。</p>
    <div class="post-grid"><div v-for="post in posts" :key="post.id" class="saved-post"><PostCard :post="post" /><button class="c-button remove-bookmark" :disabled="removing !== null || loading" :aria-label="`取消收藏：${post.title || post.body.slice(0, 60)}`" @click="remove(post)">{{ removing === post.id ? '正在取消…' : '取消收藏' }}</button></div></div>
    <p v-if="loading" class="community-empty" role="status">正在加载收藏…</p>
    <div v-else-if="!posts.length && !error && !cursor" class="community-empty"><h2>还没有可展示的收藏</h2><p>在喜欢的帖子中点击收藏，就能在这里找到。</p><RouterLink class="c-button" to="/">去社区看看</RouterLink></div>
    <footer v-if="cursor" class="feed-footer"><button class="c-button" :disabled="loading || removing !== null" @click="load(true)">加载更多收藏</button></footer>
  </CommunityShell>
</template>
<style scoped>.saved-post{min-width:0}.remove-bookmark{margin-top:10px;width:100%}</style>
