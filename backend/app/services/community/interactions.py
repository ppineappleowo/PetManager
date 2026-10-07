import json
from app.core.errors import BusinessError

class InteractionService:

    def __init__(self, *, repository, get_post, notifications):
        self.repository = repository
        self.get = get_post
        self.notifications = notifications

    def interaction_counts(self, post_id, user_id=None):
        with self.repository.read():
            likes = self.repository.count_likes(post_id)
            comments = self.repository.count_comments(post_id)
            liked = bool(self.repository.has_like(post_id, user_id)) if user_id is not None else False
        return {'like_count': likes, 'comment_count': comments, 'liked': liked}

    def like(self, post_id, user_id, liked):
        with self.repository.transaction():
            self.get(post_id)
            if liked:
                self.repository.insert_like(post_id, user_id)
            else:
                self.repository.remove_like(post_id, user_id)
            return self.interaction_counts(post_id, user_id)

    def comment_row(self, comment_id):
        row = self.repository.get_comment(comment_id)
        if row is None:
            raise BusinessError(404, '评论不可用')
        return dict(row)

    def add_comment(self, post_id, user_id, body, reply_to, request_key):
        with self.repository.transaction():
            post = self.get(post_id)
            old = self.repository.find_comment_request(user_id, request_key)
            if old:
                if (old['post_id'], old['body'], old['reply_to']) != (post_id, body, reply_to):
                    raise BusinessError(409, '该提交已使用，请刷新评论后再发送')
                return dict(old)
            if reply_to is not None:
                target = self.comment_row(reply_to)
                if target['post_id'] != post_id or target['status'] != 'published':
                    raise BusinessError(404, '回复对象不可用，请重新选择')
            row = self.repository.insert_comment(post_id, user_id, body, reply_to, request_key)
            recipients = {post['user_id']: 'comment'}
            if reply_to is not None:
                recipients[target['user_id']] = 'reply'
            for recipient, kind in recipients.items():
                self.notifications.emit(recipient, user_id, kind, f'comment:{row.lastrowid}', post_id, row.lastrowid)
            return self.comment_row(row.lastrowid)

    def comments(self, post_id, after=0, limit=20):
        with self.repository.read():
            self.get(post_id)
            rows = self.repository.list_comments(post_id, after, limit)
            items = [dict(row) for row in rows[:limit]]
            return {'items': items, 'next_cursor': items[-1]['id'] if len(rows) > limit else None}

    def delete_comment(self, comment_id, user_id):
        with self.repository.transaction():
            row = self.comment_row(comment_id)
            if row['user_id'] != user_id:
                raise BusinessError(404, '评论不可用')
            if row['status'] != 'deleted':
                self.repository.delete_comment(comment_id)

    def moderate_comment(self, comment_id, actor_id, status, reason, version):
        with self.repository.transaction():
            row = self.comment_row(comment_id)
            if row['status'] == 'deleted' or row['version'] != version:
                raise BusinessError(409, '评论已删除或状态已变化，请刷新')
            self.repository.update_comment_status(status, reason, comment_id)
            self.repository.audit_comment(comment_id, actor_id, status, reason)
            self.repository.audit_repository().add(row['user_id'],actor_id,'comment',comment_id,reason,
                {'status':row['status'],'version':row['version']},{'status':status,'version':version+1})

    def report(self, user_id, target_type, target_id, reason):
        with self.repository.transaction():
            if target_type == 'post':
                target = self.get(target_id)
                post_id = target_id
                snapshot = {'title': target['title'], 'body': target['body'], 'images': target['images']}
            else:
                target = self.comment_row(target_id)
                post_id = target['post_id']
                self.get(post_id)
                if target['status'] != 'published':
                    raise BusinessError(404, '评论不可用')
                snapshot = {'body': target['body']}
            self.repository.insert_report(user_id, target_type, target_id, post_id, reason, snapshot)
            row = self.repository.find_report(user_id, target_type, target_id)
            return dict(row)

    def report_listing(self, status, offset, limit):
        with self.repository.read():
            total = self.repository.count_reports(status)
            rows = self.repository.list_reports(status, limit, offset)
            items = []
            for row in rows:
                data = dict(row)
                data['snapshot'] = json.loads(data['snapshot'])
                data['target'] = self.get(data['target_id'], admin=True) if data['target_type'] == 'post' else self.comment_row(data['target_id'])
                data['target'].pop('request_key', None)
                items.append(data)
            return {'items': items, 'total': total}

    def resolve_report(self, report_id, actor_id, action, note):
        with self.repository.transaction():
            row = self.repository.get_report(report_id)
            if row is None:
                raise BusinessError(404, '举报不存在')
            if row['status'] != 'open':
                if row['resolution'] == action and row['note'] == note:
                    return
                raise BusinessError(409, '举报已被处理，请刷新')
            if action == 'hide':
                self.repository.hide_report_target(row['target_type'], row['target_id'], actor_id, note)
            self.repository.resolve_report(action, note, actor_id, report_id)

    def admin_comments(self, post_id, offset, limit):
        with self.repository.read():
            return self.repository.list_admin_comments(post_id, offset, limit)
