"""captaciones

Revision ID: ec9ca2b2c984
Revises: d3eeac574286
Create Date: 2026-10-29 12:04:41.487992

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "ec9ca2b2c984"
down_revision: str | None = "d3eeac574286"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "captaciones",
        sa.Column("numero", sa.Integer(), sa.Identity(always=False, start=201), nullable=False),
        sa.Column(
            "negocio", postgresql.ENUM(name="tipo_negocio", create_type=False), nullable=False
        ),
        sa.Column("codigo_inmueble", sa.String(length=40), nullable=False),
        sa.Column("direccion", sa.String(length=300), nullable=False),
        sa.Column("modo", sa.Enum("rapido", "completo", name="modo_captacion"), nullable=False),
        sa.Column(
            "tipo_inmueble",
            sa.Enum(
                "apartamento", "casa", "local", "oficina", "lote", "bodega", name="tipo_inmueble"
            ),
            nullable=True,
        ),
        sa.Column("barrio", sa.String(length=120), nullable=True),
        sa.Column("municipio", sa.String(length=120), nullable=True),
        sa.Column("precio", sa.BigInteger(), nullable=True),
        sa.Column("area_m2", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("habitaciones", sa.SmallInteger(), nullable=True),
        sa.Column("banos", sa.SmallInteger(), nullable=True),
        sa.Column("parqueadero", sa.Boolean(), nullable=True),
        sa.Column("propietario_nombre", sa.String(length=200), nullable=True),
        sa.Column("propietario_telefono", sa.String(length=40), nullable=True),
        sa.Column("observaciones", sa.Text(), nullable=True),
        sa.Column(
            "estado",
            sa.Enum("por_verificar", "aprobada", "rechazada", name="estado_captacion"),
            server_default="por_verificar",
            nullable=False,
        ),
        sa.Column(
            "enviada_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reenvios", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column(
            "motivo_rechazo",
            sa.Enum("codigo_inexistente", "codigo_no_corresponde", name="motivo_rechazo_captacion"),
            nullable=True,
        ),
        sa.Column("observacion_rechazo", sa.Text(), nullable=True),
        sa.Column("verificado_por_id", sa.Uuid(), nullable=True),
        sa.Column("verificado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publicada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gps_lat", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("gps_lng", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("gps_precision_m", sa.Integer(), nullable=True),
        sa.Column("gps_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("asesor_id", sa.Uuid(), nullable=False),
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
            ["asesor_id"],
            ["users.id"],
            name=op.f("fk_captaciones_asesor_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_captaciones_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["verificado_por_id"],
            ["users.id"],
            name=op.f("fk_captaciones_verificado_por_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_captaciones")),
        sa.UniqueConstraint("numero", name=op.f("uq_captaciones_numero")),
    )
    op.create_index(op.f("ix_captaciones_asesor_id"), "captaciones", ["asesor_id"], unique=False)
    op.create_index(
        op.f("ix_captaciones_codigo_inmueble"), "captaciones", ["codigo_inmueble"], unique=False
    )
    op.create_index(op.f("ix_captaciones_enviada_at"), "captaciones", ["enviada_at"], unique=False)
    op.create_index(
        "ix_captaciones_estado_asesor", "captaciones", ["estado", "asesor_id"], unique=False
    )
    op.create_index(
        "uq_captaciones_codigo_vigente",
        "captaciones",
        ["codigo_inmueble"],
        unique=True,
        postgresql_where=sa.text("estado <> 'rechazada'"),
    )
    op.create_table(
        "captacion_eventos",
        sa.Column("captacion_id", sa.Uuid(), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "enviada",
                "editada",
                "aprobada",
                "rechazada",
                "reenviada",
                "publicada",
                "reasignada",
                name="tipo_evento_captacion",
            ),
            nullable=False,
        ),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("detalle", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["captacion_id"],
            ["captaciones.id"],
            name=op.f("fk_captacion_eventos_captacion_id_captaciones"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_captacion_eventos_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_captacion_eventos")),
    )
    op.create_index(
        op.f("ix_captacion_eventos_captacion_id"),
        "captacion_eventos",
        ["captacion_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_captacion_eventos_captacion_id"), table_name="captacion_eventos")
    op.drop_table("captacion_eventos")
    op.drop_index(
        "uq_captaciones_codigo_vigente",
        table_name="captaciones",
        postgresql_where=sa.text("estado <> 'rechazada'"),
    )
    op.drop_index("ix_captaciones_estado_asesor", table_name="captaciones")
    op.drop_index(op.f("ix_captaciones_enviada_at"), table_name="captaciones")
    op.drop_index(op.f("ix_captaciones_codigo_inmueble"), table_name="captaciones")
    op.drop_index(op.f("ix_captaciones_asesor_id"), table_name="captaciones")
    op.drop_table("captaciones")
    for name in (
        "tipo_evento_captacion",
        "motivo_rechazo_captacion",
        "estado_captacion",
        "tipo_inmueble",
        "modo_captacion",
    ):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
