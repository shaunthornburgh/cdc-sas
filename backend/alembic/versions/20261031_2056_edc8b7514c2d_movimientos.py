"""movimientos

Revision ID: edc8b7514c2d
Revises: 191ea5bc3ba3
Create Date: 2026-10-31 20:56:47.254323

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "edc8b7514c2d"
down_revision: str | None = "191ea5bc3ba3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_ENUMS = {
    "tipo_movimiento": (
        "salida_ruta",
        "tiempo_detenido",
        "salida_zona",
        "trabajo_campo",
        "atencion_campo",
    ),
    "estado_movimiento": ("sin_justificar", "por_revisar", "aprobada", "rechazada", "registro"),
    "motivo_movimiento": (
        "cita_fuera_ruta",
        "permiso_personal",
        "cita_no_programada",
        "inventario",
        "imprevisto_personal",
    ),
    "tipo_campo": ("apoyo_cita", "acompanamiento_ruta", "salida_grupal", "otra"),
    "actividad_campo": (
        "captacion",
        "visita_propietario",
        "cita_venta",
        "cita_arriendo",
        "inventario",
        "otra",
    ),
    "tipo_evento_movimiento": (
        "creado",
        "justificado",
        "aprobado",
        "rechazado",
        "finalizado",
        "ubicacion",
        "config",
        "descarga",
    ),
}


def upgrade() -> None:
    bind = op.get_bind()
    for name, values in NEW_ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)
    op.create_table(
        "movimientos_config",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("minutos_alerta", sa.SmallInteger(), server_default="20", nullable=False),
        sa.Column("plazo_horas", sa.SmallInteger(), nullable=True),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name=op.f("ck_movimientos_config_una_fila")),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_movimientos_config_updated_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_movimientos_config")),
    )
    op.create_table(
        "movimientos",
        sa.Column("numero", sa.Integer(), sa.Identity(always=False, start=1), nullable=False),
        sa.Column("empleado_id", sa.Uuid(), nullable=False),
        sa.Column(
            "tipo", postgresql.ENUM(name="tipo_movimiento", create_type=False), nullable=False
        ),
        sa.Column(
            "estado", postgresql.ENUM(name="estado_movimiento", create_type=False), nullable=False
        ),
        sa.Column("ocurrido_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("minutos_umbral", sa.SmallInteger(), nullable=True),
        sa.Column("lat", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("lng", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("lugar", sa.String(length=120), nullable=True),
        sa.Column(
            "motivo", postgresql.ENUM(name="motivo_movimiento", create_type=False), nullable=True
        ),
        sa.Column("inmueble_codigo", sa.String(length=40), nullable=True),
        sa.Column("inmueble_id", sa.Uuid(), nullable=True),
        sa.Column("cliente", sa.String(length=200), nullable=True),
        sa.Column("motivo_texto", sa.String(length=300), nullable=True),
        sa.Column("autorizo", sa.String(length=20), nullable=True),
        sa.Column("evidencias", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("observacion", sa.String(length=500), nullable=True),
        sa.Column("justificada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revisado_por_id", sa.Uuid(), nullable=True),
        sa.Column("revisado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nota_revision", sa.String(length=300), nullable=True),
        sa.Column(
            "tipo_campo", postgresql.ENUM(name="tipo_campo", create_type=False), nullable=True
        ),
        sa.Column(
            "actividad_campo",
            postgresql.ENUM(name="actividad_campo", create_type=False),
            nullable=True,
        ),
        sa.Column("cita_id", sa.Uuid(), nullable=True),
        sa.Column(
            "acompanados_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("detalle", sa.String(length=300), nullable=True),
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
            "(tipo IN ('trabajo_campo', 'atencion_campo')) = (estado = 'registro')",
            name=op.f("ck_movimientos_estado_registro"),
        ),
        sa.CheckConstraint(
            "fin_at IS NULL OR fin_at >= ocurrido_at", name=op.f("ck_movimientos_fechas")
        ),
        sa.ForeignKeyConstraint(
            ["cita_id"],
            ["citas.id"],
            name=op.f("fk_movimientos_cita_id_citas"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["creado_por_id"],
            ["users.id"],
            name=op.f("fk_movimientos_creado_por_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["empleado_id"],
            ["users.id"],
            name=op.f("fk_movimientos_empleado_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["inmueble_id"],
            ["inmuebles.id"],
            name=op.f("fk_movimientos_inmueble_id_inmuebles"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["revisado_por_id"],
            ["users.id"],
            name=op.f("fk_movimientos_revisado_por_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_movimientos")),
        sa.UniqueConstraint("numero", name=op.f("uq_movimientos_numero")),
    )
    op.create_index(
        op.f("ix_movimientos_empleado_id"), "movimientos", ["empleado_id"], unique=False
    )
    op.create_index(op.f("ix_movimientos_estado"), "movimientos", ["estado"], unique=False)
    op.create_index(
        op.f("ix_movimientos_ocurrido_at"), "movimientos", ["ocurrido_at"], unique=False
    )
    op.create_table(
        "movimiento_eventos",
        sa.Column("movimiento_id", sa.Uuid(), nullable=True),
        sa.Column(
            "tipo",
            postgresql.ENUM(name="tipo_evento_movimiento", create_type=False),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("estado_antes", sa.String(length=30), nullable=True),
        sa.Column("estado_despues", sa.String(length=30), nullable=True),
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
            name=op.f("fk_movimiento_eventos_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["movimiento_id"],
            ["movimientos.id"],
            name=op.f("fk_movimiento_eventos_movimiento_id_movimientos"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_movimiento_eventos")),
    )
    op.create_index(
        op.f("ix_movimiento_eventos_movimiento_id"),
        "movimiento_eventos",
        ["movimiento_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_movimiento_eventos_movimiento_id"), table_name="movimiento_eventos")
    op.drop_table("movimiento_eventos")
    op.drop_index(op.f("ix_movimientos_ocurrido_at"), table_name="movimientos")
    op.drop_index(op.f("ix_movimientos_estado"), table_name="movimientos")
    op.drop_index(op.f("ix_movimientos_empleado_id"), table_name="movimientos")
    op.drop_table("movimientos")
    op.drop_table("movimientos_config")
    bind = op.get_bind()
    for name in NEW_ENUMS:
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
