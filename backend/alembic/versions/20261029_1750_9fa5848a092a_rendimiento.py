"""rendimiento

Revision ID: 9fa5848a092a
Revises: 9925218b240d
Create Date: 2026-10-29 17:50:09.100651

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "9fa5848a092a"
down_revision: str | None = "9925218b240d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "calificaciones",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("periodo", sa.Date(), nullable=False),
        sa.Column("indicador", sa.String(length=40), nullable=False),
        sa.Column("valor", sa.SmallInteger(), nullable=False),
        sa.Column("calificado_por_id", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("valor BETWEEN 1 AND 5", name=op.f("ck_calificaciones_valor_1_5")),
        sa.ForeignKeyConstraint(
            ["calificado_por_id"],
            ["users.id"],
            name=op.f("fk_calificaciones_calificado_por_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_calificaciones_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calificaciones")),
        sa.UniqueConstraint("user_id", "periodo", "indicador", name="uq_calificacion"),
    )
    op.create_index(op.f("ix_calificaciones_user_id"), "calificaciones", ["user_id"], unique=False)
    op.create_table(
        "rendimiento_cambios",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("periodo", sa.Date(), nullable=False),
        sa.Column(
            "antes", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "despues", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_rendimiento_cambios_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_rendimiento_cambios_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rendimiento_cambios")),
    )
    op.create_index(
        op.f("ix_rendimiento_cambios_user_id"), "rendimiento_cambios", ["user_id"], unique=False
    )
    op.create_table(
        "rendimiento_config",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("periodo", sa.Date(), nullable=False),
        sa.Column(
            "pesos", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "metas", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_rendimiento_config_updated_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_rendimiento_config_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rendimiento_config")),
        sa.UniqueConstraint("user_id", "periodo", name="uq_rendimiento_config_periodo"),
    )


def downgrade() -> None:
    op.drop_table("rendimiento_config")
    op.drop_index(op.f("ix_rendimiento_cambios_user_id"), table_name="rendimiento_cambios")
    op.drop_table("rendimiento_cambios")
    op.drop_index(op.f("ix_calificaciones_user_id"), table_name="calificaciones")
    op.drop_table("calificaciones")
