"""服务器端设置权限：python -m app.manage_user USERNAME --role admin"""
import argparse
from app.services.users import UserService
from app.core.config import get_settings
from app.database.setup import initialize_database


def main():
    parser = argparse.ArgumentParser(description="设置现有用户角色")
    parser.add_argument('username')
    parser.add_argument('--role', choices=['admin', 'user'], required=True)
    args = parser.parse_args()
    url = get_settings().database_url.get_secret_value()
    initialize_database(url)
    manager = UserService(url)
    try:
        if not manager.set_role(args.username, args.role):
            parser.error('用户不存在，请先注册')
        print(f'{args.username} 的角色已设为 {args.role}')
    finally:
        manager.close()


if __name__ == '__main__':
    main()
