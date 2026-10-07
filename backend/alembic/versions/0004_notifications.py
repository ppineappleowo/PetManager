"""Persist comment, reply and follow notifications."""
from alembic import op
import sqlalchemy as sa

revision = '0004_notifications'
down_revision = '0003_post_bookmarks'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('notifications',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('recipient_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('actor_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('kind', sa.Text(), nullable=False),
        sa.Column('event_key', sa.Text(), nullable=False),
        sa.Column('post_id', sa.BigInteger(), sa.ForeignKey('posts.id'), nullable=True),
        sa.Column('comment_id', sa.BigInteger(), sa.ForeignKey('comments.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('recipient_id', 'event_key', name='notifications_recipient_event_key'),
        sa.CheckConstraint("kind IN ('comment','reply','follow')", name='notifications_kind'))
    op.create_index('notifications_recipient', 'notifications', ['recipient_id', 'id'])
    op.create_index('notifications_unread', 'notifications', ['recipient_id', 'id'], postgresql_where=sa.text('read_at IS NULL'))


def downgrade():
    op.drop_table('notifications')
