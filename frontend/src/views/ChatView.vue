<script setup>
import { loadCurrentUser } from '../composables/useCurrentUser.js'

import { nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import PawIcon from '../components/PawIcon.vue'
import MessageBubble from '../components/MessageBubble.vue'
import { auth } from '../composables/useAuth.js'
import { useChat } from '../composables/useChat.js'
import { toast } from '../composables/useToast.js'
import {community} from '../api/community.js'

const router = useRouter()
const { threadId, threads, messages, draft, selectedFile, selectedPet,sending, stopping, loading, status, error, canSend,
  lastRequestId, initialize, switchThread, newThread, removeThread, send, stop, retry } = useChat()
const isAdmin = ref(false)
const pets=ref([]),petError=ref('')
async function loadPets(){try{pets.value=(await community('/me/pets')).items||[];petError.value=''}catch(e){petError.value=e.message}}
onMounted(loadPets)
onMounted(async () => { try { isAdmin.value = (await loadCurrentUser()).role === 'admin' } catch { /* 主界面已有认证错误处理 */ } })
const sidebarOpen = ref(false)
const chatArea = ref(null)
const textInput = ref(null)
const fileInput = ref(null)
const deletionId = ref(null)
const deleting = ref(false)
let scrolledUp = false
const tips = [
  ['🔍 识别品类', '帮我识别这只宠物的品种'], ['💊 常见病科普', '宠物常见病有哪些？如何预防？'],
  ['🍖 喂食方案', '请给我一份科学的宠物喂养方案'], ['🛁 洗护建议', '宠物洗护的正确方法和频率'],
  ['🎾 训练技巧', '如何训练宠物养成良好的习惯？'], ['❤️ 健康评估', '请帮我评估这只宠物的健康状况'],
]

async function scrollToBottom() {
  await nextTick()
  if (chatArea.value && !scrolledUp) chatArea.value.scrollTop = chatArea.value.scrollHeight
}
function trackScroll() {
  const el = chatArea.value
  scrolledUp = el.scrollHeight - el.scrollTop - el.clientHeight > 60
}
watch(() => [messages.value.length, messages.value.at(-1)?.content, status.value, loading.value], scrollToBottom)
watch(draft, async () => {
  await nextTick()
  if (textInput.value) {
    textInput.value.style.height = 'auto'
    textInput.value.style.height = Math.min(textInput.value.scrollHeight, 120) + 'px'
  }
})

function fillPrompt(text) {
  if (sending.value) return
  draft.value = text
  textInput.value?.focus()
}
function selectImage(event) {
  const file = event.target.files[0]
  if (file && !file.type.startsWith('image/')) toast('请选择图片文件', 'error')
  else if (file) selectedFile.value = file
  event.target.value = ''
}
async function selectThread(id) {
  sidebarOpen.value = false
  scrolledUp = false
  await switchThread(id)
}
function createThread() {
  newThread()
  sidebarOpen.value = false
  scrolledUp = false
  textInput.value?.focus()
}
async function submit() {
  scrolledUp = false
  await send()
  textInput.value?.focus()
}
function keydown(event) {
  if (event.isComposing) return
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); submit() }
  if (event.key === 'Escape') { selectedFile.value = null; sidebarOpen.value = false }
}
async function confirmDelete() {
  if (deleting.value) return
  deleting.value = true
  if (await removeThread(deletionId.value)) deletionId.value = null
  deleting.value = false
}
onMounted(async () => { await initialize(); textInput.value?.focus() })
</script>

