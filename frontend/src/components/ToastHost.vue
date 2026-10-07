<script setup>
import { toasts, dismissToast } from '../composables/useToast.js'
</script>

<template>
  <div class="toast-container" aria-live="polite">
    <button v-for="item in toasts" :key="item.id" class="toast" :class="item.type" @click="dismissToast(item.id)">
      {{ item.message }}
    </button>
  </div>
</template>

<style scoped>
.toast-container { position: fixed; top: 20px; right: 20px; z-index: 9999; display: flex; flex-direction: column; gap: 8px; pointer-events: none; }
.toast { padding: 12px 20px; max-width: min(360px, 90vw); border: none; border-radius: 12px; background: #059669; color: white; box-shadow: 0 4px 16px #0002; font-size: 13px; cursor: pointer; pointer-events: auto; }
.toast.error { background: #dc2626; }
</style>
