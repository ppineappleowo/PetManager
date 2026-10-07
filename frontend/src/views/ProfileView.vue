<script setup>
import { loadCurrentUser } from '../composables/useCurrentUser.js'

import { onMounted, reactive, ref } from 'vue'
import { useUnsavedChanges } from '../composables/useUnsavedChanges.js'
import { useRouter } from 'vue-router'
import { apiJson } from '../api/client.js'
import { auth, clearAuth } from '../composables/useAuth.js'
import PasswordDialog from '../components/PasswordDialog.vue'
import UserAvatar from '../components/UserAvatar.vue'
import { usernameError } from '../utils/validation.js'
import { toast } from '../composables/useToast.js'

const router = useRouter()
const activeSection = ref('details')
const user = ref(null), loading = ref(true), saving = ref(false), error = ref(''), passwordOpen = ref(false)
const form = reactive({ username: '', nickname: '', bio: '' })
const avatarBusy = ref(false)
const confirmLeave=useUnsavedChanges(()=>!!user.value && Object.keys(form).some(key=>form[key] !== (user.value[key]||'')),()=>saving.value||avatarBusy.value)
async function changeAvatar(event) {
  const file = event?.target?.files?.[0]
  if (event && !file) return
  if (avatarBusy.value) return
  error.value = ''
  if (file && (file.size > 5 * 1024 * 1024 || !['image/jpeg','image/png','image/webp'].includes(file.type))) {
    error.value = '请选择不超过 5 MB 的 JPEG、PNG 或 WebP 图片'
    event.target.value = ''; return
  }
  avatarBusy.value = true
  try {
    const data = await apiJson('/api/v1/community/me/avatar', file ? { method: 'PUT', body: file, headers: { 'Content-Type': file.type } } : { method: 'DELETE' })
    user.value.avatar_id = data.avatar_id
    toast(file ? '头像已更新' : '已恢复默认头像')
  } catch (reason) { error.value = reason.message }
  finally { avatarBusy.value = false; if (event) event.target.value = '' }
}
async function load() {
  loading.value = true; error.value = ''
  try {
    user.value = await loadCurrentUser()
    for (const field of Object.keys(form)) form[field] = user.value[field] || ''
  } catch (reason) { error.value = reason.message } finally { loading.value = false }
}
async function save() {
  if (saving.value || avatarBusy.value) return
  error.value = usernameError(form.username)
  if (error.value) return
  saving.value = true
  try {
    const updated = await apiJson('/api/v1/auth/me', { method: 'PATCH', body: JSON.stringify(form) })
    // 旧客户端按用户名保存当前会话；改名后沿用该账号原会话。
    const previousThread = sessionStorage.getItem(`pet_manager_thread_id:${auth.username}`)
    if (previousThread) sessionStorage.setItem(`pet_manager_thread_id:${updated.username}`, previousThread)
    auth.username = updated.username
    sessionStorage.setItem('username', updated.username)
    user.value = updated
    for (const key of Object.keys(form)) form[key] = updated[key] || ''
    toast('个人资料已保存')
  } catch (reason) { error.value = reason.message } finally { saving.value = false }
}
onMounted(load)
function logout() {
  if(!confirmLeave())return
  clearAuth()
  router.replace({ name: 'login' })
}
</script>

