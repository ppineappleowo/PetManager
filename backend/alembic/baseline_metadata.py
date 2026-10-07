"""0001_postgresql 冻结结构，仅供现有库接管校验。已发布后禁止修改。
日常 schema 修改请编辑 app/infrastructure/db_metadata.py。
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
posts = sa.Table('posts',metadata,identity(),big('user_id'),text('title'),text('body'),text('category'),text('tags'),text('images'),
    text('status',"'published'"),text('reason',"''"),integer('version',1),text('created_at',ISO_TIME),text('updated_at',ISO_TIME),
    text('request_key'),text('payload_hash'),sa.UniqueConstraint('user_id','request_key',name='posts_user_id_request_key_key'))
sa.Index('posts_feed',posts.c.status,posts.c.id.desc())
sa.Index('posts_category',posts.c.status,posts.c.category,posts.c.id.desc())
sa.Index('posts_owner',posts.c.user_id,posts.c.id.desc())
media = sa.Table('media',metadata,text('id',primary_key=True),big('user_id'),integer('ready',0),text('touched_at',UTC_TIME))
moderation = sa.Table('moderation',metadata,identity(),big('post_id','posts.id'),big('actor_id'),text('action'),text('reason'),text('created_at',UTC_TIME))
comments = sa.Table('comments',metadata,identity(),big('post_id','posts.id'),big('user_id'),text('body'),big('reply_to','comments.id',nullable=True),
    text('status',"'published'"),text('reason',"''"),integer('version',1),text('request_key'),text('created_at',ISO_TIME),
    sa.UniqueConstraint('user_id','request_key',name='comments_user_id_request_key_key'))
sa.Index('comments_post',comments.c.post_id,comments.c.id)
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
