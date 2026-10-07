const pages=new Map()
let epoch=0
export const listEpoch=()=>epoch
export function clearListCache(){epoch++;pages.clear()}
export function readListCache(key){const page=pages.get(key);if(!page||Date.now()-page.at>60000){pages.delete(key);return null}return structuredClone(page.value)}
export function writeListCache(key,value,expectedEpoch){if(expectedEpoch!==epoch)return;pages.delete(key);pages.set(key,{at:Date.now(),value:structuredClone(value)});while(pages.size>10)pages.delete(pages.keys().next().value)}
