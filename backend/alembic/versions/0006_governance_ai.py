"""Profile/pet governance, immutable audits, AI evidence and durable imports."""
from alembic import op
import sqlalchemy as sa

revision = '0006_governance_ai'
down_revision = '0005_post_tags'
branch_labels = depends_on = None
ISO = '''to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')'''


def upgrade():
    op.add_column('posts',sa.Column('ai_generated',sa.Integer(),nullable=False,server_default='0'))
    for name, default in [('profile_hidden','0'),('avatar_hidden','0'),('profile_version','1')]:
        op.add_column('users',sa.Column(name,sa.Integer(),nullable=False,server_default=default))
    op.add_column('pets',sa.Column('hidden',sa.Integer(),nullable=False,server_default='0'))
    for table in ('user_audit','community_audit'):
        op.create_table(table,sa.Column('id',sa.BigInteger(),primary_key=True),
            *[sa.Column(name,sa.BigInteger(),nullable=False) for name in ('owner_id','actor_id','target_id')],
            *[sa.Column(name,sa.Text(),nullable=False) for name in ('kind','reason','before_state','after_state')],
            sa.Column('created_at',sa.Text(),nullable=False,server_default=sa.text(ISO)))
        op.create_index(table+'_owner',table,['owner_id','id'])
    for name, default in [('sources',"'[]'"),('context',"'{}'"),('feedback',"''"),('feedback_note',"''")]:
        op.add_column('chat_turns',sa.Column(name,sa.Text(),nullable=False,server_default=sa.text(default)))
    op.create_table('knowledge_jobs',sa.Column('id',sa.Text(),primary_key=True),sa.Column('actor_id',sa.BigInteger(),nullable=False),
        *[sa.Column(name,sa.Text(),nullable=False) for name in ('source','payload')],
        *[sa.Column(name,sa.Text(),nullable=False,server_default=sa.text(default)) for name,default in
          [('status',"'queued'"),('error',"''"),('version',"''"),('created_at',ISO),('updated_at',ISO)]])


def downgrade():
    op.drop_column('posts','ai_generated')
    op.drop_table('knowledge_jobs')
    for name in ('sources','context','feedback','feedback_note'):
        op.drop_column('chat_turns',name)
    for table in ('community_audit','user_audit'):
        op.drop_table(table)
    op.drop_column('pets','hidden')
    for name in ('profile_version','avatar_hidden','profile_hidden'):
        op.drop_column('users',name)
