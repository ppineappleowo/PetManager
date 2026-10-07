from app.core.errors import BusinessError

def public_author(user):
    user=dict(user)
    username = user['username']
    fallback = f"宠友_{user['id']}" if (len(username)==11 and username.isdecimal()) or username==user['phone'] else username
    return {'id':user['id'], 'name':f"宠友_{user['id']}" if user.get('profile_hidden') else user['nickname'] or fallback, 'avatar_id':'' if user.get('avatar_hidden') else user['avatar_id']}

class CommunityPresenter:
    def __init__(self, users, community):
        self.users = users
        self.community = community

    def present(self, post):
        user = self.users.get_by_id(post.pop('user_id'))
        if user:
            post['author'] = public_author(user)
        else:
            post['author'] = {'id': None, 'name': '已注销用户'}
        if 'category' in post:
            counts = self.community.interaction_counts(post['id'])
            post.update({key: counts[key] for key in ('like_count', 'comment_count')})
            post['pets'] = [self.present_pet(pet) for pet in self.community.post_pet_list(post['id'])]
            post['pet_ids'] = [pet['id'] for pet in post['pets']]
        return post

    def present_list(self, data):
        posts = data['items']
        users = self.users.get_by_ids(post['user_id'] for post in posts)
        counts, pets = self.community.presentation_data(post['id'] for post in posts if 'category' in post)
        items = []
        for original in posts:
            post = dict(original)
            user = users.get(post.pop('user_id'))
            post['author'] = public_author(user) if user else {'id': None, 'name': '已注销用户'}
            if 'category' in post:
                post.update(counts[post['id']])
                post['pets'] = [self.present_pet(pet) for pet in pets[post['id']]]
                post['pet_ids'] = [pet['id'] for pet in post['pets']]
            items.append(post)
        return {**data, 'items': items}

    def public_user(self, user_id):
        user = self.users.get_by_id(user_id)
        if not user or user['disabled']:
            raise BusinessError(404, '用户主页不可用')
        return user

    def present_pet(self, pet):
        return {key: pet[key] for key in ('id', 'name', 'species', 'breed', 'sex', 'birthday', 'bio', 'photo_id', 'version','hidden') if key in pet}

    def present_comment(self, row):
        visible = row['status'] == 'published'
        data = {key: row[key] for key in ('id', 'post_id', 'reply_to', 'created_at', 'status')}
        data['body'] = row['body'] if visible else ''
        data['author'] = self.present({'user_id': row['user_id']})['author'] if visible else None
        data['reply_author'] = None
        if visible and row['reply_to']:
            parent = self.community.comment_row(row['reply_to'])
            data['reply_author'] = self.present({'user_id': parent['user_id']})['author'] if parent['status'] == 'published' else {'id': None, 'name': '已不可用的评论'}
        return data
