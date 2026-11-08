"""asistencia

Revision ID: 321a4093b8bb
Revises: 0b212b2789de
Create Date: 2026-11-02 20:43:05.697822

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "321a4093b8bb"
down_revision: str | None = "0b212b2789de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "marcaciones",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("asignada", sa.String(length=120), nullable=False),
        sa.Column("entrada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entrada_lat", sa.Float(), nullable=True),
        sa.Column("entrada_lng", sa.Float(), nullable=True),
        sa.Column("entrada_lugar", sa.String(length=120), nullable=True),
        sa.Column("entrada_dentro", sa.Boolean(), nullable=True),
        sa.Column("entrada_estado", sa.String(length=15), nullable=True),
        sa.Column("minutos_tarde", sa.Integer(), server_default="0", nullable=False),
        sa.Column("entrada_motivo", sa.String(length=30), nullable=True),
        sa.Column("entrada_texto", sa.String(length=500), nullable=True),
        sa.Column("entrada_revisada_por_id", sa.Uuid(), nullable=True),
        sa.Column("entrada_revisada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("salida_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("salida_lat", sa.Float(), nullable=True),
        sa.Column("salida_lng", sa.Float(), nullable=True),
        sa.Column("salida_tipo", sa.String(length=15), nullable=True),
        sa.Column("salida_estado", sa.String(length=15), nullable=True),
        sa.Column("minutos_antes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("minutos_extra", sa.Integer(), server_default="0", nullable=False),
        sa.Column("salida_motivo", sa.String(length=30), nullable=True),
        sa.Column("salida_texto", sa.String(length=500), nullable=True),
        sa.Column("salida_revisada_por_id", sa.Uuid(), nullable=True),
        sa.Column("extra_coord", sa.Boolean(), nullable=True),
        sa.Column("extra_aux", sa.Boolean(), nullable=True),
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
            ["entrada_revisada_por_id"],
            ["users.id"],
            name=op.f("fk_marcaciones_entrada_revisada_por_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["salida_revisada_por_id"],
            ["users.id"],
            name=op.f("fk_marcaciones_salida_revisada_por_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_marcaciones_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_marcaciones")),
        sa.UniqueConstraint("user_id", "fecha", name=op.f("uq_marcaciones_user_id")),
    )
    op.create_index(op.f("ix_marcaciones_fecha"), "marcaciones", ["fecha"], unique=False)
    op.create_index(op.f("ix_marcaciones_user_id"), "marcaciones", ["user_id"], unique=False)
    op.create_table(
        "sedes",
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("direccion", sa.String(length=300), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("radio_m", sa.SmallInteger(), server_default="100", nullable=False),
        sa.Column("principal", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("activa", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
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
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_sedes_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sedes")),
    )
    op.create_table(
        "asistencia_eventos",
        sa.Column("marcacion_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("registro", sa.String(length=200), nullable=False),
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
            name=op.f("fk_asistencia_eventos_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["marcacion_id"],
            ["marcaciones.id"],
            name=op.f("fk_asistencia_eventos_marcacion_id_marcaciones"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_asistencia_eventos_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asistencia_eventos")),
    )
    op.create_index(
        op.f("ix_asistencia_eventos_created_at"), "asistencia_eventos", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_asistencia_eventos_marcacion_id"),
        "asistencia_eventos",
        ["marcacion_id"],
        unique=False,
    )
    op.create_table(
        "ubicaciones_asignadas",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("sede_id", sa.Uuid(), nullable=False),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["sede_id"],
            ["sedes.id"],
            name=op.f("fk_ubicaciones_asignadas_sede_id_sedes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_ubicaciones_asignadas_updated_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_ubicaciones_asignadas_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_ubicaciones_asignadas")),
    )


def downgrade() -> None:
    op.drop_table("ubicaciones_asignadas")
    op.drop_index(op.f("ix_asistencia_eventos_marcacion_id"), table_name="asistencia_eventos")
    op.drop_index(op.f("ix_asistencia_eventos_created_at"), table_name="asistencia_eventos")
    op.drop_table("asistencia_eventos")
    op.drop_table("sedes")
    op.drop_index(op.f("ix_marcaciones_user_id"), table_name="marcaciones")
    op.drop_index(op.f("ix_marcaciones_fecha"), table_name="marcaciones")
    op.drop_table("marcaciones")
