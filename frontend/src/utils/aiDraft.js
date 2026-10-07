let draft=null

export function clearAiDraft(){draft=null}
export function createAiDraft(token,body){
  const id=crypto.randomUUID()
  draft={id,token,body}
  return id
}
export function takeAiDraft(token,id){
  const current=draft
  draft=null
  return current && current.id===id && current.token===token ? current.body : ''
}
