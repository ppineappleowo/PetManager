"""Index post tags for public discovery and backfill existing posts."""
from alembic import op
import sqlalchemy as sa

revision = '0005_post_tags'
down_revision = '0004_notifications'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('post_tags',
        sa.Column('post_id', sa.BigInteger(), sa.ForeignKey('posts.id'), primary_key=True, autoincrement=False),
        sa.Column('tag', sa.Text(), primary_key=True))
    op.create_index('post_tags_tag', 'post_tags', ['tag', 'post_id'])
    op.execute("INSERT INTO post_tags(post_id,tag) SELECT p.id,t.tag FROM posts p CROSS JOIN LATERAL jsonb_array_elements_text(p.tags::jsonb) AS t(tag) ON CONFLICT DO NOTHING")


def downgrade():
    op.drop_table('post_tags')
