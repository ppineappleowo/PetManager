import hashlib
import json
from app.core.errors import BusinessError

class PetService:

    def __init__(self, *, repository, validate_media):
        self.repository = repository
        self.validate_media = validate_media

    def pet(self, pet_id, owner=None):
        with self.repository.read():
            row = self.repository.get_pet(pet_id)
            if not row or (owner is not None and row['user_id'] != owner) or (owner is None and row['hidden']):
                raise BusinessError(404, '宠物档案不可用')
            return {key: row[key] for key in ('id', 'user_id', 'name', 'species', 'breed', 'sex', 'birthday', 'bio', 'photo_id', 'version', 'created_at','hidden')}

    def pets(self, user_id):
        with self.repository.read():
            return [self.pet(row[0],owner=user_id) for row in self.repository.list_pets(user_id)]

    def write_pet(self, user_id, data, request_key=None, pet_id=None, version=None):
        digest = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with self.repository.transaction():
            if pet_id is None:
                old = self.repository.find_pet_request(user_id, request_key)
                if old:
                    if old['payload_hash'] != digest or old['deleted']:
                        raise BusinessError(409, '这次添加已提交，请刷新后操作')
                    return self.pet(old['id'],owner=user_id)
                if self.repository.count_pets(user_id) >= 50:
                    raise BusinessError(422, '每个账号最多保留 50 份宠物档案')
            elif self.pet(pet_id, owner=user_id)['version'] != version:
                raise BusinessError(409, '宠物档案已更新，请重新加载')
            if data['photo_id']:
                self.validate_media(user_id, [data['photo_id']])
            values = tuple((data[key] for key in ('name', 'species', 'breed', 'sex', 'birthday', 'bio', 'photo_id')))
            if pet_id is None:
                pet_id = self.repository.insert_pet(user_id, request_key, digest, values)
            else:
                self.repository.update_pet(pet_id, values)
            self.repository.touch_pet_media(user_id)
            return self.pet(pet_id,owner=user_id)

    def delete_pet(self, pet_id, user_id, version):
        with self.repository.transaction():
            if self.pet(pet_id, owner=user_id)['version'] != version:
                raise BusinessError(409, '宠物档案已更新，请重新加载')
            self.repository.delete_pet(pet_id)
            self.repository.bump_linked_post_versions(pet_id)
            self.repository.remove_pet_links(pet_id)
            self.repository.touch_deleted_pet_media(user_id)

    def post_pet_list(self, post_id):
        with self.repository.read():
            return [self.pet(row[0]) for row in self.repository.list_post_pets(post_id)]
