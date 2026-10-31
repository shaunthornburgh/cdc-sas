"""pedidos

Revision ID: 9925218b240d
Revises: f74bfca293a5
Create Date: 2026-10-29 16:35:23.910233

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "9925218b240d"
down_revision: str | None = "f74bfca293a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pedidos",
        sa.Column("numero", sa.Integer(), sa.Identity(always=False, start=30), nullable=False),
        sa.Column("cliente_nombre", sa.String(length=200), nullable=False),
        sa.Column("cliente_telefono", sa.String(length=40), nullable=True),
        sa.Column("lead_id", sa.Uuid(), nullable=True),
        sa.Column(
            "negocio", postgresql.ENUM(name="tipo_negocio", create_type=False), nullable=False
        ),
        sa.Column(
            "tipo_inmueble",
            postgresql.ENUM(name="tipo_inmueble", create_type=False),
            nullable=False,
        ),
        sa.Column("zona", sa.String(length=80), nullable=False),
        sa.Column("presupuesto", sa.BigInteger(), nullable=False),
        sa.Column("observaciones", sa.Text(), nullable=True),
        sa.Column("fecha_limite", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "urgencia",
            sa.Enum("normal", "alta", "urgente", name="urgencia_pedido"),
            server_default="normal",
            nullable=False,
        ),
        sa.Column(
            "estado",
            sa.Enum("abierto", "atendido", "perdido", name="estado_pedido"),
            server_default="abierto",
            nullable=False,
        ),
        sa.Column("vencio", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "motivo_perdida",
            sa.Enum(
                "no_interesaron",
                "compro_con_otro",
                "presupuesto",
                "no_responde",
                "otro",
                name="motivo_perdida_pedido",
            ),
            nullable=True,
        ),
        sa.Column("cerrado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responsable_id", sa.Uuid(), nullable=False),
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
            name=op.f("fk_pedidos_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["leads.id"], name=op.f("fk_pedidos_lead_id_leads"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["responsable_id"],
            ["users.id"],
            name=op.f("fk_pedidos_responsable_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pedidos")),
        sa.UniqueConstraint("numero", name=op.f("uq_pedidos_numero")),
    )
    op.create_index(
        "ix_pedidos_estado_responsable", "pedidos", ["estado", "responsable_id"], unique=False
    )
    op.create_index(op.f("ix_pedidos_fecha_limite"), "pedidos", ["fecha_limite"], unique=False)
    op.create_index(op.f("ix_pedidos_lead_id"), "pedidos", ["lead_id"], unique=False)
    op.create_index(op.f("ix_pedidos_responsable_id"), "pedidos", ["responsable_id"], unique=False)
    op.create_table(
        "pedido_eventos",
        sa.Column("pedido_id", sa.Uuid(), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "creado",
                "actualizado",
                "extendido",
                "atendido",
                "perdido",
                "propuesta",
                "comentario",
                "reasignado",
                name="tipo_evento_pedido",
            ),
            nullable=False,
        ),
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
            name=op.f("fk_pedido_eventos_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["pedido_id"],
            ["pedidos.id"],
            name=op.f("fk_pedido_eventos_pedido_id_pedidos"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pedido_eventos")),
    )
    op.create_index(
        op.f("ix_pedido_eventos_pedido_id"), "pedido_eventos", ["pedido_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_pedido_eventos_pedido_id"), table_name="pedido_eventos")
    op.drop_table("pedido_eventos")
    op.drop_index(op.f("ix_pedidos_responsable_id"), table_name="pedidos")
    op.drop_index(op.f("ix_pedidos_lead_id"), table_name="pedidos")
    op.drop_index(op.f("ix_pedidos_fecha_limite"), table_name="pedidos")
    op.drop_index("ix_pedidos_estado_responsable", table_name="pedidos")
    op.drop_table("pedidos")
    for name in ("tipo_evento_pedido", "motivo_perdida_pedido", "estado_pedido", "urgencia_pedido"):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