<template>
  <div class="chat-page">
    <div class="bg-decor" aria-hidden="true"><div v-for="n in 3" :key="n" class="bg-decor-circle"></div></div>
    <div class="sidebar-backdrop" :class="{ show: sidebarOpen }" @click="sidebarOpen = false"></div>
    <aside class="sidebar" :class="{ open: sidebarOpen }" aria-label="历史会话">
      <div class="sidebar-header"><div class="sidebar-logo"><div class="icon"><PawIcon /></div><h1>百宠集 · AI 助手</h1></div></div>
      <button class="btn-new-chat" :disabled="sending" @click="createThread">＋ 新建会话</button>
      <div class="thread-list">
        <div v-if="!threads.length" class="thread-empty">暂无历史会话<br />开始一段新的对话吧 🐾</div>
        <div v-for="thread in threads" :key="thread.thread_id" class="thread-item" :class="{ active: threadId === thread.thread_id }">
          <button class="thread-select" :disabled="sending" :title="thread.title" @click="selectThread(thread.thread_id)">
            <span class="thread-icon">{{ threadId === thread.thread_id ? '🐾' : '💬' }}</span>
            <span class="thread-info"><span class="thread-title">{{ thread.title }}</span><span class="thread-meta">{{ thread.message_count || 0 }} 条消息</span></span>
          </button>
          <button class="thread-delete" :disabled="sending" :aria-label="'删除会话 ' + thread.title" @click="deletionId = thread.thread_id">×</button>
        </div>
      </div>
    </aside>
    <main class="main">
      <header class="main-header">
        <button class="btn-toggle-sidebar" aria-label="展开会话列表" :aria-expanded="sidebarOpen" @click="sidebarOpen = !sidebarOpen">☰</button>
        <span class="main-header-title">宠物养护咨询</span><span class="header-spacer"></span>
        <button class="admin-entry" @click="router.push('/' )">返回社区</button><button v-if="isAdmin" class="admin-entry" :disabled="sending" @click="router.push('/admin')">管理后台</button>
        <button class="profile-entry" :disabled="sending" aria-label="个人中心" :title="auth.username + ' · 个人中心'" @click="router.push('/profile')">
          <span class="profile-avatar" aria-hidden="true">{{ auth.username.slice(0, 1).toUpperCase() || 'U' }}</span>
          <span>个人中心</span><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="m9 6 6 6-6 6" /></svg>
        </button>
      </header>
      <div ref="chatArea" class="chat-area" @scroll="trackScroll">
        <div class="messages" :aria-busy="loading || sending">
          <p v-if="loading" class="state-hint" role="status">正在加载会话…</p>
          <div v-else-if="!messages.length" class="welcome">
            <div class="welcome-icon"><div class="welcome-icon-inner"><PawIcon /></div></div>
            <h2>🐶 你好，我是你的 AI 宠物管家 🐱</h2>
            <p>上传宠物照片或描述宠物情况，我会为你提供专业的养护建议</p>
            <div class="welcome-tips"><button v-for="[label, prompt] in tips" :key="label" class="welcome-tip" @click="fillPrompt(prompt)">{{ label }}</button></div>
          </div>
          <MessageBubble v-for="message in messages" :key="message.id" :message="message" :busy="sending" :can-retry="message.requestId === lastRequestId" @edit="fillPrompt" @retry="retry" />
          <p v-if="status" class="state-hint" role="status">{{ status }}</p>
          <p v-if="error" class="request-error" role="alert">{{ error }}</p>
        </div>
      </div>
      <form class="input-area" @submit.prevent="submit">
        <div class="pet-context"><label>本次咨询背景 <select v-model="selectedPet" :disabled="sending||loading"><option :value="null">不使用宠物档案</option><option v-for="pet in pets" :key="pet.id" :value="pet.id">{{ pet.name }}</option></select></label><small>仅在选择后发送该宠物资料用于回答。</small><button v-if="petError" type="button" @click="loadPets">重试加载宠物</button></div>
        <div class="input-row">
          <button type="button" class="btn-upload" :class="{ 'has-image': selectedFile }" :disabled="sending || loading" aria-label="上传图片" title="添加图片" @click="fileInput.click()"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M12 5v14M5 12h14" /></svg></button>
          <input ref="fileInput" type="file" accept="image/*" hidden @change="selectImage" />
          <div class="textarea-wrap">
            <div v-if="selectedFile" class="img-preview-tag" style="display: flex">📷 {{ selectedFile.name }}<button type="button" :disabled="sending" aria-label="移除图片" @click="selectedFile = null">×</button></div>
            <textarea ref="textInput" v-model="draft" rows="1" :disabled="sending || loading" aria-label="宠物咨询内容" placeholder="描述你的宠物情况... (Ctrl+Enter 发送)" @keydown="keydown"></textarea>
          </div>
          <button v-if="sending" class="btn-stop" type="button" :disabled="stopping" @click="stop">{{ stopping ? '停止中…' : '停止生成' }}</button>
          <button v-else class="btn-send" type="submit" :disabled="!canSend" aria-label="发送消息">➤</button>
        </div>
      </form>
    </main>
    <div v-if="deletionId" class="confirm-overlay" @keydown.esc="!deleting && (deletionId = null)">
      <section class="confirm-dialog" v-focus-trap role="dialog" aria-modal="true" aria-labelledby="delete-title">
        <h2 id="delete-title">确定删除此会话？</h2><p>此会话的历史消息将被删除。</p>
        <div><button :disabled="deleting" @click="deletionId = null">取消</button><button :disabled="deleting" class="confirm-delete" @click="confirmDelete">{{ deleting ? '正在删除…' : '确认删除' }}</button></div>
      </section>
    </div>
  </div>
