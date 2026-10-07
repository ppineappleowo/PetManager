from app.core.errors import BusinessError
import json
from app.database.repositories.ai_turns import TurnsRepository


class TurnService:
    def __init__(self, path=None, *, repository=None, recover=True):
        self.repository = repository if repository is not None else TurnsRepository(path,recover=recover)

    def get(self, user_id, request_id):
        row = self.repository.get_turn(user_id, request_id)
        return dict(row) if row else None

    def begin(self, user_id, thread_id, request_id, prompt, image_url, context=None):
        row = self.get(user_id, request_id)
        if row:
            if context is not None and json.loads(row['context']) != context:
                raise BusinessError(409,'该请求的宠物上下文已变化，请重新发送')
            if (row['thread_id'], row['prompt'], row['image_url'] or '') != (thread_id, prompt, image_url or ''):
                raise BusinessError(409, '同一请求编号不能用于不同消息')
            if row['status'] == 'completed':
                return row
            if row['status'] == 'running':
                raise BusinessError(409, '该请求仍在生成，请先停止或稍后重试')
            newer = self.repository.find_newer_turn(user_id, thread_id, row)
            if newer:
                raise BusinessError(409, '只能重试最近一条消息；请编辑后重新发送')
            with self.repository.transaction():
                self.repository.restart_turn(row)
                self.repository.set_sources(user_id,request_id,[])
        else:
            with self.repository.transaction():
                self.repository.insert_turn(user_id, thread_id, request_id, prompt, image_url)
                self.repository.set_context(user_id,request_id,context or {})
        return self.get(user_id, request_id)

    def finish(self, user_id, request_id, status, answer, error=''):
        with self.repository.transaction():
            self.repository.finish_turn(status, answer, error, user_id, request_id)

    def messages(self, user_id, thread_id):
        rows = self.repository.list_turns(user_id, thread_id)
        result = []
        for row in rows:
            shared = {key: row[key] for key in ('request_id', 'status', 'error')}
            shared['context'] = json.loads(row['context'])
            result.append({**shared, 'role': 'user', 'content': row['prompt'], 'image_url': row['image_url']})
            result.append({**shared, 'role': 'assistant', 'content': row['answer'],'sources':json.loads(row['sources']),'feedback':row['feedback']})
        return result

    def thread_ids(self, user_id):
        return [row[0] for row in self.repository.list_thread_ids(user_id)]

    def delete(self, user_id, thread_id):
        with self.repository.transaction():
            self.repository.delete_thread(user_id, thread_id)

    def close(self):
        self.repository.close()

    def metrics(self):
        from app.database.repositories.ai_metrics import AIMetricsRepository
        with self.repository.read():return AIMetricsRepository(self.repository.db,self.repository.lock).summary()

    def sources(self,user_id,request_id,sources):
        with self.repository.transaction():
            self.repository.set_sources(user_id,request_id,sources)

    def feedback(self,user_id,request_id,value,note):
        with self.repository.transaction():
            if not self.repository.feedback(user_id,request_id,value,note):
                raise BusinessError(404,'已完成的回答不存在')
