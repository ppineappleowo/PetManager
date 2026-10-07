import {onBeforeUnmount} from 'vue'
import {onBeforeRouteLeave} from 'vue-router'

export function useUnsavedChanges(dirty,busy=()=>false) {
  let accepted=false
  function confirmLeave(){
    if(busy())return false
    if(!accepted && dirty() && !window.confirm('还有未保存的修改，确定离开吗？'))return false
    accepted=true
    return true
  }
  onBeforeRouteLeave(()=>!busy() && (accepted || !dirty() || window.confirm('还有未保存的修改，确定离开吗？')))
  function beforeUnload(event){if(dirty()||busy()){event.preventDefault();event.returnValue=''}}
  window.addEventListener('beforeunload',beforeUnload)
  onBeforeUnmount(()=>window.removeEventListener('beforeunload',beforeUnload))
  return confirmLeave
}
