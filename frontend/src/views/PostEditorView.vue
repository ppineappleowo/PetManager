<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import CommunityShell from '../components/CommunityShell.vue'
import CommunityImage from '../components/CommunityImage.vue'
import { community, categories, commonTags } from '../api/community.js'
import { toast } from '../composables/useToast.js'
import {auth} from '../composables/useAuth.js'
import {takeAiDraft} from '../utils/aiDraft.js'
const route = useRoute(), router = useRouter(), editing = !!route.params.id
const form = reactive({ title: '', body: '', category: 'general', tags: [], pet_ids: [],ai_generated:false })
const aiDraft=!editing?takeAiDraft(auth.token,history.state?.aiDraftId):''
if(!editing&&aiDraft){form.body=('【AI 辅助整理，请核实内容】\n'+aiDraft).slice(0,5000);form.tags=['AI辅助'];form.ai_generated=true}
const pets = ref([]), petError = ref('')
async function loadPets() {
  petError.value = ''
  try { pets.value = ((await community('/me/pets')).items || []).filter(pet=>!pet.hidden) }
  catch (reason) { petError.value = reason.message }
}
const images = ref([]), tagInput = ref(''), error = ref(''), loading = ref(editing), busy = ref(false), loaded = ref(!editing)
const version = ref(1), baseline = ref(''), saved = ref(false)
const requestKey = crypto.randomUUID()
const snapshot = () => JSON.stringify({ ...form, images: images.value.map(i => i.id || i.preview) })
const dirty = computed(() => loaded.value && !saved.value && snapshot() !== baseline.value)
const uploading = computed(() => images.value.some(i => i.busy))
function leave() { return !(busy.value || uploading.value) && (!dirty.value || window.confirm('还有未提交的内容，确定离开吗？')) }
onBeforeRouteLeave(leave)
function beforeUnload(event) { if (dirty.value || busy.value || uploading.value) { event.preventDefault(); event.returnValue = '' } }
window.addEventListener('beforeunload', beforeUnload)
onBeforeUnmount(() => { window.removeEventListener('beforeunload', beforeUnload); images.value.forEach(i => { if (i.preview) URL.revokeObjectURL(i.preview) }) })
baseline.value = snapshot()
async function load() {
  loading.value = true; error.value = ''
  try {
    const post = await community(`/mine/${route.params.id}`)
    Object.assign(form, {title:post.title, body:post.body, category:post.category, tags:post.tags, pet_ids:post.pet_ids || [],ai_generated:!!post.ai_generated})
    images.value = post.images.map(id => ({id, busy:false, error:''})); version.value = post.version
    baseline.value = snapshot(); loaded.value = true
  } catch (reason) { error.value = reason.message }
  finally { loading.value = false }
}
function reload() { if (!dirty.value || window.confirm('重新加载将放弃当前修改，继续吗？')) load() }
onMounted(() => { loadPets(); if (editing) load() })
function addTag(value = tagInput.value) {
  value = value.trim().replace(/^#/, '')
  if (!value || form.tags.includes(value)) { tagInput.value = ''; return }
  if (value.length > 12 || form.tags.length >= 5) { error.value = '最多 5 个标签，每个标签最多 12 字'; return }
  form.tags.push(value); tagInput.value = ''; error.value = ''
}
async function upload(item) {
  if (item.busy) return
  item.busy = true; item.error = ''
  try { item.id = (await community('/media', {method:'POST', headers:{'Content-Type': item.file.type || 'application/octet-stream'}, body:item.file})).id }
  catch (reason) { item.error = reason.message }
  finally { item.busy = false }
}
async function selectImages(event) {
  const files = [...event.target.files]; event.target.value = ''
  if (files.length + images.value.length > 9) { error.value = '最多选择 9 张图片'; return }
  if (files.some(file => file.size > 10 * 1024 * 1024 || !['image/jpeg','image/png','image/webp'].includes(file.type))) { error.value = '请选择 10 MB 以内的 JPEG、PNG 或 WebP 图片'; return }
  error.value = ''
  for (const file of files) {
    images.value.push({ file, preview:URL.createObjectURL(file), id:'', busy:false, error:'' })
    // 使用响应式对象更新上传状态。
    await upload(images.value.at(-1))
  }
}
function removeImage(index) { const [item] = images.value.splice(index,1); if (item.preview) URL.revokeObjectURL(item.preview) }
function move(index, direction) { const item = images.value.splice(index,1)[0]; images.value.splice(index + direction,0,item) }
async function submit() {
  if (busy.value || uploading.value) return
  if (tagInput.value.trim()) { addTag(); if (tagInput.value.trim()) return }
  if (!form.body.trim()) { error.value = '写一点正文再发布吧'; return }
  if (images.value.some(i => !i.id)) { error.value = '请重试或移除上传失败的图片'; return }
  busy.value = true; error.value = ''
  try {
    const body = { ...form, images:images.value.map(i => i.id), ...(editing ? {version:version.value} : {request_key:requestKey}) }
    const post = await community(editing ? `/posts/${route.params.id}` : '/posts', {method:editing ? 'PUT' : 'POST', body:JSON.stringify(body)})
    saved.value = true; busy.value = false
    toast(editing ? '帖子已保存' : '发布成功，分享已被看见')
    await router.replace(`/my-posts/${post.id}`)
  } catch (reason) { error.value = reason.message }
  finally { busy.value = false }
}
</script>
<template><CommunityShell><div class="editor-wrap"><header class="community-heading"><div><p class="overline">SHARE YOUR MOMENTS</p><h1>{{ editing ? '编辑你的日常' : '今天，想分享什么？' }}</h1><p>关于它的每一件小事，都有同好愿意听。</p></div></header><div v-if="error" class="community-error" role="alert">{{ error }}<button v-if="editing" :disabled="busy || uploading" type="button" @click="reload">重新加载帖子</button></div><p v-if="loading" class="community-empty">正在加载…</p><form v-else-if="loaded" class="post-editor" @submit.prevent="submit"><fieldset :disabled="busy || uploading"><div class="editor-section"><div class="field-title"><h2>分享照片 <span>选填</span></h2><small>{{ images.length }} / 9 · 首图作为封面</small></div><div class="upload-grid"><div v-for="(item,index) in images" :key="item.preview || item.id" class="upload-item"><CommunityImage :src="item.preview" :private-path="!item.preview ? `/api/v1/community/media/${item.id}?thumbnail=true` : undefined" /><span v-if="index === 0" class="cover-label">封面</span><p v-if="item.busy" class="upload-status">正在上传…</p><div v-if="item.error" class="upload-error" role="alert">{{ item.error }}<button type="button" @click="upload(item)">重试</button></div><div class="upload-actions"><button type="button" :disabled="index === 0" :aria-label="`前移图片 ${index+1}`" @click="move(index,-1)">←</button><button type="button" :disabled="index === images.length-1" :aria-label="`后移图片 ${index+1}`" @click="move(index,1)">→</button><button type="button" :aria-label="`移除图片 ${index+1}`" @click="removeImage(index)">移除</button></div></div><label v-if="images.length < 9" class="upload-add"><span>＋</span>添加照片<input type="file" multiple accept="image/jpeg,image/png,image/webp" aria-label="添加照片" @change="selectImages"></label></div><p class="field-hint">支持 JPEG、PNG、WebP，每张不超过 10 MB。也可以只用文字记录。</p></div><div class="editor-section"><label for="post-title">标题 <small>选填 · {{ form.title.length }} / 50</small></label><input id="post-title" v-model="form.title" maxlength="50" placeholder="给这段日常起个名字"><label for="post-body">正文 <small>{{ form.body.length }} / 5000</small></label><textarea id="post-body" v-model="form.body" maxlength="5000" required placeholder="分享你和它的故事、养宠心得，或想和大家聊聊的问题…"></textarea></div><div class="editor-section"><label for="post-category">宠物分类</label><select id="post-category" v-model="form.category"><option v-for="(label,key) in categories" :key="key" :value="key">{{ label }}</option></select><label for="post-tag">添加标签 <small>选填 · 最多 5 个，每个 12 字</small></label><div class="tag-input"><input id="post-tag" v-model="tagInput" maxlength="12" placeholder="输入标签后按 Enter" @keydown.enter.prevent="addTag()"><button type="button" class="c-button" @click="addTag()">添加</button></div><div class="tag-list"><button v-for="(tag,index) in form.tags" :key="tag" type="button" @click="form.tags.splice(index,1)" :aria-label="`移除标签 ${tag}`"># {{ tag }} ×</button></div><div class="suggested-tags"><span>常用：</span><button v-for="tag in commonTags" :key="tag" type="button" @click="addTag(tag)"># {{ tag }}</button></div></div><div class="editor-section"><h2>关联宠物 <small>选填，最多 5 只</small></h2><p v-if="petError" role="alert" class="community-error">{{ petError }} <button type="button" @click="loadPets">重试加载宠物</button></p><div class="pet-options"><label v-for="pet in pets" :key="pet.id"><input v-model="form.pet_ids" type="checkbox" :value="pet.id" :disabled="form.pet_ids.length >= 5 && !form.pet_ids.includes(pet.id)" />{{ pet.name }}</label></div><p class="field-hint">可以关联自己的多只宠物；不关联也可以发布。<RouterLink to="/pets">管理宠物档案 ↗</RouterLink></p></div></fieldset><footer class="editor-footer"><p>发布后公开展示。请保护自己和他人的隐私。</p><button class="c-button primary" :disabled="busy || uploading">{{ busy ? '提交中…' : uploading ? '图片上传中…' : editing ? '保存修改' : '发布日常' }}</button></footer></form></div></CommunityShell></template>

<style scoped>.pet-options{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}.pet-options label{display:flex;align-items:center;gap:8px;padding:10px 14px;border:1px solid var(--line);border-radius:12px;margin:0;overflow-wrap:anywhere}.pet-options input{width:16px;height:16px;margin:0}.field-hint a{color:var(--accent)}.editor-section h2 small{font-size:12px;color:var(--muted);font-weight:400}</style>
