"""读取已迁移的旧 LangGraph 快照；新对话由 chat_turns 管理。"""
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


class LegacyHistory:
    def __init__(self, database):
        self.database = database
        self.serde = JsonPlusSerializer()

    def get(self, config):
        values = config['configurable']
        row = self.database.execute('SELECT type,checkpoint FROM checkpoints WHERE thread_id=? AND checkpoint_ns=? ORDER BY checkpoint_id DESC LIMIT 1',
            (values['thread_id'],values.get('checkpoint_ns',''))).fetchone()
        if row is None:
            return None
        return self.serde.loads_typed((row['type'],bytes(row['checkpoint'])))
