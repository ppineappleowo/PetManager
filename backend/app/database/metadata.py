"""关系库目标结构，用于 Alembic autogenerate；业务仓储仍使用 psycopg。

新增/修改字段时更新本文件，再生成并审查迁移。不要通过运行时反射构造 metadata。
"""
import sqlalchemy as sa

metadata = sa.MetaData()
UTC_TIME = "to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS')"
ISO_TIME = '''to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')'''


def text(name, default=None, nullable=False, primary_key=False):
    return sa.Column(name, sa.Text(), nullable=nullable, primary_key=primary_key,
                     server_default=sa.text(default) if default is not None else None)


def integer(name, default=None):
    return sa.Column(name, sa.Integer(), nullable=False, server_default=sa.text(str(default)) if default is not None else None)


def identity(name='id'):
    return sa.Column(name, sa.BigInteger(), primary_key=True, autoincrement=True)


def big(name, reference=None, nullable=False, primary_key=False):
    return sa.Column(name, sa.BigInteger(), *([sa.ForeignKey(reference)] if reference else []),
                     nullable=nullable, primary_key=primary_key, autoincrement=False)


app_migrations = sa.Table('app_migrations', metadata,
    sa.Column('version', sa.Integer(), primary_key=True, autoincrement=False),
    sa.Column('applied_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')))
community_migrations = sa.Table('community_migrations', metadata,
    sa.Column('version', sa.Integer(), primary_key=True, autoincrement=False))
users = sa.Table('users', metadata, identity(), text('username'), text('password_hash'),
    text('created_at', UTC_TIME), text('role', "'user'"), integer('token_version',0), integer('disabled',0),
    text('phone',nullable=True), text('nickname',"''"), text('bio',"''"), text('avatar_id',"''"),
    sa.UniqueConstraint('username',name='users_username_key'))
sa.Index('users_phone',users.c.phone,unique=True,postgresql_where=users.c.phone.is_not(None))
for name in ('profile_hidden','avatar_hidden','profile_version'):
    users.append_column(integer(name, 1 if name == 'profile_version' else 0))
