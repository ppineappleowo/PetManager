export const focusTrap={
  mounted(el){
    const previous=document.activeElement
    el.tabIndex=-1
    const focusable=()=>[...el.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href],[tabindex="0"]')].filter(node=>node.getClientRects().length)
    queueMicrotask(()=>{if(el.isConnected)(focusable()[0]||el).focus()})
    const trap=event=>{
      if(event.key!=='Tab')return
      const elements=focusable(),first=elements[0]||el,last=elements.at(-1)||el
      if(event.shiftKey&&(document.activeElement===first||document.activeElement===el)){event.preventDefault();last.focus()}
      else if(!event.shiftKey&&(document.activeElement===last||document.activeElement===el)){event.preventDefault();first.focus()}
    }
    el.addEventListener('keydown',trap);el._releaseFocus=()=>{el.removeEventListener('keydown',trap);if(previous?.isConnected)previous.focus()}
  },
  unmounted(el){el._releaseFocus?.()},
}
