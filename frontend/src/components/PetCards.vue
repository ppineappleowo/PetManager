<script setup>
import CommunityImage from './CommunityImage.vue'
import { baseUrl } from '../api/client.js'
import { categories } from '../api/community.js'
defineProps({ pets: { type:Array, default:()=>[] } })
</script>
<template><div class="pet-cards"><component :is="pet.hidden ? 'div' : 'RouterLink'" v-for="pet in pets" :key="pet.id" :to="`/pets/${pet.id}`" class="pet-card"><CommunityImage v-if="pet.photo_id" :src="pet.hidden ? undefined : `${baseUrl}/api/v1/community/pets/${pet.id}/photo/${pet.photo_id}`" :private-path="pet.hidden ? `/api/v1/community/media/${pet.photo_id}?thumbnail=true` : undefined" :alt="pet.name" /><span v-else class="pet-placeholder" aria-hidden="true">🐾</span><div><b>{{ pet.name }}</b><small>{{ categories[pet.species] }}{{ pet.breed ? ' · ' + pet.breed : '' }}</small></div></component></div></template>
<style scoped>.pet-cards{display:flex;flex-wrap:wrap;gap:12px;margin:18px 0 26px}.pet-card{display:flex;align-items:center;gap:12px;max-width:100%;padding:12px 16px;background:#fffefb;border:1px solid #e0e7d9;border-radius:16px;color:var(--ink);text-decoration:none}.pet-card:hover{border-color:#6e936c}.pet-card .community-image,.pet-placeholder{width:52px;height:52px;min-height:52px;flex-shrink:0;border-radius:12px;display:grid;place-items:center;background:#eaf0e4}.pet-card :deep(img){height:52px}.pet-card div{min-width:0}.pet-card b{font-size:14px;overflow-wrap:anywhere}.pet-card small{display:block;color:var(--muted);font-size:11px;margin-top:6px;overflow-wrap:anywhere}</style>
