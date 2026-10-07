"""真实浏览器验收专用进程；仅操作随机 test_ schema 和 Redis 命名空间。"""
import os
import sys
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlencode

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from psycopg import sql
import uvicorn
from fastapi import Header,HTTPException
from app.setup_local_services import local_database_url


def main():
    shutdown_key=os.environ['BROWSER_TEST_SHUTDOWN_KEY']
    base_url=os.getenv('TEST_DATABASE_URL') or local_database_url()
    schema='test_'+uuid4().hex
    namespace='browser_'+uuid4().hex
    with psycopg.connect(base_url,autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    try:
        os.environ['DATABASE_URL']=base_url+('&' if '?' in base_url else '?')+urlencode({'options':'-csearch_path='+schema})
        os.environ['JWT_SECRET_KEY']='browser-test-only-secret-at-least-32-characters'
        os.environ['REDIS_NAMESPACE']=namespace
        os.environ['REDIS_URL']=os.getenv('TEST_REDIS_URL','redis://127.0.0.1:6379/15')
        os.environ['CORS_ORIGINS']='["http://127.0.0.1:5501"]'
        from app.database.setup import initialize_database
        from app.services.users import UserService
        initialize_database(os.environ['DATABASE_URL'])
        users=UserService(os.environ['DATABASE_URL'])
        try:users.create_user('browser_user','BrowserTest123')
        finally:users.close()
        from app.core.config import reset_settings
        reset_settings()
        from app.main import create_app
        instance=create_app()
        server=uvicorn.Server(uvicorn.Config(instance,host='127.0.0.1',port=8013,log_level='warning',access_log=False))
        @instance.post('/__test__/shutdown')
        def shutdown(authorization:str=Header('')):
            if authorization!='Bearer '+shutdown_key:raise HTTPException(403)
            server.should_exit=True
            return {'ok':True}
        server.run()
    finally:
        from redis import Redis
        redis=Redis.from_url(os.environ.get('REDIS_URL','redis://127.0.0.1:6379/15'))
        try:
            for key in redis.scan_iter(match=namespace+':*'):redis.delete(key)
        finally:redis.close()
        if not schema.startswith('test_') or len(schema)!=37:raise RuntimeError('Invalid test schema')
        with psycopg.connect(base_url,autocommit=True) as conn:
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


if __name__=='__main__':main()
