import hashlib
import json
from uuid import uuid4
from app.core.errors import BusinessError
from app.database.repositories.community_posts import PostsRepository
from app.services.community.interactions import InteractionService
from app.services.community.pets import PetService
from app.services.community.follows import FollowService
from app.services.community.bookmarks import BookmarkService
from app.services.community.notifications import NotificationService
from app.services.community.report_feedback import ReportFeedbackService


class CommunityService:
    def __init__(self, path=None, *, repository=None):
        self.repository = repository if repository is not None else PostsRepository(path)
        interactions, pets, follows = self.repository.related()
        self.notifications = NotificationService(self.repository.notifications_repository())
        self.report_feedback = ReportFeedbackService(self.repository.report_feedback_repository())
        self.interactions = InteractionService(repository=interactions, get_post=self.get, notifications=self.notifications)
        self.pet_service = PetService(repository=pets, validate_media=self.validate_media)
        self.follows = FollowService(repository=follows, notifications=self.notifications)
        self.bookmarks = BookmarkService(self.repository.bookmarks_repository(), self.get, self.decode)

    @staticmethod
    def decode(row):
        if row is None:
            raise BusinessError(404, '帖子不可用')
        data = dict(row)
        for key in ('tags', 'images'):
            data[key] = json.loads(data[key])
        data.pop('request_key', None)
        data.pop('payload_hash', None)
        return data

    def get(self, post_id, owner=None, admin=False):
        with self.repository.read():
            data = self.decode(self.repository.get_post(post_id))
            if not admin and (data['status'] == 'deleted' or (owner is None and data['status'] != 'published') or (owner is not None and data['user_id'] != owner)):
                raise BusinessError(404, '帖子不可用')
            return data

    def listing(self, *args, **kwargs):
        data = self.repository.list_posts(*args, **kwargs)
        data['items'] = [self.decode(row) for row in data['items']]
        return data

    def presentation_data(self, post_ids):
        return self.repository.presentation_data(post_ids)

    def discover(self, *, q='', tag='', category=None, before=None, limit=24, sort='latest'):
        return self.listing(search=q.strip(), tag=tag.strip(), category=category, before=before, limit=limit, sort=sort)

    def topics(self, category=None, q='', limit=20):
        return {'items': self.repository.topics(category, q.strip(), limit)}

    def validate_media(self, user_id, images):
        for image in images:
            row = self.repository.get_owned_ready_media(image, user_id)
            if not row:
                raise BusinessError(422, '图片不可用或不属于当前用户，请重新上传')

    def write(self, user_id, data, request_key=None, post_id=None, version=None):
        data = dict(data)
        if not data.get('ai_generated'):
            data.pop('ai_generated',None)
        pet_ids = data.get('pet_ids', [])
        if not pet_ids:
            data.pop('pet_ids', None)
        digest = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with self.repository.transaction():

            if post_id is None:
                old = self.repository.find_post_request(user_id, request_key)
                if old:
                    if old['payload_hash'] != digest:
                        raise BusinessError(409, '这次发布已提交，请刷新后再发布新内容')
                    return self.decode(old)
            else:
                old = self.get(post_id, owner=user_id)
                if old['version'] != version:
                    raise BusinessError(409, '帖子已被修改，请重新加载后编辑')
            self.validate_media(user_id, data['images'])
            for pet_id in pet_ids:
                self.pet(pet_id, owner=user_id)
            values = (data['title'], data['body'], data['category'], json.dumps(data['tags'], ensure_ascii=False), json.dumps(data['images']))
            if post_id is None:
                post_id = self.repository.insert_post(user_id, request_key, digest, values)
            else:
                self.repository.update_post(post_id, values)
            self.repository.remove_post_pet_links(post_id)
            if data.get('ai_generated'):
                self.repository.mark_ai_generated(post_id)
            self.repository.replace_tags(post_id, data['tags'])
            self.repository.insert_post_pet_links(post_id, pet_ids)
            self.repository.touch_media(user_id)
            return self.get(post_id, owner=user_id)

    def delete(self, post_id, user_id):
        with self.repository.transaction():

            self.get(post_id, owner=user_id)
            self.repository.delete_post(post_id)
            self.repository.touch_deleted_post_media(user_id)

    def moderate(self, post_id, actor, status, reason, version):
        with self.repository.transaction():

            post = self.get(post_id, admin=True)
            if post['status'] == 'deleted':
                raise BusinessError(409, '作者已删除，不能恢复或下架')
            if post['version'] != version:
                raise BusinessError(409, '帖子状态已变化，请刷新后操作')
            self.repository.update_post_status(status, reason, post_id)
            self.repository.audit_post(post_id, actor, status, reason)
            self.repository.audit_repository().add(post['user_id'],actor,'post',post_id,reason,
                {'status':post['status'],'version':post['version']},{'status':status,'version':version+1})
            return self.get(post_id, admin=True)

    def new_media(self, user_id):
        media_id = uuid4().hex
        with self.repository.transaction():
            self.repository.insert_media(media_id, user_id)
        return media_id

    def ready_media(self, media_id):
        with self.repository.transaction():
            self.repository.mark_media_ready(media_id)

    def own_media(self, media_id, user_id):
        with self.repository.read():
            if not self.repository.has_owned_media(media_id, user_id):
                raise BusinessError(404, '图片不可用')

    def clean_media(self, storage):
        with self.repository.transaction():

            used = {image for row in self.repository.post_media_references() for image in json.loads(row[0])}
            used.update((row[0] for row in self.repository.pet_media_references()))
            count = 0
            for row in self.repository.expired_media():
                if row['id'] not in used:
                    storage.delete(row['id'])
                    self.repository.remove_media(row)
                    count += 1
            return count

    def close(self):
        self.repository.close()

    def interaction_counts(self, post_id, user_id=None):
        return self.interactions.interaction_counts(post_id, user_id)

    def like(self, post_id, user_id, liked):
        return self.interactions.like(post_id, user_id, liked)

    def comment_row(self, comment_id):
        return self.interactions.comment_row(comment_id)

    def add_comment(self, post_id, user_id, body, reply_to, request_key):
        return self.interactions.add_comment(post_id, user_id, body, reply_to, request_key)

    def comments(self, post_id, after=0, limit=20):
        return self.interactions.comments(post_id, after, limit)

    def delete_comment(self, comment_id, user_id):
        return self.interactions.delete_comment(comment_id, user_id)

    def moderate_comment(self, comment_id, actor_id, status, reason, version):
        return self.interactions.moderate_comment(comment_id, actor_id, status, reason, version)

    def report(self, user_id, target_type, target_id, reason):
        return self.interactions.report(user_id, target_type, target_id, reason)

    def moderate_pet(self, pet_id, actor, hidden, reason, version):
        repo = self.pet_service.repository
        with repo.transaction():
            row = repo.get_pet(pet_id)
            if not row or row['version'] != version:
                raise BusinessError(409,'宠物已删除或档案变化，请刷新')
            repo.moderate(pet_id,hidden)
            self.repository.audit_repository().add(row['user_id'],actor,'pet',pet_id,reason,
                {'hidden':row['hidden'],'version':version},{'hidden':int(hidden),'version':version+1})

    def audit(self, owner=None, before=None, limit=20):
        with self.repository.read():
            return self.repository.audit_repository().listing(owner,before,limit)

    def admin_pets(self, before=None, limit=20):
        with self.repository.read():
            rows = self.pet_service.repository.admin_list(before,limit)
            items = [{key:row[key] for key in ('id','user_id','name','species','bio','photo_id','hidden','version')} for row in rows[:limit]]
            return {'items':items,'next_cursor':items[-1]['id'] if len(rows)>limit else None}

    def admin_pet(self, pet_id):
        with self.repository.read():
            row = self.pet_service.repository.get_pet(pet_id)
            if not row:
                raise BusinessError(404,'宠物档案不可用')
            return dict(row)

    def metrics(self):
        return self.repository.metrics()

    def search_pets(self,q,before=None,limit=20):
        with self.repository.read():rows=self.pet_service.repository.public_search(q,before,limit)
        keys=('id','name','species','breed')
        items=[{k:row[k] for k in keys} for row in rows[:limit]]
        return {'items':items,'next_cursor':items[-1]['id'] if len(rows)>limit else None}

    def report_listing(self, status, offset, limit):
        return self.interactions.report_listing(status, offset, limit)

    def resolve_report(self, report_id, actor_id, action, note):
        return self.interactions.resolve_report(report_id, actor_id, action, note)

    def pet(self, pet_id, owner=None):
        return self.pet_service.pet(pet_id, owner)

    def pets(self, user_id):
        return self.pet_service.pets(user_id)

    def write_pet(self, user_id, data, request_key=None, pet_id=None, version=None):
        return self.pet_service.write_pet(user_id, data, request_key, pet_id, version)

    def delete_pet(self, pet_id, user_id, version):
        return self.pet_service.delete_pet(pet_id, user_id, version)

    def post_pet_list(self, post_id):
        return self.pet_service.post_pet_list(post_id)

    def follow_counts(self, user_id):
        return self.follows.follow_counts(user_id)

    def follow_state(self, actor, target):
        return self.follows.follow_state(actor, target)

    def set_follow(self, actor, target, enabled):
        return self.follows.set_follow(actor, target, enabled)

    def moderation_history(self, post_id):
        return self.repository.moderation_history(post_id)

    def admin_comments(self, post_id, offset, limit):
        return self.interactions.admin_comments(post_id, offset, limit)

    def connections(self, actor, kind, before=None, limit=24):
        return self.follows.connections(actor, kind, before, limit)
