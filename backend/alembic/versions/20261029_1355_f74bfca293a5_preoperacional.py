"""preoperacional

Revision ID: f74bfca293a5
Revises: ec9ca2b2c984
Create Date: 2026-10-29 13:55:35.492369

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f74bfca293a5"
down_revision: str | None = "ec9ca2b2c984"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "preoperacional_config",
        sa.Column("cargo", postgresql.ENUM(name="cargo", create_type=False), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_preoperacional_config_updated_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("cargo", name=op.f("pk_preoperacional_config")),
    )
    op.create_table(
        "preoperacionales",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("realizado_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "medio",
            sa.Enum(
                "carro",
                "moto",
                "bicicleta",
                "transporte_publico",
                "a_pie",
                "otro",
                name="medio_transporte",
            ),
            nullable=False,
        ),
        sa.Column("placa", sa.String(length=10), nullable=True),
        sa.Column(
            "respuestas",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("observaciones", sa.Text(), nullable=True),
        sa.Column("tiene_novedad", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("revisado_por_id", sa.Uuid(), nullable=True),
        sa.Column("revisado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision_nota", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["revisado_por_id"],
            ["users.id"],
            name=op.f("fk_preoperacionales_revisado_por_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_preoperacionales_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_preoperacionales")),
        sa.UniqueConstraint("user_id", "fecha", name="uq_preoperacionales_user_fecha"),
    )
    op.create_index(op.f("ix_preoperacionales_fecha"), "preoperacionales", ["fecha"], unique=False)
    op.create_index(
        op.f("ix_preoperacionales_user_id"), "preoperacionales", ["user_id"], unique=False
    )
    # Every cargo starts with the preoperacional active (G-012).
    op.execute(
        "INSERT INTO preoperacional_config (cargo, activo) VALUES "
        "('gerencia', true), ('coordinacion', true), ('asesor', true), "
        "('auxiliar_administrativa', true), ('atencion_cliente', true)"
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_preoperacionales_user_id"), table_name="preoperacionales")
    op.drop_index(op.f("ix_preoperacionales_fecha"), table_name="preoperacionales")
    op.drop_table("preoperacionales")
    op.drop_table("preoperacional_config")
    sa.Enum(name="medio_transporte").drop(op.get_bind(), checkfirst=True)
