<script setup>
defineProps({ tags: { type: Array, default: () => [] } })
</script>
<template><div v-if="tags.length" class="topic-links"><RouterLink v-for="tag in tags" :key="tag" :to="{path:'/',query:{tag}}">#{{ tag }}</RouterLink></div></template>
<style scoped>.topic-links{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0;font-size:12px}.topic-links a{color:var(--accent);text-decoration:none;overflow-wrap:anywhere}.topic-links a:hover{text-decoration:underline}</style>
