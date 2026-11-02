"""rutas

Revision ID: 0b212b2789de
Revises: 22a26b3f8a7e
Create Date: 2026-11-02 20:24:38.928228

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0b212b2789de"
down_revision: str | None = "22a26b3f8a7e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rutas",
        sa.Column("asesor_id", sa.Uuid(), nullable=False),
        sa.Column("desde", sa.Date(), nullable=False),
        sa.Column("hasta", sa.Date(), nullable=False),
        sa.Column("dias", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("observacion", sa.String(length=300), nullable=True),
        sa.Column("origen", sa.String(length=10), nullable=False),
        sa.Column("estado", sa.String(length=15), nullable=False),
        sa.Column("motivo", sa.String(length=60), nullable=True),
        sa.Column("motivo_texto", sa.String(length=500), nullable=True),
        sa.Column("respondida_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reemplaza_id", sa.Uuid(), nullable=True),
        sa.Column("creado_por_id", sa.Uuid(), nullable=True),
        sa.Column("calificacion", sa.SmallInteger(), nullable=True),
        sa.Column("calificada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("calificada_por_id", sa.Uuid(), nullable=True),
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
            ["asesor_id"], ["users.id"], name=op.f("fk_rutas_asesor_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["calificada_por_id"],
            ["users.id"],
            name=op.f("fk_rutas_calificada_por_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["creado_por_id"],
            ["users.id"],
            name=op.f("fk_rutas_creado_por_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reemplaza_id"],
            ["rutas.id"],
            name=op.f("fk_rutas_reemplaza_id_rutas"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rutas")),
    )
    op.create_index(op.f("ix_rutas_asesor_id"), "rutas", ["asesor_id"], unique=False)
    op.create_index(op.f("ix_rutas_desde"), "rutas", ["desde"], unique=False)
    op.create_index(op.f("ix_rutas_estado"), "rutas", ["estado"], unique=False)
    op.create_index(op.f("ix_rutas_hasta"), "rutas", ["hasta"], unique=False)
    op.create_table(
        "ruta_eventos",
        sa.Column("ruta_id", sa.Uuid(), nullable=False),
        sa.Column("accion", sa.String(length=200), nullable=False),
        sa.Column("antes", sa.String(length=300), nullable=True),
        sa.Column("despues", sa.String(length=500), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
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
            name=op.f("fk_ruta_eventos_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ruta_id"],
            ["rutas.id"],
            name=op.f("fk_ruta_eventos_ruta_id_rutas"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ruta_eventos")),
    )
    op.create_index(
        op.f("ix_ruta_eventos_created_at"), "ruta_eventos", ["created_at"], unique=False
    )
    op.create_index(op.f("ix_ruta_eventos_ruta_id"), "ruta_eventos", ["ruta_id"], unique=False)
    op.create_table(
        "ruta_zonas",
        sa.Column("ruta_id", sa.Uuid(), nullable=False),
        sa.Column("orden", sa.SmallInteger(), nullable=False),
        sa.Column("zona", sa.String(length=60), nullable=False),
        sa.Column("hora_inicio", sa.Time(), nullable=False),
        sa.Column("hora_fin", sa.Time(), nullable=False),
        sa.Column("dias", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ruta_id"], ["rutas.id"], name=op.f("fk_ruta_zonas_ruta_id_rutas"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ruta_zonas")),
    )
    op.create_index(op.f("ix_ruta_zonas_ruta_id"), "ruta_zonas", ["ruta_id"], unique=False)
    op.create_table(
        "ruta_llegadas",
        sa.Column("zona_id", sa.Uuid(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("llegada_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("nota", sa.String(length=300), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["zona_id"],
            ["ruta_zonas.id"],
            name=op.f("fk_ruta_llegadas_zona_id_ruta_zonas"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ruta_llegadas")),
        sa.UniqueConstraint("zona_id", "fecha", name=op.f("uq_ruta_llegadas_zona_id")),
    )
    op.create_index(op.f("ix_ruta_llegadas_zona_id"), "ruta_llegadas", ["zona_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ruta_llegadas_zona_id"), table_name="ruta_llegadas")
    op.drop_table("ruta_llegadas")
    op.drop_index(op.f("ix_ruta_zonas_ruta_id"), table_name="ruta_zonas")
    op.drop_table("ruta_zonas")
    op.drop_index(op.f("ix_ruta_eventos_ruta_id"), table_name="ruta_eventos")
    op.drop_index(op.f("ix_ruta_eventos_created_at"), table_name="ruta_eventos")
    op.drop_table("ruta_eventos")
    op.drop_index(op.f("ix_rutas_hasta"), table_name="rutas")
    op.drop_index(op.f("ix_rutas_estado"), table_name="rutas")
    op.drop_index(op.f("ix_rutas_desde"), table_name="rutas")
    op.drop_index(op.f("ix_rutas_asesor_id"), table_name="rutas")
    op.drop_table("rutas")
