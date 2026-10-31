"""administracion inmuebles

Revision ID: 738115d532c7
Revises: 42c32e635113
Create Date: 2026-10-31 15:04:06.834830

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "738115d532c7"
down_revision: str | None = "42c32e635113"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_ENUMS = {
    "tipo_inventario": ("entrega", "recepcion"),
    "estado_inventario": ("programado", "realizado", "con_novedades", "firmado"),
    "tipo_solicitud": ("peticion", "queja", "reclamo", "sugerencia"),
    "solicitante": ("propietario", "inquilino"),
    "canal_solicitud": ("whatsapp", "llamada", "correo", "oficina"),
    "prioridad_admin": ("normal", "urgente"),
    "estado_solicitud": ("abierta", "en_tramite", "respondida", "cerrada"),
    "estado_ambiente": ("bueno", "regular", "malo"),
    "categoria_reparacion": (
        "plomeria",
        "electrico",
        "humedad",
        "cerrajeria",
        "pintura",
        "electrodomesticos",
        "otro",
    ),
    "estado_reparacion": ("recibida", "cotizada", "aprobada", "en_ejecucion", "terminada"),
    "paga_reparacion": ("por_definir", "propietario", "inquilino", "empresa", "aseguradora"),
}


def upgrade() -> None:
    bind = op.get_bind()
    for name, values in NEW_ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)
    op.create_table(
        "inventarios",
        sa.Column("numero", sa.Integer(), sa.Identity(always=False, start=19), nullable=False),
        sa.Column("inmueble_id", sa.Uuid(), nullable=False),
        sa.Column(
            "tipo", postgresql.ENUM(name="tipo_inventario", create_type=False), nullable=False
        ),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("referencia", sa.String(length=300), nullable=False),
        sa.Column("responsable_id", sa.Uuid(), nullable=True),
        sa.Column(
            "estado",
            postgresql.ENUM(name="estado_inventario", create_type=False),
            server_default="programado",
            nullable=False,
        ),
        sa.Column("firmado_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_inventarios_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["inmueble_id"],
            ["inmuebles.id"],
            name=op.f("fk_inventarios_inmueble_id_inmuebles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["responsable_id"],
            ["users.id"],
            name=op.f("fk_inventarios_responsable_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventarios")),
        sa.UniqueConstraint("numero", name=op.f("uq_inventarios_numero")),
    )
    op.create_index(op.f("ix_inventarios_estado"), "inventarios", ["estado"], unique=False)
    op.create_index(op.f("ix_inventarios_fecha"), "inventarios", ["fecha"], unique=False)
    op.create_index(
        op.f("ix_inventarios_inmueble_id"), "inventarios", ["inmueble_id"], unique=False
    )
    op.create_index(
        op.f("ix_inventarios_responsable_id"), "inventarios", ["responsable_id"], unique=False
    )
    op.create_table(
        "solicitudes",
        sa.Column("numero", sa.Integer(), sa.Identity(always=False, start=12), nullable=False),
        sa.Column("inmueble_id", sa.Uuid(), nullable=False),
        sa.Column(
            "tipo", postgresql.ENUM(name="tipo_solicitud", create_type=False), nullable=False
        ),
        sa.Column("de", postgresql.ENUM(name="solicitante", create_type=False), nullable=False),
        sa.Column("nombre", sa.String(length=200), nullable=True),
        sa.Column(
            "canal", postgresql.ENUM(name="canal_solicitud", create_type=False), nullable=False
        ),
        sa.Column("descripcion", sa.String(length=1000), nullable=False),
        sa.Column(
            "prioridad",
            postgresql.ENUM(name="prioridad_admin", create_type=False),
            server_default="normal",
            nullable=False,
        ),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column(
            "estado",
            postgresql.ENUM(name="estado_solicitud", create_type=False),
            server_default="abierta",
            nullable=False,
        ),
        sa.Column("responsable_id", sa.Uuid(), nullable=True),
        sa.Column("respuesta", sa.Text(), nullable=True),
        sa.Column("fecha_respuesta", sa.Date(), nullable=True),
        sa.Column("respondida_por_id", sa.Uuid(), nullable=True),
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
            name=op.f("fk_solicitudes_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["inmueble_id"],
            ["inmuebles.id"],
            name=op.f("fk_solicitudes_inmueble_id_inmuebles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["respondida_por_id"],
            ["users.id"],
            name=op.f("fk_solicitudes_respondida_por_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["responsable_id"],
            ["users.id"],
            name=op.f("fk_solicitudes_responsable_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_solicitudes")),
        sa.UniqueConstraint("numero", name=op.f("uq_solicitudes_numero")),
    )
    op.create_index(op.f("ix_solicitudes_estado"), "solicitudes", ["estado"], unique=False)
    op.create_index(op.f("ix_solicitudes_fecha"), "solicitudes", ["fecha"], unique=False)
    op.create_index(
        op.f("ix_solicitudes_inmueble_id"), "solicitudes", ["inmueble_id"], unique=False
    )
    op.create_index(
        op.f("ix_solicitudes_responsable_id"), "solicitudes", ["responsable_id"], unique=False
    )
    op.create_table(
        "inventario_ambientes",
        sa.Column("inventario_id", sa.Uuid(), nullable=False),
        sa.Column("orden", sa.SmallInteger(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column(
            "estado", postgresql.ENUM(name="estado_ambiente", create_type=False), nullable=True
        ),
        sa.Column("observacion", sa.String(length=500), nullable=True),
        sa.Column("fotos", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["inventario_id"],
            ["inventarios.id"],
            name=op.f("fk_inventario_ambientes_inventario_id_inventarios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventario_ambientes")),
    )
    op.create_index(
        op.f("ix_inventario_ambientes_inventario_id"),
        "inventario_ambientes",
        ["inventario_id"],
        unique=False,
    )
    op.create_table(
        "reparaciones",
        sa.Column("numero", sa.Integer(), sa.Identity(always=False, start=29), nullable=False),
        sa.Column("inmueble_id", sa.Uuid(), nullable=False),
        sa.Column("titulo", sa.String(length=500), nullable=False),
        sa.Column(
            "categoria",
            postgresql.ENUM(name="categoria_reparacion", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "prioridad",
            postgresql.ENUM(name="prioridad_admin", create_type=False),
            server_default="normal",
            nullable=False,
        ),
        sa.Column("solicitante", sa.String(length=200), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column(
            "estado",
            postgresql.ENUM(name="estado_reparacion", create_type=False),
            server_default="recibida",
            nullable=False,
        ),
        sa.Column("proveedor", sa.String(length=200), nullable=True),
        sa.Column("valor", sa.BigInteger(), nullable=True),
        sa.Column(
            "paga",
            postgresql.ENUM(name="paga_reparacion", create_type=False),
            server_default="por_definir",
            nullable=False,
        ),
        sa.Column("fecha_fin", sa.Date(), nullable=True),
        sa.Column("responsable_id", sa.Uuid(), nullable=True),
        sa.Column("inventario_id", sa.Uuid(), nullable=True),
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
            name=op.f("fk_reparaciones_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["inmueble_id"],
            ["inmuebles.id"],
            name=op.f("fk_reparaciones_inmueble_id_inmuebles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["inventario_id"],
            ["inventarios.id"],
            name=op.f("fk_reparaciones_inventario_id_inventarios"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["responsable_id"],
            ["users.id"],
            name=op.f("fk_reparaciones_responsable_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reparaciones")),
        sa.UniqueConstraint("inventario_id", name=op.f("uq_reparaciones_inventario_id")),
        sa.UniqueConstraint("numero", name=op.f("uq_reparaciones_numero")),
    )
    op.create_index(op.f("ix_reparaciones_estado"), "reparaciones", ["estado"], unique=False)
    op.create_index(op.f("ix_reparaciones_fecha"), "reparaciones", ["fecha"], unique=False)
    op.create_index(
        op.f("ix_reparaciones_inmueble_id"), "reparaciones", ["inmueble_id"], unique=False
    )
    op.create_index(
        op.f("ix_reparaciones_responsable_id"), "reparaciones", ["responsable_id"], unique=False
    )
    op.create_table(
        "admin_eventos",
        sa.Column("inventario_id", sa.Uuid(), nullable=True),
        sa.Column("reparacion_id", sa.Uuid(), nullable=True),
        sa.Column("solicitud_id", sa.Uuid(), nullable=True),
        sa.Column("titulo", sa.String(length=300), nullable=False),
        sa.Column("detalle", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "num_nonnulls(inventario_id, reparacion_id, solicitud_id) = 1",
            name=op.f("ck_admin_eventos_un_registro"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_admin_eventos_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["inventario_id"],
            ["inventarios.id"],
            name=op.f("fk_admin_eventos_inventario_id_inventarios"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reparacion_id"],
            ["reparaciones.id"],
            name=op.f("fk_admin_eventos_reparacion_id_reparaciones"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["solicitud_id"],
            ["solicitudes.id"],
            name=op.f("fk_admin_eventos_solicitud_id_solicitudes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_eventos")),
    )
    op.create_index(
        op.f("ix_admin_eventos_inventario_id"), "admin_eventos", ["inventario_id"], unique=False
    )
    op.create_index(
        op.f("ix_admin_eventos_reparacion_id"), "admin_eventos", ["reparacion_id"], unique=False
    )
    op.create_index(
        op.f("ix_admin_eventos_solicitud_id"), "admin_eventos", ["solicitud_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_admin_eventos_solicitud_id"), table_name="admin_eventos")
    op.drop_index(op.f("ix_admin_eventos_reparacion_id"), table_name="admin_eventos")
    op.drop_index(op.f("ix_admin_eventos_inventario_id"), table_name="admin_eventos")
    op.drop_table("admin_eventos")
    op.drop_index(op.f("ix_reparaciones_responsable_id"), table_name="reparaciones")
    op.drop_index(op.f("ix_reparaciones_inmueble_id"), table_name="reparaciones")
    op.drop_index(op.f("ix_reparaciones_fecha"), table_name="reparaciones")
    op.drop_index(op.f("ix_reparaciones_estado"), table_name="reparaciones")
    op.drop_table("reparaciones")
    op.drop_index(op.f("ix_inventario_ambientes_inventario_id"), table_name="inventario_ambientes")
    op.drop_table("inventario_ambientes")
    op.drop_index(op.f("ix_solicitudes_responsable_id"), table_name="solicitudes")
    op.drop_index(op.f("ix_solicitudes_inmueble_id"), table_name="solicitudes")
    op.drop_index(op.f("ix_solicitudes_fecha"), table_name="solicitudes")
    op.drop_index(op.f("ix_solicitudes_estado"), table_name="solicitudes")
    op.drop_table("solicitudes")
    op.drop_index(op.f("ix_inventarios_responsable_id"), table_name="inventarios")
    op.drop_index(op.f("ix_inventarios_inmueble_id"), table_name="inventarios")
    op.drop_index(op.f("ix_inventarios_fecha"), table_name="inventarios")
    op.drop_index(op.f("ix_inventarios_estado"), table_name="inventarios")
    op.drop_table("inventarios")
    bind = op.get_bind()
    for name in NEW_ENUMS:
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
