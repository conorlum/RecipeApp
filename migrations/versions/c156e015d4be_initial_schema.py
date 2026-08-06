"""initial schema

Revision ID: c156e015d4be
Revises:
Create Date: 2026-08-05 22:49:34.546760

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

JSONB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


# revision identifiers, used by Alembic.
revision = 'c156e015d4be'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # users and pantries reference each other (users.active_pantry_id ->
    # pantries.id, pantries.owner_id -> users.id). Create users first
    # without the pantry FK, then pantries, then add the FK onto users —
    # avoids a table-creation-order cycle that SQLite tolerates but
    # Postgres does not.
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=80), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('active_pantry_id', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('username')
    )
    op.create_table('quantity_equivalencies',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('phrase', sa.String(length=120), nullable=False),
    sa.Column('quantity', sa.Float(), nullable=False),
    sa.Column('unit', sa.String(length=60), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('phrase')
    )
    op.create_table('pantries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users') as batch_op:
        batch_op.create_foreign_key(
            'fk_users_active_pantry_id_pantries', 'pantries', ['active_pantry_id'], ['id']
        )
    op.create_table('grocery_lists',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('pantry_id_used', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['pantry_id_used'], ['pantries.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('pantry_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('pantry_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('added_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['pantry_id'], ['pantries.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('recipes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('times_made', sa.Integer(), nullable=False),
    sa.Column('servings', sa.Integer(), nullable=True),
    sa.Column('source_type', sa.String(length=20), nullable=False),
    sa.Column('source_url', sa.Text(), nullable=True),
    sa.Column('raw_text', sa.Text(), nullable=True),
    sa.Column('ingredients', JSONB, nullable=False),
    sa.Column('steps', JSONB, nullable=False),
    sa.Column('tags', JSONB, nullable=False),
    sa.Column('shared_from_user_id', sa.Integer(), nullable=True),
    sa.Column('shared_from_recipe_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['shared_from_recipe_id'], ['recipes.id'], ),
    sa.ForeignKeyConstraint(['shared_from_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('grocery_list_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('grocery_list_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('quantity', sa.String(length=60), nullable=True),
    sa.Column('unit', sa.String(length=60), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('checked', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['grocery_list_id'], ['grocery_lists.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('grocery_list_recipes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('grocery_list_id', sa.Integer(), nullable=False),
    sa.Column('recipe_id', sa.Integer(), nullable=False),
    sa.Column('scale', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['grocery_list_id'], ['grocery_lists.id'], ),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('recipe_notes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('recipe_id', sa.Integer(), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('note_text', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('recipe_notes')
    op.drop_table('grocery_list_recipes')
    op.drop_table('grocery_list_items')
    op.drop_table('recipes')
    op.drop_table('pantry_items')
    op.drop_table('grocery_lists')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('fk_users_active_pantry_id_pantries', type_='foreignkey')
    op.drop_table('pantries')
    op.drop_table('quantity_equivalencies')
    op.drop_table('users')
    # ### end Alembic commands ###
