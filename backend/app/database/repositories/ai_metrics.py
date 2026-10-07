from app.database.repositories.base import Repository


class AIMetricsRepository(Repository):
    def __init__(self,db,lock):self.db,self.lock=db,lock
    def summary(self):
        rows=self.db.execute('SELECT status,feedback,COUNT(*) AS total FROM chat_turns GROUP BY status,feedback').fetchall()
        values={'completed':0,'failed':0,'cancelled':0,'running':0,'helpful':0,'unhelpful':0}
        for row in rows:
            values[row['status']]=values.get(row['status'],0)+row['total']
            if row['feedback'] in ('helpful','unhelpful'):values[row['feedback']]+=row['total']
        return values
