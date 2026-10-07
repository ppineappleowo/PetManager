<script setup>
import {ref,watch} from 'vue'
import CommunityShell from '../components/CommunityShell.vue'
import {community} from '../api/community.js'
import {useCursorList} from '../composables/useCursorList.js'
const kind=ref('community'),labels={post:'帖子',comment:'评论',pet:'宠物档案',profile:'个人资料',avatar:'头像',access:'账号权限'}
const {items,cursor,loading,error,load}=useCursorList(before=>community(`/me/moderation?kind=${kind.value}${before?'&before='+before:''}`))
watch(kind,()=>load(),{immediate:true})
function outcome(item){
  const r=item.result||{}
  if(item.kind==='access')return [r.role==='admin'?'管理员':'普通用户',r.disabled?'账号已停用':'账号可用',r.revoked?'已撤销旧登录':''].filter(Boolean).join(' · ')
  if('status' in r)return r.status==='published'?'已恢复公开展示':r.status==='deleted'?'内容已删除':'已停止公开展示'
  return (r.hidden||r.profile_hidden||r.avatar_hidden)?'已停止公开展示':'已恢复公开展示'
}
</script>
<template><CommunityShell><header class="community-heading"><div><h1>处理记录</h1><p>查看与你有关的内容处理和原因。</p></div></header><label>记录范围 <select v-model="kind"><option value="community">日常、评论和宠物</option><option value="users">个人资料和账号</option></select></label><button class="c-button" :disabled="loading" @click="load()">刷新记录</button><p v-if="error" role="alert">{{ error }}，请刷新重试。</p><article v-for="item in items" :key="item.id"><h2>{{ labels[item.kind] }} #{{ item.target_id }}</h2><p><strong>{{ outcome(item) }}</strong></p><p>{{ item.reason }}</p><small>{{ item.created_at }}</small></article><p v-if="loading" role="status">正在加载…</p><p v-else-if="!items.length&&!error" class="community-empty">暂无处理记录</p><button v-if="cursor" class="c-button" :disabled="loading" @click="load(true)">加载更多</button></CommunityShell></template>
<style scoped>article{background:white;border:1px solid var(--line);border-radius:14px;padding:20px;margin:16px 0;overflow-wrap:anywhere}h2{font-size:16px}p{line-height:1.8;margin:10px 0}small{color:var(--muted)}select{font:inherit;padding:9px;border:1px solid var(--line);border-radius:8px;margin-right:10px}</style>
