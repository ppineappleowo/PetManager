<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { apiFetch } from '../api/client.js'
const props = defineProps({ src: String, privatePath: String, alt: { type: String, default: '帖子图片' } })
const url = ref(''), failed = ref(false)
let generation = 0, objectUrl = ''
function release() { if (objectUrl) URL.revokeObjectURL(objectUrl); objectUrl = '' }
async function load() {
  const id = ++generation
  release(); failed.value = false; url.value = props.src || ''
  if (props.privatePath) {
    try {
      const blob = await (await apiFetch(props.privatePath)).blob()
      if (id !== generation) return
      objectUrl = URL.createObjectURL(blob); url.value = objectUrl
    } catch { if (id === generation) failed.value = true }
  }
}
watch(() => [props.src, props.privatePath], load, { immediate: true })
onBeforeUnmount(() => { generation++; release() })
</script>
<template><div class="community-image"><div v-if="failed" class="image-fallback"><span>图片暂不可用</span><button type="button" @click.prevent.stop="load">重试</button></div><img v-else-if="url" :src="url" :alt="alt" loading="lazy" @error="failed = true"><span v-else class="image-fallback">图片加载中…</span></div></template>
