<script setup>
import {ref,watch} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import CommunityShell from '../components/CommunityShell.vue'
import {community} from '../api/community.js'
import {useCursorList} from '../composables/useCursorList.js'
const route=useRoute(),router=useRouter(),draft=ref('')
const kind=()=>route.query.kind==='pets'?'pets':'users'
const {items,cursor,loading,error,load}=useCursorList(before=>community(`/search/${kind()}?q=${encodeURIComponent(route.query.q||'')}${before?'&before='+before:''}`,{authenticated:false}))
watch(()=>route.fullPath,()=>{draft.value=route.query.q||'';load()},{immediate:true})
</script>
<template><CommunityShell><header class="community-heading"><div><h1>寻找同好</h1><p>通过公开昵称、宠物名字或品种找到感兴趣的伙伴。</p></div></header><form @submit.prevent="router.push({path:'/discover',query:{...route.query,q:draft.trim()}})"><label>搜索同好<input v-model="draft" maxlength="100"></label><button class="c-button">搜索</button></form><nav><RouterLink :to="{query:{...route.query,kind:'users'}}">宠友</RouterLink><RouterLink :to="{query:{...route.query,kind:'pets'}}">宠物</RouterLink></nav><p v-if="error" role="alert">{{ error }} <button @click="load(!!cursor)">重试</button></p><div class="results"><RouterLink v-for="row in items" :key="row.id" :to="`/${kind()==='pets'?'pets':'users'}/${row.id}`"><h2>{{ row.name }}</h2><p>{{ row.breed || (kind()==='pets'?row.species:'查看公开主页') }}</p></RouterLink></div><p v-if="loading" role="status">正在搜索…</p><p v-else-if="!items.length&&!error">没有找到匹配的同好。</p><button v-if="cursor" class="c-button" :disabled="loading" @click="load(true)">加载更多</button></CommunityShell></template>
<style scoped>form,nav{display:flex;gap:16px;align-items:end;margin-bottom:20px}input{display:block;padding:10px;border:1px solid var(--line);border-radius:8px;width:100%;font:inherit}form label{flex:1;min-width:0}nav a{color:var(--accent)}.results{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px}.results a{border:1px solid var(--line);background:white;border-radius:14px;padding:20px;text-decoration:none;color:var(--ink);overflow-wrap:anywhere}.results h2{font-size:17px}.results p{font-size:13px;margin-top:10px}</style>
