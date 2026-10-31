"""inmuebles

Revision ID: 42c32e635113
Revises: 17b1cb0ef432
Create Date: 2026-10-29 19:04:27.803793

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "42c32e635113"
down_revision: str | None = "17b1cb0ef432"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_ENUMS = {
    "estado_inmueble": (
        "disponible",
        "separado",
        "arrendado",
        "vendido",
        "retirado",
    ),
}


def upgrade() -> None:
    bind = op.get_bind()
    for name, values in NEW_ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)
    op.create_table(
        "inmuebles",
        sa.Column("codigo", sa.String(length=40), nullable=False),
        sa.Column(
            "negocio", postgresql.ENUM(name="tipo_negocio", create_type=False), nullable=False
        ),
        sa.Column(
            "tipo_inmueble", postgresql.ENUM(name="tipo_inmueble", create_type=False), nullable=True
        ),
        sa.Column("direccion", sa.String(length=300), nullable=False),
        sa.Column("zona", sa.String(length=60), nullable=True),
        sa.Column("barrio", sa.String(length=120), nullable=True),
        sa.Column("municipio", sa.String(length=120), nullable=True),
        sa.Column("precio", sa.BigInteger(), nullable=True),
        sa.Column("administracion", sa.BigInteger(), nullable=True),
        sa.Column("area_m2", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("habitaciones", sa.SmallInteger(), nullable=True),
        sa.Column("banos", sa.SmallInteger(), nullable=True),
        sa.Column("parqueadero", sa.Boolean(), nullable=True),
        sa.Column("estrato", sa.SmallInteger(), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("propietario_nombre", sa.String(length=200), nullable=True),
        sa.Column("propietario_telefono", sa.String(length=40), nullable=True),
        sa.Column(
            "estado", postgresql.ENUM(name="estado_inmueble", create_type=False), nullable=False
        ),
        sa.Column(
            "estado_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("captacion_id", sa.Uuid(), nullable=True),
        sa.Column("captador_id", sa.Uuid(), nullable=True),
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
            ["captacion_id"],
            ["captaciones.id"],
            name=op.f("fk_inmuebles_captacion_id_captaciones"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["captador_id"],
            ["users.id"],
            name=op.f("fk_inmuebles_captador_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_inmuebles_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inmuebles")),
        sa.UniqueConstraint("captacion_id", name=op.f("uq_inmuebles_captacion_id")),
        sa.UniqueConstraint("codigo", name=op.f("uq_inmuebles_codigo")),
    )
    op.create_index(op.f("ix_inmuebles_captador_id"), "inmuebles", ["captador_id"], unique=False)
    op.create_index(op.f("ix_inmuebles_estado"), "inmuebles", ["estado"], unique=False)
    op.create_index(op.f("ix_inmuebles_negocio"), "inmuebles", ["negocio"], unique=False)
    op.create_index(op.f("ix_inmuebles_zona"), "inmuebles", ["zona"], unique=False)
    op.create_table(
        "inmueble_eventos",
        sa.Column("inmueble_id", sa.Uuid(), nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("detalle", sa.Text(), nullable=True),
        sa.Column(
            "datos", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
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
            name=op.f("fk_inmueble_eventos_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["inmueble_id"],
            ["inmuebles.id"],
            name=op.f("fk_inmueble_eventos_inmueble_id_inmuebles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inmueble_eventos")),
    )
    op.create_index(
        op.f("ix_inmueble_eventos_inmueble_id"), "inmueble_eventos", ["inmueble_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_inmueble_eventos_inmueble_id"), table_name="inmueble_eventos")
    op.drop_table("inmueble_eventos")
    op.drop_index(op.f("ix_inmuebles_zona"), table_name="inmuebles")
    op.drop_index(op.f("ix_inmuebles_negocio"), table_name="inmuebles")
    op.drop_index(op.f("ix_inmuebles_estado"), table_name="inmuebles")
    op.drop_index(op.f("ix_inmuebles_captador_id"), table_name="inmuebles")
    op.drop_table("inmuebles")
    bind = op.get_bind()
    for name in NEW_ENUMS:
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
