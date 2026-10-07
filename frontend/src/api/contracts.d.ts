export interface CursorPage<T>{items:T[];next_cursor:number|null}
export interface PublicAuthor{id:number|null;name:string;avatar_id?:string}
export interface Pet{id:number;name:string;species:string;breed:string;bio:string;hidden:number;version:number}
export interface Post{id:number;title:string;body:string;tags:string[];images:string[];status:'published'|'hidden'|'deleted';ai_generated:number;version:number;author:PublicAuthor;pets:Pet[]}
export interface Evidence{id:string;source:string;type:'knowledge'|'web';url?:string;version:string;excerpt:string}
export interface ChatMessage{role:'user'|'assistant';content:string;request_id?:string;sources?:Evidence[];context?:Pick<Pet,'id'|'name'|'species'|'breed'|'bio'|'version'>;feedback?:'helpful'|'unhelpful'|'';status?:'running'|'completed'|'failed'|'cancelled'}
export interface KnowledgeJob{id:string;source:string;status:'queued'|'building'|'completed'|'failed';error:string;version:string}
