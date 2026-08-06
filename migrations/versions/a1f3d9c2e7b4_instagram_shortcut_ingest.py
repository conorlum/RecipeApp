"""add users.api_token, recipes.raw_image, recipes.needs_review

Revision ID: a1f3d9c2e7b4
Revises: c156e015d4be
Create Date: 2026-08-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1f3d9c2e7b4'
down_revision = 'c156e015d4be'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('api_token', sa.String(length=128), nullable=True))
    with op.batch_alter_table('users') as batch_op:
        batch_op.create_unique_constraint('uq_users_api_token', ['api_token'])

    op.add_column('recipes', sa.Column('raw_image', sa.LargeBinary(), nullable=True))
    op.add_column(
        'recipes',
        sa.Column('needs_review', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column('recipes', 'needs_review')
    op.drop_column('recipes', 'raw_image')

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('uq_users_api_token', type_='unique')
    op.drop_column('users', 'api_token')
