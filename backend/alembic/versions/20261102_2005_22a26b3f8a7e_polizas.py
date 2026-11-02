"""polizas

Revision ID: 22a26b3f8a7e
Revises: 45cf501e54f1
Create Date: 2026-11-02 20:05:49.360339

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "22a26b3f8a7e"
down_revision: str | None = "45cf501e54f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "aseguradoras",
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("nit", sa.String(length=40), nullable=True),
        sa.Column("contacto", sa.String(length=120), nullable=True),
        sa.Column("telefono", sa.String(length=200), nullable=True),
        sa.Column("activa", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("dias_max", sa.SmallInteger(), server_default="60", nullable=False),
        sa.Column("aviso_dias", sa.SmallInteger(), server_default="10", nullable=False),
        sa.Column("ejemplo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("eliminada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eliminada_por_id", sa.Uuid(), nullable=True),
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
            name=op.f("fk_aseguradoras_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["eliminada_por_id"],
            ["users.id"],
            name=op.f("fk_aseguradoras_eliminada_por_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_aseguradoras")),
    )
    op.create_table(
        "poliza_tipos",
        sa.Column("aseguradora_id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("precio_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("costo_estudio", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("dias_respuesta", sa.SmallInteger(), nullable=True),
        sa.Column(
            "coberturas",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
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
            ["aseguradora_id"],
            ["aseguradoras.id"],
            name=op.f("fk_poliza_tipos_aseguradora_id_aseguradoras"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_poliza_tipos_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_poliza_tipos")),
    )
    op.create_index(
        op.f("ix_poliza_tipos_aseguradora_id"), "poliza_tipos", ["aseguradora_id"], unique=False
    )
    op.create_table(
        "polizas",
        sa.Column("cierre_id", sa.Uuid(), nullable=True),
        sa.Column("inmueble_id", sa.Uuid(), nullable=True),
        sa.Column("descripcion", sa.String(length=200), nullable=True),
        sa.Column("tipo_id", sa.Uuid(), nullable=False),
        sa.Column("aseguradora_id", sa.Uuid(), nullable=False),
        sa.Column("canon", sa.BigInteger(), nullable=False),
        sa.Column("estado", sa.String(length=15), nullable=False),
        sa.Column("radicado", sa.String(length=80), nullable=True),
        sa.Column("estudio_fecha", sa.Date(), nullable=False),
        sa.Column("decision_fecha", sa.Date(), nullable=True),
        sa.Column("motivo_negada", sa.String(length=300), nullable=True),
        sa.Column("estudios", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("retomada_motivo", sa.String(length=300), nullable=True),
        sa.Column("recuperada", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("firma_fecha", sa.Date(), nullable=True),
        sa.Column("activada_fecha", sa.Date(), nullable=True),
        sa.Column("numero_poliza", sa.String(length=80), nullable=True),
        sa.Column("soporte", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("seguro_inmueble", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("terminada_fecha", sa.Date(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("eliminada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eliminada_por_id", sa.Uuid(), nullable=True),
        sa.Column("eliminada_motivo", sa.String(length=300), nullable=True),
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
            ["aseguradora_id"],
            ["aseguradoras.id"],
            name=op.f("fk_polizas_aseguradora_id_aseguradoras"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cierre_id"],
            ["cierres.id"],
            name=op.f("fk_polizas_cierre_id_cierres"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_polizas_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["eliminada_por_id"],
            ["users.id"],
            name=op.f("fk_polizas_eliminada_por_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["inmueble_id"],
            ["inmuebles.id"],
            name=op.f("fk_polizas_inmueble_id_inmuebles"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tipo_id"],
            ["poliza_tipos.id"],
            name=op.f("fk_polizas_tipo_id_poliza_tipos"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_polizas")),
    )
    op.create_index(op.f("ix_polizas_activada_fecha"), "polizas", ["activada_fecha"], unique=False)
    op.create_index(op.f("ix_polizas_aseguradora_id"), "polizas", ["aseguradora_id"], unique=False)
    op.create_index(op.f("ix_polizas_cierre_id"), "polizas", ["cierre_id"], unique=False)
    op.create_index(op.f("ix_polizas_estado"), "polizas", ["estado"], unique=False)
    op.create_index(op.f("ix_polizas_inmueble_id"), "polizas", ["inmueble_id"], unique=False)
    op.create_table(
        "poliza_eventos",
        sa.Column("poliza_id", sa.Uuid(), nullable=True),
        sa.Column("aseguradora_id", sa.Uuid(), nullable=True),
        sa.Column("registro", sa.String(length=200), nullable=False),
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
            name=op.f("fk_poliza_eventos_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["aseguradora_id"],
            ["aseguradoras.id"],
            name=op.f("fk_poliza_eventos_aseguradora_id_aseguradoras"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["poliza_id"],
            ["polizas.id"],
            name=op.f("fk_poliza_eventos_poliza_id_polizas"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_poliza_eventos")),
    )
    op.create_index(
        op.f("ix_poliza_eventos_aseguradora_id"), "poliza_eventos", ["aseguradora_id"], unique=False
    )
    op.create_index(
        op.f("ix_poliza_eventos_created_at"), "poliza_eventos", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_poliza_eventos_poliza_id"), "poliza_eventos", ["poliza_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_poliza_eventos_poliza_id"), table_name="poliza_eventos")
    op.drop_index(op.f("ix_poliza_eventos_created_at"), table_name="poliza_eventos")
    op.drop_index(op.f("ix_poliza_eventos_aseguradora_id"), table_name="poliza_eventos")
    op.drop_table("poliza_eventos")
    op.drop_index(op.f("ix_polizas_inmueble_id"), table_name="polizas")
    op.drop_index(op.f("ix_polizas_estado"), table_name="polizas")
    op.drop_index(op.f("ix_polizas_cierre_id"), table_name="polizas")
    op.drop_index(op.f("ix_polizas_aseguradora_id"), table_name="polizas")
    op.drop_index(op.f("ix_polizas_activada_fecha"), table_name="polizas")
    op.drop_table("polizas")
    op.drop_index(op.f("ix_poliza_tipos_aseguradora_id"), table_name="poliza_tipos")
    op.drop_table("poliza_tipos")
    op.drop_table("aseguradoras")
