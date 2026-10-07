<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { apiJson } from '../api/client.js'
import { clearAuth } from '../composables/useAuth.js'
import { toast } from '../composables/useToast.js'
import { passwordError } from '../utils/validation.js'

const emit = defineEmits(['close'])
const form = reactive({ old: '', password: '', confirm: '' })
const errors = reactive({ old: '', password: '', confirm: '' })
const busy = ref(false)
const serverError = ref('')
const waitUntil = ref(0)
const now = ref(Date.now())
const countdown = computed(() => Math.max(0, Math.ceil((waitUntil.value - now.value) / 1000)))
const timer = setInterval(() => { now.value = Date.now() }, 1000)
onBeforeUnmount(() => clearInterval(timer))

async function submit() {
  if (busy.value || countdown.value) return
  errors.old = form.old ? '' : '请输入原密码'
  errors.password = passwordError(form.password) || (form.old === form.password ? '新密码不能与原密码相同' : '')
  errors.confirm = form.password === form.confirm ? '' : '两次输入的密码不一致'
  if (Object.values(errors).some(Boolean)) return
  busy.value = true
  serverError.value = ''
  try {
    await apiJson('/api/v1/auth/password', { method: 'POST', body: JSON.stringify({ old_password: form.old, new_password: form.password }) })
    clearAuth()
    toast('密码已修改，请重新登录')
    emit('close')
  } catch (error) {
    serverError.value = error.message
    if (error.retryAfter) waitUntil.value = Date.now() + error.retryAfter * 1000
  } finally { busy.value = false }
}
</script>

<template>
  <div class="overlay" @keydown.esc="!busy && emit('close')">
    <form class="password-dialog" v-focus-trap role="dialog" aria-modal="true" aria-labelledby="password-title" @submit.prevent="submit" novalidate>
      <h2 id="password-title">修改密码</h2><p>修改成功后，所有旧登录令牌失效，需要重新登录。</p>
      <label for="old-password">原密码</label><input id="old-password" v-model="form.old" type="password" autocomplete="current-password" :disabled="busy" maxlength="64" />
      <span class="field-error">{{ errors.old }}</span>
      <label for="new-password">新密码</label><input id="new-password" v-model="form.password" type="password" autocomplete="new-password" :disabled="busy" maxlength="64" />
      <span class="field-error">{{ errors.password }}</span>
      <label for="confirm-password">确认新密码</label><input id="confirm-password" v-model="form.confirm" type="password" autocomplete="new-password" :disabled="busy" maxlength="64" />
      <span class="field-error">{{ errors.confirm }}</span>
      <p v-if="serverError" class="field-error" role="alert">{{ serverError }}</p>
      <div class="actions"><button type="button" :disabled="busy" @click="emit('close')">取消</button><button class="save" type="submit" :disabled="busy || !!countdown">{{ countdown ? `${countdown} 秒后重试` : busy ? '正在修改…' : '确认修改' }}</button></div>
    </form>
  </div>
</template>

<style scoped>
.overlay { position: fixed; inset: 0; z-index: 100; background: #0005; display: grid; place-items: center; padding: 20px; }
.password-dialog { width: min(420px, 100%); background: white; padding: 28px; border-radius: 18px; max-height: 90dvh; overflow: auto; }
h2 { font-size: 20px; } p { font-size: 13px; color: #6b7280; margin: 12px 0 18px; }
label { display: block; margin-top: 12px; font-size: 14px; }
input { width: 100%; padding: 10px; border: 1px solid #d1fae5; border-radius: 8px; margin-top: 6px; }
.field-error { display: block; color: #dc2626; font-size: 12px; min-height: 18px; }
.actions { display: flex; justify-content: flex-end; gap: 12px; margin-top: 20px; }
button { padding: 8px 16px; border: 1px solid #d1fae5; border-radius: 8px; cursor: pointer; }.save { background: #059669; color: white; }
</style>
