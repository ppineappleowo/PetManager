"""生成本地 Compose 密钥；不输出密钥，不覆盖已有密码。"""
import argparse
from pathlib import Path
import secrets
from urllib.parse import quote
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[2]


def local_database_url():
    password = dotenv_values(ROOT/'.env').get('POSTGRES_PASSWORD')
    if not password:
        raise RuntimeError('请先执行 python -m app.setup_local_services')
    return f"postgresql://baichongji:{quote(password,safe='')}@127.0.0.1:5432/baichongji"


def configure_backend():
    path=ROOT/'backend'/'.env'
    set_key(path,'DATABASE_URL',local_database_url())
    set_key(path,'REDIS_URL','redis://127.0.0.1:6379/0')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--configure-backend',action='store_true')
    args=parser.parse_args()
    path=ROOT/'.env'
    if not dotenv_values(path).get('POSTGRES_PASSWORD'):
        set_key(path,'POSTGRES_PASSWORD',secrets.token_urlsafe(36))
    if args.configure_backend:
        configure_backend()
    print('本地服务配置已准备完成（密钥未输出）')


if __name__=='__main__':
    main()
