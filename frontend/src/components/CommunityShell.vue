<script setup>
import { loadCurrentUser } from '../composables/useCurrentUser.js'

import { onMounted, ref } from 'vue'
import { auth } from '../composables/useAuth.js'
import { notificationState } from '../composables/useNotifications.js'
import PawIcon from './PawIcon.vue'
import '../assets/community.css'
const admin = ref(false)
onMounted(async () => {
  if (auth.token) { try { admin.value = (await loadCurrentUser()).role === 'admin' } catch {} }
})
</script>
<template>
  <div class="community-app">
    <aside class="community-sidebar">
      <RouterLink to="/" class="community-brand"><span class="brand-paw"><PawIcon /></span><span>百宠集<small>BAICHONGJI</small></span></RouterLink>
      <nav aria-label="平台导航">
        <RouterLink to="/" exact-active-class="selected"><span aria-hidden="true">⌂</span>社区</RouterLink>
        <RouterLink to="/following" active-class="selected"><span aria-hidden="true">♡</span>关注动态</RouterLink>
        <RouterLink to="/connections" active-class="selected"><span aria-hidden="true">♧</span>我的同好</RouterLink>
        <RouterLink to="/publish" active-class="selected"><span aria-hidden="true">＋</span>发布日常</RouterLink>
        <RouterLink to="/my-posts" active-class="selected"><span aria-hidden="true">▤</span>我的帖子</RouterLink>
        <RouterLink to="/bookmarks" active-class="selected"><span aria-hidden="true">☆</span>我的收藏</RouterLink>
        <RouterLink to="/notifications" active-class="selected"><span aria-hidden="true">♧</span>消息通知<span v-if="notificationState.unread">{{ notificationState.unread > 99 ? '99+' : notificationState.unread }}</span></RouterLink>
        <RouterLink to="/reports" active-class="selected"><span aria-hidden="true">☷</span>我的举报</RouterLink>
        <RouterLink to="/pets" active-class="selected"><span aria-hidden="true">🐾</span>我的宠物</RouterLink><RouterLink to="/ai"><span aria-hidden="true">✧</span>AI 助手</RouterLink>
      </nav>
      <div class="sidebar-note"><span>在这里，遇见同好。</span><p>分享平凡日常里的<br>每一份不平凡的宠爱。</p></div>
      <div class="community-account"><RouterLink v-if="admin" to="/admin">管理后台 ↗</RouterLink><RouterLink :to="auth.token ? '/profile' : '/login'"><span class="mini-avatar">{{ auth.username.slice(0, 1) || '♡' }}</span><span>{{ auth.token ? '个人中心' : '登录 / 注册' }}</span></RouterLink></div>
    </aside>
    <main class="community-main"><slot /></main>
    <nav class="mobile-community-nav" aria-label="移动导航"><RouterLink to="/">社区</RouterLink><RouterLink to="/ai">AI 助手</RouterLink><RouterLink to="/notifications">消息<span v-if="notificationState.unread"> · {{ notificationState.unread > 99 ? '99+' : notificationState.unread }}</span></RouterLink><RouterLink class="mobile-publish" to="/publish" aria-label="发布帖子">＋</RouterLink><RouterLink to="/my-posts">我的帖子</RouterLink><RouterLink :to="auth.token ? '/profile' : '/login'">{{ auth.token ? '我的' : '登录' }}</RouterLink></nav>
  </div>
</template>
