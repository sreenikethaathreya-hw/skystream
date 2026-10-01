"""add lead rules

Revision ID: 12b29bdda6f4
Revises: 88ac1681fc1f
Create Date: 2026-09-30 23:25:49.920084

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = '12b29bdda6f4'
down_revision: Union[str, None] = '88ac1681fc1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('lead_rules',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('country_code', sa.String(length=2), nullable=False),
    sa.Column('mega_segment_id', sa.String(length=10), nullable=False),
    sa.Column('segment_ids', sa.JSON(), nullable=True),
    sa.Column('months', sa.JSON(), nullable=True),
    sa.Column('metric', sa.String(length=30), nullable=False),
    sa.Column('comparator', sa.String(length=10), nullable=False),
    sa.Column('threshold', sa.Float(), nullable=False),
    sa.Column('required_driver', sa.String(length=40), nullable=True),
    sa.Column('severity', sa.String(length=10), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('decisions', sa.JSON(), nullable=False),
    sa.Column('provider', sa.String(length=40), nullable=False),
    sa.Column('source_entry_id', sa.String(length=36), nullable=True),
    sa.Column('created_by', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('retired_by', sa.String(length=200), nullable=True),
    sa.Column('retired_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['source_entry_id'], ['demand_entries.id'], name=op.f('fk_lead_rules_source_entry_id_demand_entries')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lead_rules'))
    )
    with op.batch_alter_table('lead_rules', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lead_rules_active'), ['active'], unique=False)
        batch_op.create_index(batch_op.f('ix_lead_rules_country_code'), ['country_code'], unique=False)
        batch_op.create_index(batch_op.f('ix_lead_rules_mega_segment_id'), ['mega_segment_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('lead_rules', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lead_rules_mega_segment_id'))
        batch_op.drop_index(batch_op.f('ix_lead_rules_country_code'))
        batch_op.drop_index(batch_op.f('ix_lead_rules_active'))

    op.drop_table('lead_rules')
