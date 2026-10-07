<script setup>
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import PawIcon from '../components/PawIcon.vue'
import { apiJson } from '../api/client.js'
import { setAuth } from '../composables/useAuth.js'
import { toast } from '../composables/useToast.js'
import { usernameError, passwordError } from '../utils/validation.js'

const router = useRouter()
const route = useRoute()
const tab = ref('login')
const busy = ref(false)
const showPassword = ref(false)
const login = reactive({ username: '', password: '' })
const registration = reactive({ phone: '', password: '', confirm: '' })
const errors = reactive({ phone: '', password: '', confirm: '' })
const loginErrors = reactive({ username: '', password: '' })
const loginError = ref('')

function switchTab(value) {
  tab.value = value
  Object.keys(errors).forEach((key) => { errors[key] = '' })
}

async function submitLogin() {
  if (busy.value) return
  loginErrors.username = usernameError(login.username)
  loginErrors.password = passwordError(login.password)
  if (Object.values(loginErrors).some(Boolean)) return
  loginError.value = ''
  busy.value = true
  try {
    const data = await apiJson('/api/v1/auth/login', {
      authenticated: false, method: 'POST',
      body: JSON.stringify({ username: login.username.trim(), password: login.password }),
    })
    setAuth(data)
    const target = route.query.redirect
    await router.replace(typeof target === 'string' && target.startsWith('/') && !target.startsWith('//') && !target.startsWith('/login') ? target : '/')
  } catch (error) {
    loginError.value = error.message
    Object.assign(loginErrors, error.fields || {})
  }
  finally { busy.value = false }
}

async function submitRegistration() {
  if (busy.value) return
  const phone = registration.phone.trim()
  errors.phone = /^1[3-9][0-9]{9}$/.test(phone) ? '' : '请输入正确的中国大陆手机号'
  errors.password = passwordError(registration.password)
  errors.confirm = registration.password !== registration.confirm ? '两次输入的密码不一致' : ''
  if (Object.values(errors).some(Boolean)) return
  busy.value = true
  try {
    await apiJson('/api/v1/auth/register', { authenticated: false, method: 'POST',
      body: JSON.stringify({ phone, password: registration.password }) })
    login.username = phone
    login.password = ''
    Object.assign(registration, { phone: '', password: '', confirm: '' })
    switchTab('login')
    toast('注册成功！请登录')
  } catch (error) { Object.assign(errors, error.fields || {}); toast(error.message, 'error') }
  finally { busy.value = false }
}
</script>

<template>
  <main class="login-page">
    <div class="bg-decor" aria-hidden="true"><div v-for="n in 6" :key="n" class="bg-paw">🐾</div><div class="bg-circle"></div><div class="bg-circle"></div></div>
    <div class="container"><div class="card">
      <div class="logo"><div class="logo-icon"><PawIcon /></div><h1>百宠集</h1></div>
      <div class="tabs" :class="{ 'register-active': tab === 'register' }">
        <button class="tab" :class="{ active: tab === 'login' }" :disabled="busy" @click="switchTab('login')">登 录</button>
        <button class="tab" :class="{ active: tab === 'register' }" :disabled="busy" @click="switchTab('register')">注 册</button>
      </div>
      <form v-if="tab === 'login'" @submit.prevent="submitLogin" novalidate>
        <div class="form-group"><label for="login-username">手机号或用户名</label><div class="input-wrap">
          <input id="login-username" v-model="login.username" placeholder="请输入手机号或原有用户名" autocomplete="username" :disabled="busy" :aria-invalid="!!loginErrors.username" aria-describedby="login-name-error" @blur="loginErrors.username = usernameError(login.username)" />
        </div><p id="login-name-error" class="error-msg" :class="{ show: loginErrors.username }">{{ loginErrors.username }}</p></div>
        <div class="form-group"><label for="login-password">密码</label><div class="input-wrap">
          <input id="login-password" v-model="login.password" :type="showPassword ? 'text' : 'password'" placeholder="请输入密码" autocomplete="current-password" :disabled="busy" :aria-invalid="!!loginErrors.password" aria-describedby="login-password-error" @blur="loginErrors.password = passwordError(login.password)" />
          <button type="button" class="pw-toggle" aria-label="显示或隐藏密码" @click="showPassword = !showPassword">{{ showPassword ? '🙈' : '👁' }}</button>
        </div><p id="login-password-error" class="error-msg" :class="{ show: loginErrors.password }">{{ loginErrors.password }}</p></div>
        <p v-if="loginError" class="error-msg show" role="alert">{{ loginError }}</p>
        <button class="btn-submit" :disabled="busy" type="submit">{{ busy ? '正在登录…' : '登 录' }}</button>
      </form>
      <form v-else @submit.prevent="submitRegistration" novalidate>
        <div class="form-group"><label for="register-phone">手机号</label><div class="input-wrap">
          <input id="register-phone" v-model="registration.phone" type="tel" maxlength="11" placeholder="中国大陆手机号" autocomplete="tel-national" :disabled="busy" :aria-invalid="!!errors.phone" />
        </div><p class="error-msg" :class="{ show: errors.phone }">{{ errors.phone }}</p></div>
        <div class="form-group"><label for="register-password">密码</label><div class="input-wrap">
          <input id="register-password" v-model="registration.password" :class="{ error: errors.password }" :type="showPassword ? 'text' : 'password'" placeholder="至少 6 位字符" autocomplete="new-password" :disabled="busy" :aria-invalid="!!errors.password" aria-describedby="password-error" />
          <button type="button" class="pw-toggle" aria-label="显示或隐藏密码" @click="showPassword = !showPassword">{{ showPassword ? '🙈' : '👁' }}</button>
        </div><p id="password-error" class="error-msg" :class="{ show: errors.password }">{{ errors.password }}</p></div>
        <div class="form-group"><label for="register-confirm">确认密码</label><div class="input-wrap">
          <input id="register-confirm" v-model="registration.confirm" :class="{ error: errors.confirm }" :type="showPassword ? 'text' : 'password'" placeholder="再次输入密码" autocomplete="new-password" :disabled="busy" :aria-invalid="!!errors.confirm" aria-describedby="confirm-error" />
        </div><p id="confirm-error" class="error-msg" :class="{ show: errors.confirm }">{{ errors.confirm }}</p></div>
        <button class="btn-submit" :disabled="busy" type="submit">{{ busy ? '正在注册…' : '注 册' }}</button>
      </form>
      <div class="hint">🐶 首次使用？请先注册账号 🐱</div>
    </div></div>
  </main>
</template>

<style src="../assets/login.css" scoped></style>
<style scoped>
.login-page { min-height: 100dvh; overflow-y: auto; }
</style>
