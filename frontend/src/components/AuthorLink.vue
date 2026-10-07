<script setup>
import UserAvatar from './UserAvatar.vue'
defineProps({ author: { type: Object, required: true } })
</script>
<template><RouterLink v-if="author.id" class="author-link" :to="`/users/${author.id}`"><UserAvatar :user="author" aria-hidden="true" /><span>{{ author.name }}</span></RouterLink><span v-else class="author-link"><UserAvatar :user="author" aria-hidden="true" />{{ author.name }}</span></template>
<style scoped>.author-link{display:inline-flex;align-items:center;gap:9px;min-width:0;color:inherit;text-decoration:none;overflow-wrap:anywhere}.author-link:hover{color:var(--accent)}.author-link span{min-width:0}</style>
