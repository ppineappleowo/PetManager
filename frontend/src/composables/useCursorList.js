import { ref, onScopeDispose } from 'vue'
import {readListCache,writeListCache,listEpoch} from '../utils/listCache.js'

// Each consumer owns its query state; replacement loads invalidate older responses.
export function useCursorList(fetchPage,cacheKey=null) {
  const items = ref([]), cursor = ref(null), loading = ref(false), error = ref('')
  let generation = 0
  async function load(more = false,force=false) {
    if (more && (loading.value || !cursor.value)) return
    const current = ++generation
    const key=cacheKey?.(),epoch=listEpoch()
    if(!more&&!force&&key){const cached=readListCache(key);if(cached){items.value=cached.items;cursor.value=cached.cursor;loading.value=false;error.value='';return}}
    if (!more) { items.value = []; cursor.value = null }
    loading.value = true; error.value = ''
    const isCurrent = () => current === generation
    try {
      const data = await fetchPage(more ? cursor.value : null, isCurrent)
      if (!isCurrent()) return
      items.value = [...new Map([...(more ? items.value : []), ...data.items].map(item => [item.id, item])).values()]
      cursor.value = data.next_cursor
      if(key)writeListCache(key,{items:JSON.parse(JSON.stringify(items.value)),cursor:cursor.value},epoch)
    } catch (reason) { if (isCurrent()) error.value = reason.message }
    finally { if (isCurrent()) loading.value = false }
  }
  onScopeDispose(() => { generation++ })
  return { items, cursor, loading, error, load }
}
