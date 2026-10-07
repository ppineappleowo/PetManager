"""History reads never initialize a model or recover running turns."""
from threading import RLock
from app.database.repositories.history import HistoryRepository
from app.services.ai.turns import TurnService


class ConversationHistory:
    def __init__(self,url):
        self.url=url
        self.lock=RLock()
        self.history=None
        self.turn_store=None

    def initialize(self):
        with self.lock:
            if self.history is None:
                history=HistoryRepository(self.url)
                try:
                    turns=TurnService(self.url,recover=False)
                except BaseException:
                    history.close();raise
                self.history,self.turn_store=history,turns

    def get_messages(self,thread_id,user_id):
        self.initialize()
        checkpoint=self.history.get({'configurable':{'thread_id':thread_id,'checkpoint_ns':f'user:{user_id}'}}) or {}
        result=[]
        for message in (checkpoint.get('channel_values') or {}).get('messages',[]):
            name=type(message).__name__
            if name in ('HumanMessage','AIMessage') and message.content:
                content=message.content
                image_url=None
                if isinstance(content,list):
                    text=[]
                    for part in content:
                        if isinstance(part,str):text.append(part)
                        elif isinstance(part,dict):
                            if part.get('type')=='text':text.append(part.get('text',''))
                            elif part.get('type')=='image':image_url=part.get('url','')
                            elif part.get('type')=='image_url':
                                image=part.get('image_url',{})
                                image_url=image.get('url','') if isinstance(image,dict) else image
                    content=' '.join(text)
                result.append({'role':'user' if name=='HumanMessage' else 'assistant','content':content,'image_url':image_url})
        return result+self.turn_store.messages(user_id,thread_id)

    def list_threads(self,user_id):
        self.initialize()
        ids=list(dict.fromkeys(self.turn_store.thread_ids(user_id)+[r[0] for r in self.history.thread_rows(f'user:{user_id}')]))
        items=[]
        for tid in ids:
            messages=self.get_messages(tid,user_id)
            first=next((m['content'] for m in messages if m['role']=='user'),'新会话')
            items.append({'thread_id':tid,'title':str(first)[:50],'message_count':len(messages)})
        return items

    def clear_messages(self,thread_id,user_id):
        self.initialize();self.history.clear(user_id,thread_id)

    def close(self):
        if self.history:
            self.history.close();self.turn_store.close()
