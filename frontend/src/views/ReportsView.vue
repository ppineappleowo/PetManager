<script setup>
import { watch } from 'vue'
import { useRoute } from 'vue-router'
import CommunityShell from '../components/CommunityShell.vue'
import { community } from '../api/community.js'
import { useCursorList } from '../composables/useCursorList.js'

const route = useRoute()
const filters = { all: '全部', open: '待处理', resolved: '已处理' }
const currentStatus = () => ['open', 'resolved'].includes(route.query.status) ? route.query.status : 'all'
const { items, cursor, loading, error, load } = useCursorList(before => {
  const params = new URLSearchParams({ status: currentStatus() })
  if (before) params.set('before', before)
  return community('/me/reports?' + params)
})
function time(value) {
  if (!value) return ''
  // Legacy report timestamps are stored as UTC text without an offset.
  const normalized = value.replace(' ', 'T')
  return new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(normalized) ? normalized : normalized + 'Z').toLocaleString('zh-CN')
}
watch(() => route.query.status, () => load(), { immediate: true })
</script>
<template>
  <CommunityShell>
    <header class="community-heading"><div><p class="overline">COMMUNITY FEEDBACK</p><h1>我的举报</h1><p>查看核查进度和处理说明，一起维护友善的社区。</p></div></header>
    <div class="report-tools"><nav aria-label="筛选举报"><RouterLink v-for="(label, key) in filters" :key="key" :to="{path:'/reports', query:key === 'all' ? {} : {status:key}}" class="c-button" :class="{active:currentStatus() === key}" :aria-current="currentStatus() === key ? 'page' : undefined">{{ label }}</RouterLink></nav><button class="c-button" :disabled="loading" @click="load()">刷新进度</button></div>
    <p class="privacy-note">记录仅你和管理员可见。处理结果记录当时的结论，内容当前状态可能变化。</p>
    <p v-if="error" role="alert" class="community-error">{{ error }} <button class="c-button" :disabled="loading" @click="load(!!cursor)">重试加载</button></p>
    <div class="report-list"><article v-for="item in items" :key="item.id" class="report-card">
      <header><h2>{{ item.target_type === 'post' ? '帖子' : '评论' }}举报 #{{ item.id }}</h2><span class="report-status" :class="{pending:item.status === 'open'}">{{ item.status === 'open' ? '待处理' : item.resolution === 'hide' ? '已处理违规内容' : '未采纳举报' }}</span></header>
      <p class="report-meta">{{ item.target_type === 'post' ? '帖子' : '评论' }} #{{ item.target_id }} · 提交于 {{ time(item.created_at) }}</p>
      <h3>你的举报原因</h3><p class="report-text">{{ item.reason }}</p>
      <section class="report-result"><h3>处理反馈</h3><p v-if="item.status === 'open'">管理员尚未完成核查，请稍后刷新查看。</p><template v-else><p class="report-text">{{ item.note || '暂无处理说明' }}</p><time>处理于 {{ time(item.resolved_at) }}</time></template></section>
      <footer><RouterLink v-if="item.target" class="c-button" :to="item.target">查看相关日常</RouterLink><span v-else>相关内容当前不可用</span></footer>
    </article></div>
    <p v-if="loading" role="status" class="community-empty">正在加载举报记录…</p>
    <div v-else-if="!items.length && !error" class="community-empty"><h2>{{ currentStatus() === 'all' ? '你还没有提交过举报' : '暂无这类举报记录' }}</h2><p>在帖子或评论中发现问题，可以使用举报入口告知管理员。</p></div>
    <footer v-if="cursor" class="feed-footer"><button class="c-button" :disabled="loading" @click="load(true)">加载更多举报</button></footer>
  </CommunityShell>
</template>
<style scoped>
.report-tools,.report-tools nav{display:flex;gap:10px;flex-wrap:wrap}.report-tools{justify-content:space-between}.active{background:var(--accent);color:white}.privacy-note,.report-meta,.report-result time,.report-card footer{font-size:12px;color:var(--muted);line-height:1.8}.privacy-note{margin:18px 0}.report-card{background:white;border:1px solid var(--line);border-radius:18px;padding:24px;margin:16px 0;overflow-wrap:anywhere}.report-card header{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.report-card h2{font-size:17px}.report-card h3{font-size:13px;margin:16px 0 8px}.report-meta{margin-top:8px}.report-text{white-space:pre-wrap;line-height:1.8;font-size:14px}.report-status{font-size:12px;padding:6px 10px;background:#eaf3e7;color:#386c48;border-radius:20px}.report-status.pending{background:#fbf1da;color:#85652f}.report-result{background:#f6f8f3;border-radius:12px;padding:4px 16px 16px;margin:20px 0;font-size:14px;line-height:1.8}.report-result time{display:block;margin-top:10px}@media(max-width:640px){.report-card{padding:18px}.report-tools{gap:14px}}
</style>