user_follows = sa.Table('user_follows', metadata,
    big('follower_id', 'users.id', primary_key=True), big('followed_id', 'users.id', primary_key=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    sa.CheckConstraint('follower_id <> followed_id', name='user_follows_no_self'))
sa.Index('user_follows_followed', user_follows.c.followed_id, user_follows.c.follower_id)
posts = sa.Table('posts',metadata,identity(),big('user_id'),text('title'),text('body'),text('category'),text('tags'),text('images'),
    text('status',"'published'"),text('reason',"''"),integer('version',1),text('created_at',ISO_TIME),text('updated_at',ISO_TIME),
    text('request_key'),text('payload_hash'),sa.UniqueConstraint('user_id','request_key',name='posts_user_id_request_key_key'))
sa.Index('posts_feed',posts.c.status,posts.c.id.desc())
sa.Index('posts_category',posts.c.status,posts.c.category,posts.c.id.desc())
sa.Index('posts_owner',posts.c.user_id,posts.c.id.desc())
posts.append_column(integer('ai_generated',0))
post_tags = sa.Table('post_tags', metadata, big('post_id', 'posts.id', primary_key=True), text('tag', primary_key=True))
sa.Index('post_tags_tag', post_tags.c.tag, post_tags.c.post_id)
post_bookmarks = sa.Table('post_bookmarks', metadata, identity(), big('user_id', 'users.id'), big('post_id', 'posts.id'),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    sa.UniqueConstraint('user_id', 'post_id', name='post_bookmarks_user_post_key'))
sa.Index('post_bookmarks_owner', post_bookmarks.c.user_id, post_bookmarks.c.id)
media = sa.Table('media',metadata,text('id',primary_key=True),big('user_id'),integer('ready',0),text('touched_at',UTC_TIME))
moderation = sa.Table('moderation',metadata,identity(),big('post_id','posts.id'),big('actor_id'),text('action'),text('reason'),text('created_at',UTC_TIME))
comments = sa.Table('comments',metadata,identity(),big('post_id','posts.id'),big('user_id'),text('body'),big('reply_to','comments.id',nullable=True),
    text('status',"'published'"),text('reason',"''"),integer('version',1),text('request_key'),text('created_at',ISO_TIME),
    sa.UniqueConstraint('user_id','request_key',name='comments_user_id_request_key_key'))
sa.Index('comments_post',comments.c.post_id,comments.c.id)
notifications = sa.Table('notifications', metadata, identity(), big('recipient_id', 'users.id'), big('actor_id', 'users.id'),
    text('kind'), text('event_key'), big('post_id', 'posts.id', nullable=True), big('comment_id', 'comments.id', nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.UniqueConstraint('recipient_id', 'event_key', name='notifications_recipient_event_key'),
    sa.CheckConstraint("kind IN ('comment','reply','follow')", name='notifications_kind'))
sa.Index('notifications_recipient', notifications.c.recipient_id, notifications.c.id)
sa.Index('notifications_unread', notifications.c.recipient_id, notifications.c.id, postgresql_where=notifications.c.read_at.is_(None))
post_likes = sa.Table('post_likes',metadata,big('post_id','posts.id',primary_key=True),big('user_id',primary_key=True))
comment_moderation = sa.Table('comment_moderation',metadata,identity(),big('comment_id','comments.id'),big('actor_id'),text('action'),text('reason'),text('created_at',UTC_TIME))
reports = sa.Table('reports',metadata,identity(),big('user_id'),text('target_type'),big('target_id'),big('post_id','posts.id'),text('reason'),text('snapshot'),
    text('status',"'open'"),text('resolution',nullable=True),text('note',nullable=True),big('actor_id',nullable=True),text('resolved_at',nullable=True),text('created_at',UTC_TIME),
    sa.UniqueConstraint('user_id','target_type','target_id',name='reports_user_id_target_type_target_id_key'))
sa.Index('reports_status',reports.c.status,reports.c.id.desc())
pets = sa.Table('pets',metadata,identity(),big('user_id'),text('name'),text('species'),text('breed',"''"),text('sex',"'unknown'"),text('birthday',nullable=True),text('bio',"''"),
    text('photo_id',nullable=True),integer('version',1),integer('deleted',0),text('request_key'),text('payload_hash'),text('created_at',ISO_TIME),
    sa.UniqueConstraint('user_id','request_key',name='pets_user_id_request_key_key'))
sa.Index('pets_owner',pets.c.user_id,pets.c.deleted,pets.c.id)
pets.append_column(integer('hidden',0))
post_pets = sa.Table('post_pets',metadata,big('post_id','posts.id',primary_key=True),big('pet_id','pets.id',primary_key=True))
sa.Index('pet_posts',post_pets.c.pet_id,post_pets.c.post_id)
chat_turns = sa.Table('chat_turns',metadata,identity('seq'),text('user_id'),text('thread_id'),text('request_id'),text('prompt'),text('image_url',nullable=True),
    text('answer',"''"),text('status'),text('error',"''"),sa.UniqueConstraint('user_id','request_id',name='chat_turns_user_id_request_id_key'))
sa.Index('chat_turns_thread',chat_turns.c.user_id,chat_turns.c.thread_id,chat_turns.c.seq)
checkpoints = sa.Table('checkpoints',metadata,text('thread_id',primary_key=True),text('checkpoint_ns',"''",primary_key=True),text('checkpoint_id',primary_key=True),
    text('parent_checkpoint_id',nullable=True),text('type',nullable=True),sa.Column('checkpoint',sa.LargeBinary()),sa.Column('metadata',sa.LargeBinary()))
writes = sa.Table('writes',metadata,text('thread_id',primary_key=True),text('checkpoint_ns',"''",primary_key=True),text('checkpoint_id',primary_key=True),text('task_id',primary_key=True),
    sa.Column('idx',sa.Integer(),primary_key=True,autoincrement=False),text('channel',nullable=True),text('type',nullable=True),sa.Column('value',sa.LargeBinary()))
data_imports = sa.Table('data_imports',metadata,text('name',primary_key=True),text('source_fingerprint'),text('report'),
    sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')))

for table_name in ('user_audit','community_audit'):
    audit = sa.Table(table_name,metadata,identity(),big('owner_id'),big('actor_id'),text('kind'),big('target_id'),
        text('reason'),text('before_state'),text('after_state'),text('created_at',ISO_TIME))
    sa.Index(table_name+'_owner',audit.c.owner_id,audit.c.id)
chat_turns.append_column(text('sources',"'[]'"))
chat_turns.append_column(text('context',"'{}'"))
chat_turns.append_column(text('feedback',"''"))
chat_turns.append_column(text('feedback_note',"''"))
knowledge_jobs = sa.Table('knowledge_jobs',metadata,text('id',primary_key=True),big('actor_id'),text('source'),text('payload'),
    text('status',"'queued'"),text('error',"''"),text('version',"''"),text('created_at',ISO_TIME),text('updated_at',ISO_TIME))
