"""PostgreSQL baseline: users, community, pets and chat history.

Revision ID: 0001_postgresql
Revises: None
Frozen SQL snapshot is part of this revision; do not change after deployment.
"""
from pathlib import Path
from alembic import op

revision = '0001_postgresql'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    snapshot = Path(__file__).with_name('0001_postgresql.sql').read_text(encoding='utf-8')
    for statement in snapshot.split(';'):
        if statement.strip():
            op.execute(statement.strip())


def downgrade():
    # Destructive baseline downgrade: run only after backup and review.
    for table in ('data_imports','writes','checkpoints','chat_turns','post_pets','pets','reports',
                  'comment_moderation','post_likes','comments','moderation','media','posts',
                  'users','community_migrations','app_migrations'):
        op.drop_table(table)
