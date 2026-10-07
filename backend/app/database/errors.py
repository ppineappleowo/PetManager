"""仓储层向调用者公开的约束错误，集中封装旧数据库适配行为。"""
from sqlite3 import IntegrityError as IntegrityConflict
