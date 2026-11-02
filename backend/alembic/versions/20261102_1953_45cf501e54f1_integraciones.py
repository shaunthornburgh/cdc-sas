"""integraciones

Revision ID: 45cf501e54f1
Revises: 2fa8225d7dd1
Create Date: 2026-11-02 19:53:28.750916

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "45cf501e54f1"
down_revision: str | None = "2fa8225d7dd1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integraciones",
        sa.Column("clave", sa.String(length=40), nullable=False),
        sa.Column("nombre", sa.String(length=80), nullable=False),
        sa.Column("grupo", sa.String(length=10), nullable=False),
        sa.Column("fuente", postgresql.ENUM(name="fuente_lead", create_type=False), nullable=True),
        sa.Column("orden", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("estado", sa.String(length=15), server_default="sin_conectar", nullable=False),
        sa.Column("como", sa.String(length=15), server_default="por_confirmar", nullable=False),
        sa.Column("costo_mensual", sa.BigInteger(), nullable=True),
        sa.Column(
            "datos", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "secretos", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("avisar_falla", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("conectado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("prueba_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("prueba_txt", sa.String(length=300), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["creado_por_id"],
            ["users.id"],
            name=op.f("fk_integraciones_creado_por_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integraciones")),
        sa.UniqueConstraint("clave", name=op.f("uq_integraciones_clave")),
        sa.UniqueConstraint("fuente", name=op.f("uq_integraciones_fuente")),
    )
    op.create_table(
        "integracion_eventos",
        sa.Column("integracion_id", sa.Uuid(), nullable=False),
        sa.Column("accion", sa.String(length=200), nullable=False),
        sa.Column("antes", sa.String(length=300), nullable=True),
        sa.Column("despues", sa.String(length=300), nullable=True),
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
            name=op.f("fk_integracion_eventos_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["integracion_id"],
            ["integraciones.id"],
            name=op.f("fk_integracion_eventos_integracion_id_integraciones"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integracion_eventos")),
    )
    op.create_index(
        op.f("ix_integracion_eventos_created_at"),
        "integracion_eventos",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_integracion_eventos_integracion_id"),
        "integracion_eventos",
        ["integracion_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_integracion_eventos_integracion_id"), table_name="integracion_eventos")
    op.drop_index(op.f("ix_integracion_eventos_created_at"), table_name="integracion_eventos")
    op.drop_table("integracion_eventos")
    op.drop_table("integraciones")