</template>

<style src="../assets/chat.css" scoped></style>
<style scoped>
.chat-page { height: 100dvh; }
.pet-context{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:12px;color:#667c6b;margin-bottom:8px}.pet-context select{font:inherit;padding:6px;border:1px solid #d8e4dd;border-radius:8px;max-width:210px;background:white}.pet-context small{font-size:11px}
.main { height: 100dvh; }
.header-spacer { flex: 1; }
.btn-stop { flex-shrink: 0; background: #fff1f2; color: #be123c; border: 1px solid #fecdd3; border-radius: 12px; padding: 10px; cursor: pointer; }
.main-header { flex-wrap: nowrap; gap: 12px; }
.main-header-title { white-space: nowrap; }
.profile-entry { display: inline-flex; align-items: center; gap: 9px; flex-shrink: 0; padding: 5px 10px 5px 5px; border: 1px solid #ccebdd; border-radius: 999px; background: #fff; color: #17694f; font-size: 13px; font-weight: 600; cursor: pointer; box-shadow: 0 2px 8px #146b4f08; transition: background .2s, box-shadow .2s; }
.profile-entry:hover:not(:disabled) { background: #ecfdf5; box-shadow: 0 3px 12px #146b4f14; }
.profile-avatar { display: grid; place-items: center; width: 29px; height: 29px; border-radius: 50%; background: #dff5e9; color: #16825d; font-size: 13px; }
.profile-entry svg { width: 14px; height: 14px; }
.admin-entry { border: 0; background: transparent; color: #497361; font-size: 12px; cursor: pointer; padding: 8px 0; white-space: nowrap; }
.btn-upload svg { width: 23px; height: 23px; display: block; }
.thread-select { display: flex; align-items: center; gap: 10px; flex: 1; min-width: 0; border: none; background: transparent; text-align: left; cursor: pointer; }
.thread-title, .thread-meta { display: block; }
.thread-item .thread-delete { flex-shrink: 0; }
.textarea-wrap { min-width: 0; }
.img-preview-tag { max-width: 100%; overflow-wrap: anywhere; }
.state-hint { align-self: center; color: var(--text-secondary); font-size: 13px; }
.request-error { color: #dc2626; font-size: 13px; text-align: center; }
.confirm-overlay { position: fixed; inset: 0; background: #0005; display: grid; place-items: center; z-index: 50; padding: 20px; }
.confirm-dialog { background: white; padding: 28px; border-radius: 18px; max-width: 380px; width: 100%; box-shadow: var(--shadow-lg); }
.confirm-dialog h2 { font-size: 18px; }.confirm-dialog p { font-size: 14px; color: #6b7280; margin: 14px 0 24px; }
.confirm-dialog div { display: flex; justify-content: flex-end; gap: 12px; }
.confirm-dialog button { border: 1px solid var(--border); padding: 8px 16px; border-radius: 8px; cursor: pointer; }
.confirm-dialog .confirm-delete { background: #dc2626; color: white; border-color: #dc2626; }
@media (max-width: 480px) { .main-header { gap: 8px; } .profile-entry { gap: 5px; padding-right: 8px; } .profile-entry svg { display: none; } .profile-avatar { width: 25px; height: 25px; } .main-header-title { font-size: 14px; } }
</style>