<template>
  <main class="profile-page">
    <div class="profile-container">
      <header class="page-heading">
        <div><h1>个人中心</h1><p>管理你的资料，与毛孩子一起成长。</p></div>
        <RouterLink class="back-link" to="/">← 返回社区</RouterLink>
      </header>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p v-if="loading" class="loading" role="status">正在加载个人资料…</p>
      <button v-else-if="!user" class="outline-button" @click="load">重新加载</button>
      <div v-else class="profile-layout">
        <aside class="profile-sidebar">
          <div class="identity">
            <UserAvatar class="profile-avatar" :user="user" />
            <h2>{{ user.nickname || user.username }}</h2>
            <p>@{{ user.username }}</p>
            <span class="role-badge"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 10c-3 0-4 3-6 5s0 6 3 4c2-1 4-1 6 0 3 2 5-2 3-4s-3-5-6-5Z"/><ellipse cx="5" cy="8" rx="2" ry="3"/><ellipse cx="10" cy="4" rx="2" ry="3"/><ellipse cx="16" cy="5" rx="2" ry="3"/><ellipse cx="20" cy="10" rx="2" ry="3"/></svg>{{ user.role === 'admin' ? '管理员' : '宠物家长' }}</span>
            <RouterLink class="public-link" :to="`/users/${user.id}`" aria-label="查看我的公开主页">查看公开主页 <span aria-hidden="true">↗</span></RouterLink>
          </div>
          <nav class="profile-nav" aria-label="个人中心导航">
            <button :class="{ active: activeSection === 'details' }" :aria-current="activeSection === 'details' ? 'page' : undefined" @click="activeSection = 'details'">
              <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="7" r="4"/><path d="M4 22v-3a8 8 0 0 1 16 0v3"/></svg>个人资料
            </button>
            <RouterLink to="/pets"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 11c-3 0-4 3-6 5s0 5 3 3c2-1 4-1 6 0 3 2 5-1 3-3s-3-5-6-5Z"/><ellipse cx="4" cy="9" rx="2" ry="3"/><ellipse cx="9" cy="4" rx="2" ry="3"/><ellipse cx="15" cy="4" rx="2" ry="3"/><ellipse cx="20" cy="9" rx="2" ry="3"/></svg>我的宠物</RouterLink>
            <button :class="{ active: activeSection === 'security' }" :aria-current="activeSection === 'security' ? 'page' : undefined" @click="activeSection = 'security'">
              <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="10" width="16" height="12" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 5v3"/></svg>账号与安全
            </button>
          </nav>
          <RouterLink class="public-link" style="margin-bottom:20px" to="/bookmarks">我的收藏 ↗</RouterLink><RouterLink class="public-link" style="margin-bottom:20px" to="/notifications">消息通知 ↗</RouterLink><RouterLink class="public-link" style="margin-bottom:20px" to="/reports">我的举报 ↗</RouterLink><RouterLink class="public-link" style="margin-bottom:20px" to="/moderation">处理记录 ↗</RouterLink><RouterLink class="public-link" style="margin-bottom:20px" to="/connections">我的关注与粉丝 ↗</RouterLink><div class="sidebar-footer"><button class="signout" :disabled="saving || avatarBusy" @click="logout"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 4H5v16h5m-1-8h12m-4-4 4 4-4 4"/></svg>退出登录</button></div>
        </aside>
        <div class="profile-content">
          <section v-show="activeSection === 'details'" class="card details-card" aria-labelledby="details-title">
            <header class="card-heading"><h2 id="details-title">个人资料</h2><p>这些信息将展示在你的公开主页。</p></header>
            <div class="avatar-settings">
              <span class="avatar-label">头像</span><UserAvatar class="edit-avatar" :user="user" />
              <div class="avatar-controls"><div class="avatar-actions"><label class="avatar-upload" :class="{ busy: avatarBusy || saving }">{{ avatarBusy ? '正在更新…' : '更换头像' }}<input aria-label="上传头像" type="file" accept="image/jpeg,image/png,image/webp" :disabled="avatarBusy || saving" @change="changeAvatar" /></label><button v-if="user.avatar_id" class="text-button" :disabled="avatarBusy || saving" @click="changeAvatar()">移除头像</button></div><p>支持 JPG、PNG、WebP，最大 5 MB。</p></div>
            </div>
            <form @submit.prevent="save">
              <h3 class="section-title">基本信息</h3>
              <div class="field-grid">
                <div class="field"><label for="profile-username">用户名</label><input id="profile-username" v-model="form.username" maxlength="32" required :disabled="saving" autocomplete="username" aria-describedby="username-hint" /><small id="username-hint">用户名用于登录，2–32 位中英文、数字或下划线。</small></div>
                <div class="field"><label for="profile-nickname">昵称</label><input id="profile-nickname" v-model="form.nickname" maxlength="32" :disabled="saving" autocomplete="nickname" placeholder="怎么称呼你？" /><small>选择一个让人记住的名字。</small></div>
              </div>
              <div class="field bio-field"><label for="profile-bio">个人简介</label><textarea id="profile-bio" v-model="form.bio" maxlength="300" :disabled="saving" placeholder="分享你和毛孩子的故事…" aria-describedby="bio-counter"></textarea><small id="bio-counter" class="counter">{{ form.bio.length }} / 300</small></div>
              <div class="form-footer"><span>修改后记得保存。</span><button type="submit" class="primary" :disabled="saving || avatarBusy">{{ saving ? '保存中…' : '保存修改' }}</button></div>
            </form>
          </section>
          <section v-show="activeSection === 'security'" class="card security-card" aria-labelledby="security-title">
            <header class="card-heading"><h2 id="security-title">账号与安全</h2><p>管理你的登录信息，安心记录每一份陪伴。</p></header>
            <dl><div><dt>手机号</dt><dd>{{ user.phone || '未绑定' }}</dd></div><div><dt>注册时间（UTC）</dt><dd>{{ user.created_at }}</dd></div></dl>
            <div class="password-row"><div><h3>登录密码</h3><p>修改后需要重新登录。</p></div><button class="outline-button" :disabled="saving || avatarBusy" @click="passwordOpen = true">修改密码</button></div>
          </section>
          <RouterLink class="pet-shortcut" to="/pets"><span class="pet-symbol" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 10c-3 0-4 3-6 5s0 6 3 4c2-1 4-1 6 0 3 2 5-2 3-4s-3-5-6-5Z"/><ellipse cx="5" cy="8" rx="2" ry="3"/><ellipse cx="10" cy="4" rx="2" ry="3"/><ellipse cx="16" cy="5" rx="2" ry="3"/><ellipse cx="20" cy="10" rx="2" ry="3"/></svg></span><div><h3>我的宠物</h3><p>管理毛孩子的资料。</p></div><span class="pet-action">管理宠物 <span aria-hidden="true">→</span></span></RouterLink>
        </div>
      </div>
    </div>
    <PasswordDialog v-if="passwordOpen" @close="passwordOpen = false" />
  </main>
