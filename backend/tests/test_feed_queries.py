import copy
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from app.services.users import UserService
from app.services.community.posts import CommunityService
from app.services.community.presentation import CommunityPresenter


class FeedQueriesTests(unittest.TestCase):
    def test_batch_matches_single_and_query_count_is_constant(self):
        with tempfile.TemporaryDirectory() as directory:
            users = UserService(str(Path(directory) / 'users.db'))
            posts = CommunityService(Path(directory) / 'community.db')
            try:
                user = users.create_user('13700000000', 'secret123')
                pet = posts.write_pet(user['id'], dict(name='小猫', species='cat', breed='', sex='unknown', birthday=None, bio='', photo_id=None), request_key=str(uuid4()))
                for i in range(24):
                    post = posts.write(user['id'], dict(title='', body=str(i), category='cat', tags=[], images=[], pet_ids=[pet['id']]), request_key=str(uuid4()))
                    posts.like(post['id'], user['id'], True)
                    posts.add_comment(post['id'], user['id'], '你好', None, str(uuid4()))
                presenter = CommunityPresenter(users, posts)
                for size in (1, 24):
                    data = posts.listing(limit=size)
                    expected = [presenter.present(copy.deepcopy(row)) for row in data['items']]
                    statements = []
                    users.repository.db.set_trace_callback(statements.append)
                    posts.repository.db.set_trace_callback(statements.append)
                    data = posts.listing(limit=size)
                    original = copy.deepcopy(data)
                    result = presenter.present_list(data)
                    users.repository.db.set_trace_callback(None)
                    posts.repository.db.set_trace_callback(None)
                    self.assertEqual(result['items'], expected)
                    self.assertEqual(data, original)
                    self.assertEqual(len([sql for sql in statements if sql.lstrip().upper().startswith('SELECT')]), 6)
                    self.assertNotIn('phone', result['items'][0]['author'])
                self.assertEqual(presenter.present_list({'items': [], 'next_cursor': None})['items'], [])
            finally:
                posts.close()
                users.close()
