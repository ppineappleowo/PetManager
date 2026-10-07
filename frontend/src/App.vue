<script setup>
import { watch } from 'vue'
import { RouterView, useRouter, useRoute } from 'vue-router'
import { useNotificationPolling } from './composables/useNotifications.js'
import { auth } from './composables/useAuth.js'
import ToastHost from './components/ToastHost.vue'

const router = useRouter()
useNotificationPolling(useRoute())
watch(() => [auth.token, router.currentRoute.value.fullPath], ([token]) => {
  if (!token && router.currentRoute.value.meta.requiresAuth) router.replace({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
})
</script>

<template>
  <RouterView :key="$route.path" />
  <ToastHost />
</template>
