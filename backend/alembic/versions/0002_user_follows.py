"""Add persistent user follow relationships."""
from alembic import op
import sqlalchemy as sa

revision = '0002_user_follows'
down_revision = '0001_postgresql'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('user_follows',
        sa.Column('follower_id', sa.BigInteger(), sa.ForeignKey('users.id'), primary_key=True, autoincrement=False),
        sa.Column('followed_id', sa.BigInteger(), sa.ForeignKey('users.id'), primary_key=True, autoincrement=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint('follower_id <> followed_id', name='user_follows_no_self'))
    op.create_index('user_follows_followed', 'user_follows', ['followed_id', 'follower_id'])


def downgrade():
    op.drop_index('user_follows_followed', table_name='user_follows')
    op.drop_table('user_follows')
