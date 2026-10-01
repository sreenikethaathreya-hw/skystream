"""money in usd and budget rates

Values are net USD at the Syngenta budget rate (SME answer), so the *_eur columns are renamed in place.

Revision ID: 3c1d7e2a9b40
Revises: 12b29bdda6f4
Create Date: 2026-10-01 12:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "3c1d7e2a9b40"
down_revision: Union[str, None] = "12b29bdda6f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RENAMED = ("plan_years", "monthly_actuals", "competitor_shares")


def upgrade() -> None:
    for table in RENAMED:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column("value_eur", new_column_name="value_usd")

    op.create_table(
        "fx_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("budget_year", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("currency_name", sa.String(length=80), nullable=True),
        sa.Column("per_usd", sa.Float(), nullable=False),
        sa.Column("batch_id", sa.String(length=36), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fx_rates")),
        sa.UniqueConstraint("budget_year", "currency", name="uq_fx_rates_year_currency"),
    )
    with op.batch_alter_table("fx_rates", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_fx_rates_budget_year"), ["budget_year"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("fx_rates", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_fx_rates_budget_year"))
    op.drop_table("fx_rates")
    for table in RENAMED:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column("value_usd", new_column_name="value_eur")
