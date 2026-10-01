"""user widgets and widget preferences

Revision ID: 5d2f8a1c9e47
Revises: a7bff5427ff3
Create Date: 2026-10-01 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = '5d2f8a1c9e47'
down_revision: Union[str, None] = 'a7bff5427ff3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('user_widget_prefs',
    sa.Column('user_id', sa.String(length=200), nullable=False),
    sa.Column('visible', sa.JSON(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_user_widget_prefs'))
    )
    op.create_table('user_widgets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.String(length=200), nullable=False),
    sa.Column('title', sa.String(length=120), nullable=False),
    sa.Column('tool', sa.String(length=60), nullable=False),
    sa.Column('args', sa.JSON(), nullable=False),
    sa.Column('country_code', sa.String(length=2), nullable=False),
    sa.Column('mega_segment_id', sa.String(length=10), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_widgets'))
    )
    with op.batch_alter_table('user_widgets', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_widgets_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('user_widgets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_widgets_user_id'))

    op.drop_table('user_widgets')
    op.drop_table('user_widget_prefs')
