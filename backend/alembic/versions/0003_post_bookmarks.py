"""Add private post bookmarks."""
from alembic import op
import sqlalchemy as sa

revision = '0003_post_bookmarks'
down_revision = '0002_user_follows'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('post_bookmarks',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('post_id', sa.BigInteger(), sa.ForeignKey('posts.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('user_id', 'post_id', name='post_bookmarks_user_post_key'))
    op.create_index('post_bookmarks_owner', 'post_bookmarks', ['user_id', 'id'])


def downgrade():
    op.drop_index('post_bookmarks_owner', table_name='post_bookmarks')
    op.drop_table('post_bookmarks')
