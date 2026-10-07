"""离线 SQLite → PostgreSQL 导入的兼容命令入口。"""
import argparse
import json
import socket
from app.core.config import Settings
from app.setup_local_services import local_database_url, configure_backend
from app.database.legacy.importer import inspect_sources, migrate

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect',action='store_true')
    parser.add_argument('--configure-backend',action='store_true')
    args=parser.parse_args()
    settings=Settings()
    if args.inspect:
        print(json.dumps(inspect_sources(settings.resources_dir),ensure_ascii=False,indent=2))
        return
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(('127.0.0.1',settings.server_port))==0:
            raise RuntimeError('请先停止正在运行的项目后端，再进行离线迁移')
    report=migrate(settings.resources_dir,local_database_url())
    if args.configure_backend:
        configure_backend()
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