</template>

<style scoped>
.profile-page{--profile-ink:#123737;--profile-muted:#637a80;--profile-line:#dfe7e3;--profile-green:#285947;min-height:100dvh;background:#fafbf8;color:var(--profile-ink);font-size:15px}
.profile-container{max-width:1152px;margin:0 auto;padding:28px 0 36px}.page-heading{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:28px}h1{font-size:40px;line-height:1.3;letter-spacing:1px;margin:0 0 6px}.page-heading p{font-size:17px;color:var(--profile-muted);line-height:1.7}.back-link{font-size:13px;color:var(--profile-muted);text-decoration:none;white-space:nowrap}.back-link:hover{color:var(--profile-green)}
.profile-layout{display:grid;grid-template-columns:260px minmax(0,1fr);gap:16px;align-items:start}.profile-sidebar{border:1px solid var(--profile-line);border-radius:15px;padding:34px 20px 20px;min-height:788px;display:flex;flex-direction:column;background:#ffffff60}.identity{text-align:center;padding:0 3px 25px;border-bottom:1px solid var(--profile-line);min-width:0}.profile-avatar{width:98px;height:98px;font-size:44px;background:#e5eee8;color:#274f44}.identity h2{font-size:25px;margin:12px 0 4px;line-height:1.4;overflow-wrap:anywhere}.identity p{color:var(--profile-muted);overflow-wrap:anywhere}.role-badge{display:inline-flex;align-items:center;gap:8px;border-radius:30px;padding:7px 14px;background:#e2efe4;color:var(--profile-green);font-size:13px;font-weight:600;margin:12px 0 22px}.role-badge svg{width:17px;height:17px;fill:currentColor}.public-link{display:flex;justify-content:center;align-items:center;gap:9px;border:1px solid #527c69;border-radius:10px;min-height:44px;text-decoration:none;color:var(--profile-green);font-weight:600;font-size:14px}.public-link:hover{background:#eaf2ec}
.profile-nav{display:grid;gap:10px;margin:24px 0}.profile-nav button,.profile-nav a,.signout{display:flex;align-items:center;gap:22px;text-decoration:none;border:0;background:transparent;color:#375659;border-radius:9px;padding:13px 12px;text-align:left;font:inherit;cursor:pointer;min-height:49px}.profile-nav .active{background:#e8f2e9;color:#214f40;font-weight:650}.profile-nav a:hover,.profile-nav button:hover,.signout:hover{background:#edf3ed}.profile-nav svg,.signout svg{width:23px;height:23px;flex-shrink:0;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}.sidebar-footer{border-top:1px solid var(--profile-line);margin-top:auto;padding-top:17px}.signout{width:100%;font-size:14px}
.profile-content{display:grid;gap:17px;min-width:0}.card{border:1px solid var(--profile-line);border-radius:16px;padding:30px 34px 22px;background:#fff;box-shadow:0 2px 10px #163e2a02}.card-heading h2{font-size:28px;letter-spacing:.5px;line-height:1.5;margin:0}.card-heading p{color:var(--profile-muted);line-height:1.7;margin:3px 0 0;font-size:15px}.avatar-settings{display:flex;gap:28px;align-items:center;padding:30px 0 32px;border-bottom:1px solid var(--profile-line)}.avatar-label{align-self:flex-start;font-weight:650;min-width:70px;padding-top:3px}.edit-avatar{width:84px;height:84px;font-size:40px;background:#e8efe9;color:#274f44}.avatar-controls{min-width:0}.avatar-actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.avatar-controls p{color:var(--profile-muted);font-size:13px;line-height:1.8;margin-top:10px}.avatar-upload{position:relative;overflow:hidden;display:inline-flex;justify-content:center;align-items:center;border:1px solid #d1dcda;border-radius:10px;padding:10px 25px;cursor:pointer;font-size:14px;font-weight:600}.avatar-upload input{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%}.avatar-upload:hover{background:#f3f7f3}.avatar-upload.busy{opacity:.55;cursor:wait}.text-button{border:0;background:transparent;color:var(--profile-muted);font:inherit;font-size:13px;cursor:pointer}
.section-title{font-size:19px;margin:23px 0 19px}.field-grid{display:grid;grid-template-columns:1fr 1fr;gap:25px}.field{min-width:0}.field label{display:block;font-weight:650;margin-bottom:9px;font-size:16px}.field input,.field textarea{width:100%;border:1px solid #cfdad8;border-radius:8px;padding:11px 16px;font:inherit;color:var(--profile-ink);background:#fff;line-height:1.6;transition:border-color .15s,box-shadow .15s}.field input::placeholder,.field textarea::placeholder{color:var(--profile-muted)}.field input:focus,.field textarea:focus{outline:none;border-color:#527c69;box-shadow:0 0 0 3px #e9f2eb}.field small{display:block;color:var(--profile-muted);font-size:13px;line-height:1.7;margin-top:8px}.bio-field{margin-top:28px}.field textarea{min-height:116px;resize:vertical;vertical-align:top}.field .counter{text-align:right;margin-top:8px}.form-footer{display:flex;align-items:center;justify-content:space-between;gap:15px;border-top:1px solid var(--profile-line);margin-top:20px;padding-top:20px}.form-footer>span{font-size:13px;color:var(--profile-muted)}.primary,.outline-button{border:1px solid var(--profile-green);border-radius:9px;padding:12px 25px;font:inherit;font-size:14px;font-weight:600;cursor:pointer}.primary{min-width:142px;background:var(--profile-green);color:white;box-shadow:0 2px 5px #28594715}.primary:hover:not(:disabled){background:#1d4537}.outline-button{background:white;color:var(--profile-green)}button:disabled{opacity:.5;cursor:not-allowed}button:focus-visible,a:focus-visible,.avatar-upload:focus-within{outline:3px solid #81aa92;outline-offset:3px}
.pet-shortcut{display:flex;align-items:center;gap:23px;padding:23px 30px;background:#ffffffb0;border:1px solid var(--profile-line);border-radius:16px;text-decoration:none;color:var(--profile-ink)}.pet-shortcut:hover{background:#f1f7f1;border-color:#b8cec1}.pet-symbol{width:58px;height:58px;display:grid;place-items:center;border-radius:50%;background:#e7f1e8;color:#285947;flex-shrink:0}.pet-symbol svg{width:29px;height:29px;fill:currentColor}.pet-shortcut h3{font-size:18px;margin:0 0 5px}.pet-shortcut p{font-size:13px;color:var(--profile-muted)}.pet-action{margin-left:auto;color:#327553;font-weight:600;font-size:14px;white-space:nowrap}.pet-action span{margin-left:8px}.security-card{min-height:390px}.security-card dl{margin:30px 0}.security-card dl>div{display:flex;justify-content:space-between;gap:20px;padding:18px 0;border-bottom:1px solid var(--profile-line)}dt{color:var(--profile-muted)}dd{margin:0;text-align:right;overflow-wrap:anywhere;min-width:0}.password-row{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:28px 0 12px}.password-row h3{font-size:17px}.password-row p{color:var(--profile-muted);font-size:13px;margin-top:8px}.error{padding:14px 18px;background:#fff0ee;color:#a4433b;border-radius:10px;margin-bottom:20px}.loading{padding:70px 20px;text-align:center;color:var(--profile-muted)}
@media(min-width:1400px){.profile-container{max-width:1152px}.profile-layout{grid-template-columns:260px minmax(0,1fr)}}
@media(max-width:1210px){.profile-container{margin:0 28px}.profile-layout{grid-template-columns:235px minmax(0,1fr)}.card{padding:28px 26px 22px}.avatar-label{min-width:48px}.avatar-settings{gap:20px}}
@media(max-width:800px){.profile-container{margin:0 20px;padding-top:24px}.profile-layout{grid-template-columns:1fr;gap:20px}h1{font-size:32px}.page-heading p{font-size:14px}.profile-sidebar{min-height:0;padding:22px}.identity{display:grid;grid-template-columns:68px 1fr;column-gap:18px;text-align:left;align-items:center;padding-bottom:20px}.profile-avatar{width:68px;height:68px;font-size:32px;grid-row:1/4}.identity h2{font-size:22px;margin:0}.identity p{font-size:13px}.role-badge{justify-self:start;margin:7px 0 0;padding:4px 10px;font-size:12px}.public-link{grid-column:1/-1;margin-top:18px;min-height:40px}.profile-nav{grid-template-columns:repeat(3,minmax(0,1fr));gap:4px;margin:16px 0}.profile-nav button,.profile-nav a{justify-content:center;gap:8px;padding:12px 6px;font-size:13px}.profile-nav svg{width:19px;height:19px}.sidebar-footer{padding-top:10px}.signout{justify-content:center;min-height:36px;padding:8px;gap:10px}.card-heading h2{font-size:25px}.pet-shortcut{padding:20px}.profile-content{gap:16px}}
@media(max-width:480px){.profile-container{margin:0 16px;padding-top:22px}.page-heading{align-items:flex-start;gap:8px;margin-bottom:22px}h1{font-size:29px}.page-heading p{font-size:12px}.back-link{font-size:12px;margin-top:10px}.profile-sidebar{padding:20px 16px}.card{padding:24px 20px 20px}.card-heading p{font-size:13px}.avatar-settings{flex-wrap:wrap;gap:16px;padding:24px 0}.avatar-label{flex-basis:100%;padding:0}.edit-avatar{width:62px;height:62px;font-size:30px}.avatar-controls{flex:1}.avatar-upload{padding:9px 16px;font-size:13px}.avatar-controls p{font-size:11px}.field-grid{grid-template-columns:1fr;gap:20px}.bio-field{margin-top:22px}.field small{font-size:12px}.field label{font-size:14px}.field input,.field textarea{font-size:14px}.form-footer>span{font-size:12px}.primary{min-width:114px;padding:11px 16px}.pet-shortcut{gap:12px;padding:18px 16px}.pet-symbol{width:42px;height:42px}.pet-symbol svg{width:24px;height:24px}.pet-shortcut h3{font-size:16px}.pet-shortcut p{font-size:12px}.pet-action{font-size:12px}.pet-action span{margin-left:2px}.password-row{flex-wrap:wrap}.security-card dl>div{font-size:13px}}
</style>
