<script setup>
import TopicTags from './TopicTags.vue'
import AuthorLink from './AuthorLink.vue'
import CommunityImage from './CommunityImage.vue'
import { categories, imageUrl, statusLabel } from '../api/community.js'
defineProps({ post: { type: Object, required: true }, mine: Boolean, showAuthor: { type: Boolean, default: true } })
</script>
<template>      <article class="post-card"><RouterLink class="post-content-link" :to="mine ? `/my-posts/${post.id}` : `/posts/${post.id}`">
        <CommunityImage v-if="post.images.length" :src="post.status === 'published' ? imageUrl(post.id, post.images[0], true) : undefined" :private-path="post.status !== 'published' ? `/api/v1/community/media/${post.images[0]}?thumbnail=true` : undefined" :alt="post.title || '宠物日常'" />
        <div v-else class="text-cover"><span>{{ categories[post.category] }} · 日常碎片</span><p>{{ post.body.slice(0, 130) }}</p><span class="text-flower" aria-hidden="true">✳</span></div>
        <div class="post-card-content"><span v-if="mine" class="post-status" :class="post.status">{{ statusLabel(post.status) }}</span><h2>{{ post.title || post.body.slice(0, 60) }}</h2><p class="card-tags">♡ {{ post.like_count || 0 }} · 评论 {{ post.comment_count || 0 }}</p></div></RouterLink><span v-if="post.ai_generated" class="ai-label">AI 辅助整理 · 请核实</span><TopicTags class="card-topic-links" :tags="post.tags" /><div v-if="showAuthor && post.author" class="post-author card-author"><AuthorLink :author="post.author" /><small>{{ new Date(post.created_at).toLocaleDateString('zh-CN', {month:'numeric',day:'numeric'}) }}</small></div>
      </article></template>
<style scoped>.card-topic-links{padding:0 16px}.post-content-link{color:inherit;text-decoration:none;display:block}.card-author{padding:0 16px 16px}</style>
