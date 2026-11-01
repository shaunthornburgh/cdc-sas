"""plataformas

Revision ID: 9b057f2ad5c6
Revises: edc8b7514c2d
Create Date: 2026-10-31 22:10:08.606413

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "9b057f2ad5c6"
down_revision: str | None = "edc8b7514c2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_ENUMS = {
    "tipo_evento_plataforma": (
        "responsable",
        "plan",
        "activa",
        "regla",
        "descarga",
    ),
}


def upgrade() -> None:
    bind = op.get_bind()
    for name, values in NEW_ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)
    op.create_table(
        "plataformas",
        sa.Column("fuente", postgresql.ENUM(name="fuente_lead", create_type=False), nullable=False),
        sa.Column("nombre", sa.String(length=80), nullable=False),
        sa.Column("color", sa.String(length=7), server_default="#00843D", nullable=False),
        sa.Column("orden", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("activa", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("responsable_id", sa.Uuid(), nullable=True),
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
            ["responsable_id"],
            ["users.id"],
            name=op.f("fk_plataformas_responsable_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plataformas")),
        sa.UniqueConstraint("fuente", name=op.f("uq_plataformas_fuente")),
    )
    op.create_table(
        "plataformas_config",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("dias_regla", sa.SmallInteger(), server_default="7", nullable=False),
        sa.Column("confirmada", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name=op.f("ck_plataformas_config_una_fila")),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_plataformas_config_updated_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plataformas_config")),
    )
    op.create_table(
        "plataforma_actualizaciones",
        sa.Column("plataforma_id", sa.Uuid(), nullable=False),
        sa.Column(
            "realizada_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("actualizado_por_id", sa.Uuid(), nullable=True),
        sa.Column("responsable_id", sa.Uuid(), nullable=True),
        sa.Column("cupo_total", sa.SmallInteger(), nullable=False),
        sa.Column("cupo_usado", sa.SmallInteger(), nullable=False),
        sa.Column("destacados_total", sa.SmallInteger(), nullable=False),
        sa.Column("destacados_usados", sa.SmallInteger(), nullable=False),
        sa.Column("observacion", sa.String(length=300), nullable=True),
        sa.Column("dias_desde_anterior", sa.SmallInteger(), nullable=True),
        sa.Column("regla_dias", sa.SmallInteger(), nullable=False),
        sa.Column("a_tiempo", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "cupo_usado >= 0 AND cupo_usado <= cupo_total "
            "AND destacados_usados >= 0 AND destacados_usados <= destacados_total",
            name=op.f("ck_plataforma_actualizaciones_cupos"),
        ),
        sa.ForeignKeyConstraint(
            ["actualizado_por_id"],
            ["users.id"],
            name=op.f("fk_plataforma_actualizaciones_actualizado_por_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["plataforma_id"],
            ["plataformas.id"],
            name=op.f("fk_plataforma_actualizaciones_plataforma_id_plataformas"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["responsable_id"],
            ["users.id"],
            name=op.f("fk_plataforma_actualizaciones_responsable_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plataforma_actualizaciones")),
    )
    op.create_index(
        op.f("ix_plataforma_actualizaciones_plataforma_id"),
        "plataforma_actualizaciones",
        ["plataforma_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_plataforma_actualizaciones_realizada_at"),
        "plataforma_actualizaciones",
        ["realizada_at"],
        unique=False,
    )
    op.create_table(
        "plataforma_eventos",
        sa.Column("plataforma_id", sa.Uuid(), nullable=True),
        sa.Column(
            "tipo",
            postgresql.ENUM(name="tipo_evento_plataforma", create_type=False),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("antes", sa.String(length=200), nullable=True),
        sa.Column("despues", sa.String(length=200), nullable=True),
        sa.Column("detalle", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_plataforma_eventos_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["plataforma_id"],
            ["plataformas.id"],
            name=op.f("fk_plataforma_eventos_plataforma_id_plataformas"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plataforma_eventos")),
    )
    op.create_index(
        op.f("ix_plataforma_eventos_plataforma_id"),
        "plataforma_eventos",
        ["plataforma_id"],
        unique=False,
    )
    op.create_table(
        "plataforma_planes",
        sa.Column("plataforma_id", sa.Uuid(), nullable=False),
        sa.Column("precio", sa.BigInteger(), nullable=False),
        sa.Column("activacion", sa.Date(), nullable=False),
        sa.Column("vencimiento", sa.Date(), nullable=False),
        sa.Column("cupo_total", sa.SmallInteger(), nullable=False),
        sa.Column("destacados_total", sa.SmallInteger(), nullable=False),
        sa.Column("alarma_dias", sa.SmallInteger(), server_default="10", nullable=False),
        sa.Column("creado_por_id", sa.Uuid(), nullable=True),
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
        sa.CheckConstraint(
            "precio >= 0 AND cupo_total >= 0 AND destacados_total >= 0",
            name=op.f("ck_plataforma_planes_valores"),
        ),
        sa.CheckConstraint("vencimiento >= activacion", name=op.f("ck_plataforma_planes_fechas")),
        sa.ForeignKeyConstraint(
            ["creado_por_id"],
            ["users.id"],
            name=op.f("fk_plataforma_planes_creado_por_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["plataforma_id"],
            ["plataformas.id"],
            name=op.f("fk_plataforma_planes_plataforma_id_plataformas"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plataforma_planes")),
    )
    op.create_index(
        op.f("ix_plataforma_planes_plataforma_id"),
        "plataforma_planes",
        ["plataforma_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_plataforma_planes_plataforma_id"), table_name="plataforma_planes")
    op.drop_table("plataforma_planes")
    op.drop_index(op.f("ix_plataforma_eventos_plataforma_id"), table_name="plataforma_eventos")
    op.drop_table("plataforma_eventos")
    op.drop_index(
        op.f("ix_plataforma_actualizaciones_realizada_at"), table_name="plataforma_actualizaciones"
    )
    op.drop_index(
        op.f("ix_plataforma_actualizaciones_plataforma_id"), table_name="plataforma_actualizaciones"
    )
    op.drop_table("plataforma_actualizaciones")
    op.drop_table("plataformas_config")
    op.drop_table("plataformas")
    bind = op.get_bind()
    for name in NEW_ENUMS:
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
