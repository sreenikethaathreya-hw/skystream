"""add country dimension, uploads, users, scopes, settings, seasonality

Figure tables (market, plan, monthly, competitors, grower potential) are recreated with a country
column because their contents are always reloaded from the demo seed or from admin uploads.
User-entered tables (demand_entries, claims, track records) are altered in place and backfilled to ES.

Revision ID: 88ac1681fc1f
Revises: 09f0c4196760
Create Date: 2026-09-30 17:49:42.475189

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "88ac1681fc1f"
down_revision: Union[str, None] = "09f0c4196760"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COUNTRIES = [
    ("ES", "Spain", ["SPAIN", "ESPANA", "ESPAÑA", "ESP"], "EUR"),
    ("PT", "Portugal", ["PORTUGAL", "PRT"], "EUR"),
    ("FR", "France", ["FRANCE", "FRA"], "EUR"),
    ("IT", "Italy", ["ITALY", "ITALIA", "ITA"], "EUR"),
    ("DE", "Germany", ["GERMANY", "DEUTSCHLAND", "DEU"], "EUR"),
    ("NL", "Netherlands", ["NETHERLANDS", "THE NETHERLANDS", "HOLLAND", "NLD"], "EUR"),
    ("BE", "Belgium", ["BELGIUM", "BEL"], "EUR"),
    ("GR", "Greece", ["GREECE", "GRC"], "EUR"),
    ("PL", "Poland", ["POLAND", "POL"], "PLN"),
    ("RO", "Romania", ["ROMANIA", "ROU"], "RON"),
    ("HU", "Hungary", ["HUNGARY", "HUN"], "HUF"),
    ("GB", "United Kingdom", ["UNITED KINGDOM", "UK", "GBR", "GREAT BRITAIN"], "GBP"),
    ("IE", "Ireland", ["IRELAND", "IRL"], "EUR"),
    ("AT", "Austria", ["AUSTRIA", "AUT"], "EUR"),
    ("CH", "Switzerland", ["SWITZERLAND", "CHE"], "CHF"),
    ("TR", "Turkey", ["TURKEY", "TÜRKIYE", "TURKIYE", "TUR"], "TRY"),
    ("MA", "Morocco", ["MOROCCO", "MAR"], "MAD"),
    ("EG", "Egypt", ["EGYPT", "EGY"], "EGP"),
    ("IL", "Israel", ["ISRAEL", "ISR"], "ILS"),
    ("UA", "Ukraine", ["UKRAINE", "UKR"], "UAH"),
    ("RU", "Russia", ["RUSSIA", "RUSSIAN FEDERATION", "RUS"], "RUB"),
    ("US", "United States", ["UNITED STATES", "USA", "US"], "USD"),
    ("CA", "Canada", ["CANADA", "CAN"], "CAD"),
    ("MX", "Mexico", ["MEXICO", "MÉXICO", "MEX"], "MXN"),
    ("BR", "Brazil", ["BRAZIL", "BRASIL", "BRA"], "BRL"),
    ("AR", "Argentina", ["ARGENTINA", "ARG"], "ARS"),
    ("CL", "Chile", ["CHILE", "CHL"], "CLP"),
    ("PE", "Peru", ["PERU", "PER"], "PEN"),
    ("CO", "Colombia", ["COLOMBIA", "COL"], "COP"),
    ("IN", "India", ["INDIA", "IND"], "INR"),
    ("CN", "China", ["CHINA", "CHN"], "CNY"),
    ("JP", "Japan", ["JAPAN", "JPN"], "JPY"),
    ("KR", "South Korea", ["SOUTH KOREA", "KOREA", "KOR"], "KRW"),
    ("AU", "Australia", ["AUSTRALIA", "AUS"], "AUD"),
    ("ZA", "South Africa", ["SOUTH AFRICA", "ZAF"], "ZAR"),
    ("KE", "Kenya", ["KENYA", "KEN"], "KES"),
]

FIGURE_TABLES = [
    "monthly_plan",
    "monthly_actuals",
    "market_years",
    "plan_years",
    "competitor_shares",
    "grower_potential",
]


def _country_col() -> sa.Column:
    return sa.Column("country_code", sa.String(length=2), nullable=False)


def _index(table: str, *columns: str) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column], unique=False)


def _create_figure_tables() -> None:
    op.create_table(
        "market_years",
        sa.Column("id", sa.Integer(), nullable=False),
        _country_col(),
        sa.Column("segment_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("hectares", sa.Float(), nullable=False),
        sa.Column("qty_ks", sa.Float(), nullable=False),
        sa.Column("density", sa.Float(), nullable=False),
        sa.Column("price_exseed", sa.Float(), nullable=False),
        sa.Column("price_farmgate", sa.Float(), nullable=False),
        sa.Column("notes", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["segment_id"], ["segments.id"], name="fk_market_years_segment_id_segments"),
        sa.PrimaryKeyConstraint("id", name="pk_market_years"),
        sa.UniqueConstraint(
            "country_code", "segment_id", "year", name="uq_market_years_country_code_segment_id_year"
        ),
    )
    _index("market_years", "country_code", "segment_id")

    op.create_table(
        "plan_years",
        sa.Column("id", sa.Integer(), nullable=False),
        _country_col(),
        sa.Column("segment_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("qty_ks", sa.Float(), nullable=False),
        sa.Column("value_eur", sa.Float(), nullable=False),
        sa.Column("net_price", sa.Float(), nullable=False),
        sa.Column("fpi_qty_ks", sa.Float(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["segment_id"], ["segments.id"], name="fk_plan_years_segment_id_segments"),
        sa.PrimaryKeyConstraint("id", name="pk_plan_years"),
        sa.UniqueConstraint(
            "country_code", "segment_id", "year", name="uq_plan_years_country_code_segment_id_year"
        ),
    )
    _index("plan_years", "country_code", "segment_id")

    for table in ("monthly_actuals", "monthly_plan"):
        extra = (
            [sa.Column("value_eur", sa.Float(), nullable=False)]
            if table == "monthly_actuals"
            else [sa.Column("basis", sa.String(length=30), nullable=False)]
        )
        op.create_table(
            table,
            sa.Column("id", sa.Integer(), nullable=False),
            _country_col(),
            sa.Column("segment_id", sa.Integer(), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("month", sa.Integer(), nullable=False),
            sa.Column("qty_ks", sa.Float(), nullable=False),
            *extra,
            sa.ForeignKeyConstraint(["segment_id"], ["segments.id"], name=f"fk_{table}_segment_id_segments"),
            sa.PrimaryKeyConstraint("id", name=f"pk_{table}"),
            sa.UniqueConstraint(
                "country_code",
                "segment_id",
                "year",
                "month",
                name=f"uq_{table}_country_code_segment_id_year_month",
            ),
        )
        _index(table, "country_code", "segment_id")

    op.create_table(
        "competitor_shares",
        sa.Column("id", sa.Integer(), nullable=False),
        _country_col(),
        sa.Column("mega_segment_id", sa.String(length=10), nullable=False),
        sa.Column("competitor", sa.String(length=80), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("share_pct", sa.Float(), nullable=False),
        sa.Column("value_eur", sa.Float(), nullable=False),
        sa.Column("trend", sa.String(length=30), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_competitor_shares"),
        sa.UniqueConstraint(
            "country_code",
            "mega_segment_id",
            "competitor",
            "year",
            name="uq_competitor_shares_key",
        ),
    )
    _index("competitor_shares", "country_code", "mega_segment_id")

    op.create_table(
        "grower_potential",
        sa.Column("id", sa.Integer(), nullable=False),
        _country_col(),
        sa.Column("crop_local", sa.String(length=120), nullable=False),
        sa.Column("variety", sa.String(length=80), nullable=True),
        sa.Column("owner", sa.String(length=20), nullable=False),
        sa.Column("hectares", sa.Float(), nullable=False),
        sa.Column("density", sa.Float(), nullable=False),
        sa.Column("region", sa.String(length=80), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_grower_potential"),
    )
    _index("grower_potential", "country_code", "crop_local")


def upgrade() -> None:
    for table in FIGURE_TABLES:
        op.drop_table(table)
    _create_figure_tables()

    with op.batch_alter_table("segments") as batch_op:
        batch_op.add_column(sa.Column("species", sa.String(length=80), nullable=True))
        batch_op.alter_column(
            "owner_id", existing_type=sa.String(length=40), type_=sa.String(length=200), nullable=True
        )
        batch_op.create_index("ix_segments_species", ["species"], unique=False)

    with op.batch_alter_table("demand_entries") as batch_op:
        batch_op.add_column(
            sa.Column("country_code", sa.String(length=2), server_default="ES", nullable=False)
        )
        batch_op.alter_column("user_id", existing_type=sa.String(length=40), type_=sa.String(length=200))
        batch_op.alter_column("reviewed_by", existing_type=sa.String(length=40), type_=sa.String(length=200))
        batch_op.create_index("ix_demand_entries_country_code", ["country_code"], unique=False)

    with op.batch_alter_table("rep_track_records") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.String(length=40), type_=sa.String(length=200))

    countries = op.create_table(
        "countries",
        sa.Column("code", sa.String(length=2), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.PrimaryKeyConstraint("code", name="pk_countries"),
    )
    op.bulk_insert(
        countries,
        [{"code": c, "name": n, "aliases": a, "currency": cur} for c, n, a, cur in COUNTRIES],
    )

    op.create_table(
        "upload_batches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("uploaded_by", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("rows_read", sa.Integer(), nullable=False),
        sa.Column("accepted", sa.Integer(), nullable=False),
        sa.Column("rejected", sa.Integer(), nullable=False),
        sa.Column("warnings", sa.Integer(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("commit_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_upload_batches"),
    )
    _index("upload_batches", "kind", "status")

    op.create_table(
        "app_users",
        sa.Column("id", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_app_users"),
    )
    op.create_table(
        "user_scopes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=200), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("scope_type", sa.String(length=10), nullable=False),
        sa.Column("scope_id", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_users.id"], name="fk_user_scopes_user_id_app_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_scopes"),
        sa.UniqueConstraint(
            "user_id",
            "country_code",
            "scope_type",
            "scope_id",
            name="uq_user_scopes_user_id_country_code_scope_type_scope_id",
        ),
    )
    _index("user_scopes", "user_id")

    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=60), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(length=200), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_settings"),
    )
    op.create_table(
        "seasonality",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("scope_type", sa.String(length=10), nullable=False),
        sa.Column("scope_id", sa.String(length=20), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_seasonality"),
        sa.UniqueConstraint(
            "country_code",
            "scope_type",
            "scope_id",
            "month",
            name="uq_seasonality_country_code_scope_type_scope_id_month",
        ),
    )
    _index("seasonality", "country_code")


def downgrade() -> None:
    for table in ("seasonality", "settings", "user_scopes", "app_users", "upload_batches", "countries"):
        op.drop_table(table)
    with op.batch_alter_table("demand_entries") as batch_op:
        batch_op.drop_index("ix_demand_entries_country_code")
        batch_op.drop_column("country_code")
    with op.batch_alter_table("segments") as batch_op:
        batch_op.drop_index("ix_segments_species")
        batch_op.drop_column("species")
    for table in FIGURE_TABLES:
        op.drop_table(table)
    raise RuntimeError(
        "Figure tables were dropped; rerun the previous revision's create statements and reseed to finish downgrading."
    )
