<script setup>
import { ref, watch } from 'vue'
import { baseUrl } from '../api/client.js'
const props = defineProps({ user: { type: Object, required: true } })
const failed = ref(false)
watch(() => props.user.avatar_id, () => { failed.value = false })
</script>
<template><span class="user-avatar"><img v-if="user.avatar_id && !failed" :src="`${baseUrl}/api/v1/community/users/${user.id}/avatar/${user.avatar_id}`" alt="" @error="failed = true" /><span v-else>{{ (user.name || user.nickname || user.username || '宠').slice(0,1) }}</span></span></template>
<style scoped>.user-avatar{display:inline-grid;place-items:center;width:32px;height:32px;flex-shrink:0;overflow:hidden;border-radius:50%;background:#e7eee6;color:#32654c;vertical-align:middle}.user-avatar img{width:100%;height:100%;object-fit:cover}</style>
