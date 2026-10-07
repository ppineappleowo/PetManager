import secrets
from app.core.errors import BusinessError
from app.database.errors import IntegrityConflict
from app.database.repositories.users import UsersRepository
from app.core.passwords import _hash_password, _verify_password


class UserService:
    # Credentials are hashed and checked outside SQL repositories.

    def __init__(self, db_path=None, *, repository=None):
        self.repository = repository if repository is not None else UsersRepository(db_path)

    @staticmethod
    def _public(row):
        return {key: row[key] for key in ('id', 'username', 'created_at', 'role', 'token_version', 'disabled', 'phone', 'nickname', 'bio', 'avatar_id','profile_hidden','avatar_hidden','profile_version')} if row else None

    def moderate(self, user_id, actor, field, hidden, reason, version):
        with self.repository.transaction():
            before = self.get_by_id(user_id)
            if before is None:
                raise BusinessError(404,'用户不存在')
            if before['profile_version'] != version:
                raise BusinessError(409,'资料已变化，请刷新')
            key = field + '_hidden'
            self.repository.moderate_profile(user_id,key,hidden)
            after = self.get_by_id(user_id)
            keys = ('nickname','bio','profile_hidden') if field == 'profile' else ('avatar_id','avatar_hidden')
            self.repository.audit_repository().add(user_id,actor,field,user_id,reason,
                {k:before[k] for k in keys},{k:after[k] for k in keys})

    def audit(self, owner=None, before=None, limit=20):
        with self.repository.read():
            return self.repository.audit_repository().listing(owner,before,limit)

    def search(self, q='', offset=0, limit=20):
        with self.repository.read():
            return self.repository.search_accounts(q,offset,limit)

    def public_search(self,q,before=None,limit=20):
        from app.services.community.presentation import public_author
        with self.repository.read():rows=self.repository.public_search(q,before,limit)
        items=[public_author(dict(row)) for row in rows[:limit]]
        return {'items':items,'next_cursor':items[-1]['id'] if len(rows)>limit else None}

    def set_avatar(self, user_id, avatar_id):
        with self.repository.transaction():

            old = self.repository.avatar_id(user_id)
            self.repository.update_avatar(avatar_id, user_id)
        return old

    def create_user(self, username: str, password: str):
        password_hash = _hash_password(password)
        with self.repository.read():
            try:
                with self.repository.transaction():
                    cursor = self.repository.insert_account(password_hash, username)
                return self.get_by_id(cursor.lastrowid)
            except IntegrityConflict:
                return None

    def authenticate(self, username: str, password: str):
        with self.repository.read():
            row = self.repository.find_credentials(username)
        stored = row['password_hash'] if row else '0' * 32 + ':' + '0' * 64
        valid = _verify_password(password, stored)
        return self._public(row) if valid and row and (not row['disabled']) else None

    def register_phone(self, phone, password):

        password_hash = _hash_password(password)
        with self.repository.transaction():

            if self.repository.phone_exists(phone):
                raise BusinessError(409, '手机号已被使用，请直接登录')
            username = '用户_' + secrets.token_hex(8)
            cursor = self.repository.insert_phone_account(username, phone, password_hash)
            user_id = cursor.lastrowid
        return self.get_by_id(user_id)

    def login_scope(self, identifier):
        with self.repository.read():
            row = self.repository.find_login_id(identifier)
            return str(row['id']) if row else identifier

    def update_profile(self, user_id, username, nickname, bio):

        with self.repository.transaction():
            conflict = self.repository.find_name_conflict(user_id, username)
            if conflict:
                raise BusinessError(409, '用户名已被使用')
            try:
                self.repository.update_profile(username, nickname, bio, user_id)
            except IntegrityConflict:
                raise BusinessError(409, '用户名已被使用')
        return self.get_by_id(user_id)

    def list_users(self):
        with self.repository.read():
            return [dict(row) for row in self.repository.list_accounts()]

    def admin_update(self, user_id, actor_id, role=None, disabled=None, revoke=False):

        with self.repository.transaction():

            row = self.repository.get_account_for_update(user_id)
            if not row:
                raise BusinessError(404, '用户不存在')
            new_role = role if role is not None else row['role']
            new_disabled = int(disabled) if disabled is not None else row['disabled']
            if user_id == actor_id and (new_role != 'admin' or new_disabled):
                raise BusinessError(409, '不能降级或禁用当前管理员')
            if row['role'] == 'admin' and (not row['disabled']) and (new_role != 'admin' or new_disabled):
                count = self.repository.count_active_admins()
                if count <= 1:
                    raise BusinessError(409, '至少保留一个可用管理员')
            self.repository.update_access(new_role, new_disabled, user_id, revoke, row)
            self.repository.audit_repository().add(user_id,actor_id,'access',user_id,'账号权限调整',
                {'role':row['role'],'disabled':row['disabled']}, {'role':new_role,'disabled':new_disabled,'revoked':bool(revoke)})

    def get_by_id(self, user_id: int):
        with self.repository.read():
            return self._public(self.repository.get_account(user_id))

    def get_by_ids(self, user_ids):
        with self.repository.read():
            return {row['id']: self._public(row) for row in self.repository.get_accounts(user_ids)}

    def change_password(self, user_id: int, old_password: str, new_password: str, token_version: int):
        with self.repository.read():
            row = self.repository.get_credentials(user_id)
            if not row or row['token_version'] != token_version or (not _verify_password(old_password, row['password_hash'])):
                return False
            new_hash = _hash_password(new_password)
            with self.repository.transaction():
                updated = self.repository.update_password(new_hash, user_id, token_version)
            return updated.rowcount == 1

    def set_role(self, username: str, role: str):
        if role not in ('admin', 'user'):
            raise ValueError('Invalid role')
        with self.repository.transaction():
            return self.repository.update_role(role, username) == 1

    def close(self):
        self.repository.close()

    def health(self):
        self.repository.ping()
