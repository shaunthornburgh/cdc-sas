"""compensacion

Revision ID: 17b1cb0ef432
Revises: 9fa5848a092a
Create Date: 2026-10-29 18:43:02.676485

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "17b1cb0ef432"
down_revision: str | None = "9fa5848a092a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_ENUMS = {
    "tipo_pago": (
        "comision",
        "bono",
        "salario",
    ),
    "estado_pago": (
        "en_proceso",
        "pagado",
    ),
    "tipo_bono": (
        "rendimiento",
        "manual",
    ),
    "estado_compensacion": (
        "generada",
        "visto_bueno",
        "pendiente_pago",
        "pagada",
        "anulada",
    ),
    "estado_cierre": (
        "cerrado",
        "caido",
    ),
    "estado_salario": (
        "por_confirmar",
        "confirmado",
        "pagado",
    ),
    "tipo_comision": (
        "cerrador",
        "captador",
        "filtro",
        "grupal",
        "manual",
    ),
}


def upgrade() -> None:
    bind = op.get_bind()
    for name, values in NEW_ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)
    op.create_table(
        "compensacion_config",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column(
            "valores", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_compensacion_config_updated_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_compensacion_config")),
    )
    op.create_table(
        "compensacion_eventos",
        sa.Column("entidad", sa.String(length=20), nullable=False),
        sa.Column("entidad_id", sa.String(length=40), nullable=False),
        sa.Column("accion", sa.String(length=200), nullable=False),
        sa.Column(
            "antes", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "despues", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
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
            name=op.f("fk_compensacion_eventos_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_compensacion_eventos")),
    )
    op.create_index(
        "ix_compensacion_eventos_entidad",
        "compensacion_eventos",
        ["entidad", "entidad_id"],
        unique=False,
    )
    op.create_table(
        "pagos",
        sa.Column("beneficiario_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", postgresql.ENUM(name="tipo_pago", create_type=False), nullable=False),
        sa.Column("concepto", sa.String(length=300), nullable=False),
        sa.Column("valor", sa.BigInteger(), nullable=False),
        sa.Column("fecha_programada", sa.Date(), nullable=False),
        sa.Column("estado", postgresql.ENUM(name="estado_pago", create_type=False), nullable=False),
        sa.Column("pagado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registrado_por_id", sa.Uuid(), nullable=True),
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
            ["beneficiario_id"],
            ["users.id"],
            name=op.f("fk_pagos_beneficiario_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["registrado_por_id"],
            ["users.id"],
            name=op.f("fk_pagos_registrado_por_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pagos")),
    )
    op.create_index(op.f("ix_pagos_beneficiario_id"), "pagos", ["beneficiario_id"], unique=False)
    op.create_table(
        "salario_config",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("salario_mensual", sa.BigInteger(), nullable=False),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_salario_config_updated_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_salario_config_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_salario_config")),
    )
    op.create_table(
        "bonos",
        sa.Column("tipo", postgresql.ENUM(name="tipo_bono", create_type=False), nullable=False),
        sa.Column("rendimiento", sa.SmallInteger(), nullable=True),
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
        sa.Column("beneficiario_id", sa.Uuid(), nullable=False),
        sa.Column("concepto", sa.String(length=300), nullable=False),
        sa.Column("detalle", sa.Text(), nullable=True),
        sa.Column("valor", sa.BigInteger(), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
        sa.Column("periodo", sa.Date(), nullable=False),
        sa.Column(
            "estado", postgresql.ENUM(name="estado_compensacion", create_type=False), nullable=False
        ),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("pago_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["beneficiario_id"],
            ["users.id"],
            name=op.f("fk_bonos_beneficiario_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_bonos_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["pago_id"], ["pagos.id"], name=op.f("fk_bonos_pago_id_pagos"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bonos")),
    )
    op.create_index(op.f("ix_bonos_beneficiario_id"), "bonos", ["beneficiario_id"], unique=False)
    op.create_index(op.f("ix_bonos_periodo"), "bonos", ["periodo"], unique=False)
    op.create_index(
        "uq_bono_rendimiento_periodo",
        "bonos",
        ["beneficiario_id", "periodo"],
        unique=True,
        postgresql_where=sa.text("tipo = 'rendimiento'"),
    )
    op.create_table(
        "cierres",
        sa.Column("numero", sa.Integer(), sa.Identity(always=False, start=140), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column(
            "negocio", postgresql.ENUM(name="tipo_negocio", create_type=False), nullable=True
        ),
        sa.Column("cerrado_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cerrador_id", sa.Uuid(), nullable=True),
        sa.Column("filtro_id", sa.Uuid(), nullable=True),
        sa.Column("captador_id", sa.Uuid(), nullable=True),
        sa.Column("ganancia", sa.BigInteger(), nullable=True),
        sa.Column(
            "estado", postgresql.ENUM(name="estado_cierre", create_type=False), nullable=False
        ),
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
            ["captador_id"],
            ["users.id"],
            name=op.f("fk_cierres_captador_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["cerrador_id"],
            ["users.id"],
            name=op.f("fk_cierres_cerrador_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["filtro_id"],
            ["users.id"],
            name=op.f("fk_cierres_filtro_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["leads.id"], name=op.f("fk_cierres_lead_id_leads"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cierres")),
        sa.UniqueConstraint("lead_id", name=op.f("uq_cierres_lead_id")),
        sa.UniqueConstraint("numero", name=op.f("uq_cierres_numero")),
    )
    op.create_index(op.f("ix_cierres_cerrado_at"), "cierres", ["cerrado_at"], unique=False)
    op.create_table(
        "liquidaciones_salario",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("periodo", sa.Date(), nullable=False),
        sa.Column("corte", sa.SmallInteger(), nullable=False),
        sa.Column("salario_corte", sa.BigInteger(), nullable=False),
        sa.Column("descuento", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("novedades", sa.String(length=300), nullable=True),
        sa.Column(
            "estado", postgresql.ENUM(name="estado_salario", create_type=False), nullable=False
        ),
        sa.Column("pago_id", sa.Uuid(), nullable=True),
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
            ["pago_id"],
            ["pagos.id"],
            name=op.f("fk_liquidaciones_salario_pago_id_pagos"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_liquidaciones_salario_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_liquidaciones_salario")),
        sa.UniqueConstraint("user_id", "periodo", "corte", name="uq_liquidacion_corte"),
    )
    op.create_index(
        op.f("ix_liquidaciones_salario_user_id"), "liquidaciones_salario", ["user_id"], unique=False
    )
    op.create_table(
        "comisiones",
        sa.Column("tipo", postgresql.ENUM(name="tipo_comision", create_type=False), nullable=False),
        sa.Column("cierre_id", sa.Uuid(), nullable=True),
        sa.Column("base", sa.BigInteger(), nullable=True),
        sa.Column("porcentaje", sa.Numeric(precision=6, scale=3), nullable=True),
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
        sa.Column("beneficiario_id", sa.Uuid(), nullable=False),
        sa.Column("concepto", sa.String(length=300), nullable=False),
        sa.Column("detalle", sa.Text(), nullable=True),
        sa.Column("valor", sa.BigInteger(), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
        sa.Column("periodo", sa.Date(), nullable=False),
        sa.Column(
            "estado", postgresql.ENUM(name="estado_compensacion", create_type=False), nullable=False
        ),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("pago_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["beneficiario_id"],
            ["users.id"],
            name=op.f("fk_comisiones_beneficiario_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cierre_id"],
            ["cierres.id"],
            name=op.f("fk_comisiones_cierre_id_cierres"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_comisiones_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["pago_id"], ["pagos.id"], name=op.f("fk_comisiones_pago_id_pagos"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comisiones")),
    )
    op.create_index(
        op.f("ix_comisiones_beneficiario_id"), "comisiones", ["beneficiario_id"], unique=False
    )
    op.create_index(op.f("ix_comisiones_cierre_id"), "comisiones", ["cierre_id"], unique=False)
    op.create_index(op.f("ix_comisiones_periodo"), "comisiones", ["periodo"], unique=False)
    op.create_index(
        "uq_comision_cierre_tipo",
        "comisiones",
        ["cierre_id", "tipo"],
        unique=True,
        postgresql_where=sa.text("cierre_id IS NOT NULL AND tipo <> 'manual'"),
    )
    op.create_index(
        "uq_comision_grupal_periodo",
        "comisiones",
        ["beneficiario_id", "periodo"],
        unique=True,
        postgresql_where=sa.text("tipo = 'grupal'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_comision_grupal_periodo",
        table_name="comisiones",
        postgresql_where=sa.text("tipo = 'grupal'"),
    )
    op.drop_index(
        "uq_comision_cierre_tipo",
        table_name="comisiones",
        postgresql_where=sa.text("cierre_id IS NOT NULL AND tipo <> 'manual'"),
    )
    op.drop_index(op.f("ix_comisiones_periodo"), table_name="comisiones")
    op.drop_index(op.f("ix_comisiones_cierre_id"), table_name="comisiones")
    op.drop_index(op.f("ix_comisiones_beneficiario_id"), table_name="comisiones")
    op.drop_table("comisiones")
    op.drop_index(op.f("ix_liquidaciones_salario_user_id"), table_name="liquidaciones_salario")
    op.drop_table("liquidaciones_salario")
    op.drop_index(op.f("ix_cierres_cerrado_at"), table_name="cierres")
    op.drop_table("cierres")
    op.drop_index(
        "uq_bono_rendimiento_periodo",
        table_name="bonos",
        postgresql_where=sa.text("tipo = 'rendimiento'"),
    )
    op.drop_index(op.f("ix_bonos_periodo"), table_name="bonos")
    op.drop_index(op.f("ix_bonos_beneficiario_id"), table_name="bonos")
    op.drop_table("bonos")
    op.drop_table("salario_config")
    op.drop_index(op.f("ix_pagos_beneficiario_id"), table_name="pagos")
    op.drop_table("pagos")
    op.drop_index("ix_compensacion_eventos_entidad", table_name="compensacion_eventos")
    op.drop_table("compensacion_eventos")
    op.drop_table("compensacion_config")
    bind = op.get_bind()
    for name in NEW_ENUMS:
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
