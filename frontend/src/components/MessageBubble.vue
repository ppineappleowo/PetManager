<script setup>
import { computed, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import PawIcon from './PawIcon.vue'
import { toast } from '../composables/useToast.js'
import {apiJson} from '../api/client.js'
import {useRouter} from 'vue-router'
import {auth} from '../composables/useAuth.js'
import {createAiDraft} from '../utils/aiDraft.js'
const router=useRouter(),feedbackBusy=ref(false)
async function feedback(value){if(feedbackBusy.value)return;feedbackBusy.value=true;try{await apiJson(`/api/v1/chat/requests/${props.message.requestId}/feedback`,{method:'PUT',body:JSON.stringify({value:props.message.feedback===value?'':value})});props.message.feedback=props.message.feedback===value?'':value}catch(e){toast(e.message,'error')}finally{feedbackBusy.value=false}}
function draftPost(){if(!confirm('将此回答带入发布编辑器？请检查并删除私人信息，确认内容后再发布。'))return;router.push({path:'/publish',state:{aiDraftId:createAiDraft(auth.token,props.message.content)}})}

const props = defineProps({ message: { type: Object, required: true }, busy: Boolean, canRetry: Boolean })
defineEmits(['edit', 'retry'])
const html = computed(() => DOMPurify.sanitize(marked.parse(props.message.content || '', { breaks: true })))
const imageUrl = computed(() => /^https?:\/\//i.test(props.message.imageUrl || '') ? props.message.imageUrl : '')

async function copy() {
  try {
    await navigator.clipboard.writeText(props.message.content)
    toast('已复制到剪贴板')
  } catch { toast('复制失败', 'error') }
}
</script>

<template>
  <article class="msg" :class="message.role" :aria-label="message.role === 'user' ? '你的消息' : 'AI 回答'">
    <div class="msg-avatar"><PawIcon v-if="message.role === 'assistant'" /><span v-else>👤</span></div>
    <div class="msg-content-wrap">
      <div class="msg-bubble" @dblclick="message.role === 'user' && !busy && $emit('edit', message.content)">
        <a v-if="imageUrl" :href="imageUrl" target="_blank" rel="noopener noreferrer"><img :src="imageUrl" alt="上传的宠物照片" class="msg-image" /></a>
        <div v-if="message.role === 'assistant' && message.content" class="markdown" v-html="html"></div>
        <div v-else-if="message.content" class="user-text">{{ message.content }}</div>
        <div v-else-if="message.pending" class="typing-indicator">🐾 AI 正在思考…</div>
        <p v-if="message.error" class="message-error" role="alert">{{ message.error }}</p>
        <p v-if="message.state === 'cancelled'" class="message-state">已停止{{ message.role === 'assistant' && message.content ? '，以上为部分回答' : '' }}</p>
        <p v-else-if="message.role === 'user' && message.state === 'sending'" class="message-state">正在处理…</p>
        <p v-else-if="message.role === 'user' && message.state === 'failed'" class="message-state">本轮请求失败</p>
      </div>
      <div v-if="message.role === 'assistant' && canRetry && ['failed', 'cancelled'].includes(message.state)" class="msg-actions">
        <button :disabled="busy" @click="$emit('retry', message.requestId)">重试</button>
      </div>
      <div v-if="message.content && !message.pending" class="msg-actions">
        <button v-if="message.role === 'assistant'" @click="copy">📋 复制</button>
        <button v-else :disabled="busy" @click="$emit('edit', message.content)">编辑后重发</button>
      </div>
      <details v-if="message.role==='assistant'&&message.sources?.length" class="sources"><summary>检索参考资料 · {{ message.sources.length }}</summary><p>这些资料来自本轮检索，请结合回答核对。</p><article v-for="source in message.sources" :key="source.id"><a v-if="/^https?:\/\//i.test(source.url||'')" :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.source }}</a><strong v-else>{{ source.source }}</strong><small v-if="source.version">版本 {{ source.version }}</small><p>{{ source.excerpt }}</p></article></details>
      <div v-if="message.role==='assistant'&&message.requestId&&message.state==='completed'" class="msg-actions"><button :disabled="feedbackBusy" :aria-pressed="message.feedback==='helpful'" @click="feedback('helpful')">有帮助</button><button :disabled="feedbackBusy" :aria-pressed="message.feedback==='unhelpful'" @click="feedback('unhelpful')">没帮助</button><button :disabled="busy" @click="draftPost">整理成日常</button></div>
    </div>
  </article>
</template>

<style scoped>
.msg { display: flex; gap: 10px; max-width: 82%; }
.sources{background:#f4f8f0;border:1px solid var(--line);border-radius:10px;padding:12px;margin-top:10px;font-size:12px;overflow-wrap:anywhere}.sources article{padding:10px 0;border-top:1px solid var(--line)}.sources small{display:block;color:var(--muted)}.sources p{white-space:pre-wrap}.msg-actions{flex-wrap:wrap}
.msg.user { align-self: flex-end; flex-direction: row-reverse; }
.msg.assistant { align-self: flex-start; }
.msg-avatar { width: 34px; height: 34px; flex-shrink: 0; border-radius: 12px; display: flex; align-items: center; justify-content: center; background: #f3f4f6; }
.assistant .msg-avatar { background: #386a50; color: white; }
.msg-avatar svg { width: 20px; height: 20px; }
.msg-content-wrap { min-width: 0; }
.msg-bubble { padding: 14px 18px; border-radius: 18px; font-size: 14px; line-height: 1.8; overflow-wrap: anywhere; background: white; border: 1px solid #e3e8df; box-shadow: 0 2px 8px #283b2c04; }
.user .msg-bubble { background: linear-gradient(135deg, #059669, #0d9488); color: white; border: none; border-top-right-radius: 4px; }
.assistant .msg-bubble { border-top-left-radius: 4px; }
.user-text { white-space: pre-wrap; }
.msg-image { max-width: min(220px, 100%); max-height: 240px; border-radius: 12px; display: block; margin-bottom: 8px; }
.msg-actions { display: flex; gap: 6px; margin-top: 5px; }
.msg-actions button { border: 1px solid #d1fae5; border-radius: 7px; padding: 3px 8px; background: #fffc; color: #6b7280; font-size: 11px; cursor: pointer; }
.typing-indicator { color: #6b7280; font-size: 13px; }
.message-error { color: #dc2626; }
.message-state { font-size: 12px; opacity: 0.8; }
.user .message-error { color: #fff; }
.markdown :deep(p + p) { margin-top: 10px; }
.markdown :deep(ul), .markdown :deep(ol) { padding-left: 22px; }
.markdown :deep(pre) { overflow-x: auto; background: #f3f4f6; border-radius: 8px; padding: 12px; white-space: pre; }
.markdown :deep(code) { background: #f3f4f6; border-radius: 4px; padding: 2px 4px; font-size: 0.9em; }
.markdown :deep(a) { color: #059669; }
.markdown :deep(blockquote) { border-left: 3px solid #34d399; padding-left: 12px; color: #6b7280; }
.markdown :deep(h1), .markdown :deep(h2), .markdown :deep(h3) { font-size: 1.15em; margin: 12px 0 6px; }
.markdown :deep(table) { display: block; max-width: 100%; overflow-x: auto; border-collapse: collapse; }
.markdown :deep(td), .markdown :deep(th) { padding: 6px 10px; border: 1px solid #d1fae5; }
.markdown :deep(img) { max-width: 100%; }
@media (max-width: 768px) { .msg { max-width: 96%; } }
</style>
