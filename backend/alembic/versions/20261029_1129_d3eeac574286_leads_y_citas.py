"""leads y citas

Revision ID: d3eeac574286
Revises: 77dec08323d2
Create Date: 2026-10-29 11:29:16.297374

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d3eeac574286"
down_revision: str | None = "77dec08323d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("numero", sa.Integer(), sa.Identity(always=False, start=1101), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column(
            "fuente",
            sa.Enum(
                "ciencuadras",
                "espacio_urbano",
                "proppi",
                "finca_raiz",
                "metrocuadrado",
                "facebook",
                "instagram",
                "tiktok",
                "otro",
                name="fuente_lead",
            ),
            nullable=False,
        ),
        sa.Column("fuente_detalle", sa.String(length=200), nullable=True),
        sa.Column("negocio", sa.Enum("arriendo", "venta", name="tipo_negocio"), nullable=True),
        sa.Column("busca", sa.String(length=200), nullable=True),
        sa.Column("presupuesto", sa.String(length=100), nullable=True),
        sa.Column("zona", sa.String(length=200), nullable=True),
        sa.Column("para_cuando", sa.String(length=100), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column(
            "etapa",
            sa.Enum(
                "nuevo",
                "en_gestion",
                "seguimiento",
                "cita_programada",
                "ganado",
                "perdido",
                name="etapa_lead",
            ),
            server_default="nuevo",
            nullable=False,
        ),
        sa.Column(
            "motivo_perdida",
            sa.Enum(
                "no_contesta",
                "numero_equivocado",
                "no_interesado",
                "compro_con_otro",
                "presupuesto",
                name="motivo_perdida",
            ),
            nullable=True,
        ),
        sa.Column("perdida_descuenta", sa.Boolean(), nullable=True),
        sa.Column("cerrado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_to_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
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
            ["assigned_to_id"],
            ["users.id"],
            name=op.f("fk_leads_assigned_to_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_leads_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leads")),
        sa.UniqueConstraint("numero", name=op.f("uq_leads_numero")),
    )
    op.create_index(op.f("ix_leads_assigned_to_id"), "leads", ["assigned_to_id"], unique=False)
    op.create_index("ix_leads_etapa_assigned", "leads", ["etapa", "assigned_to_id"], unique=False)
    op.create_table(
        "citas",
        sa.Column("numero", sa.Integer(), sa.Identity(always=False, start=401), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "visita_arriendo",
                "visita_venta",
                "captacion",
                "visita_control",
                "inventario",
                "reunion_asesoria",
                name="tipo_cita",
            ),
            nullable=False,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("asesor_id", sa.Uuid(), nullable=True),
        sa.Column(
            "estado",
            sa.Enum(
                "pendiente", "aceptada", "rechazada", "realizada", "cancelada", name="estado_cita"
            ),
            server_default="pendiente",
            nullable=False,
        ),
        sa.Column("inmueble", sa.String(length=200), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("motivo", sa.Text(), nullable=True),
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
            ["asesor_id"], ["users.id"], name=op.f("fk_citas_asesor_id_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_citas_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["leads.id"], name=op.f("fk_citas_lead_id_leads"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_citas")),
        sa.UniqueConstraint("numero", name=op.f("uq_citas_numero")),
    )
    op.create_index(op.f("ix_citas_asesor_id"), "citas", ["asesor_id"], unique=False)
    op.create_index(op.f("ix_citas_lead_id"), "citas", ["lead_id"], unique=False)
    op.create_index(op.f("ix_citas_scheduled_at"), "citas", ["scheduled_at"], unique=False)
    op.create_table(
        "lead_seguimientos",
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column(
            "accion",
            sa.Enum(
                "llamar",
                "enviar_opciones",
                "enviar_informacion",
                "confirmar_cita",
                "seguimiento_propuesta",
                "volver_a_contactar",
                name="accion_seguimiento",
            ),
            nullable=False,
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("nota", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("done_by_id", sa.Uuid(), nullable=True),
        sa.Column("resultado", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_lead_seguimientos_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["done_by_id"],
            ["users.id"],
            name=op.f("fk_lead_seguimientos_done_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_lead_seguimientos_lead_id_leads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_seguimientos")),
    )
    op.create_index(
        op.f("ix_lead_seguimientos_due_at"), "lead_seguimientos", ["due_at"], unique=False
    )
    op.create_index(
        op.f("ix_lead_seguimientos_lead_id"), "lead_seguimientos", ["lead_id"], unique=False
    )
    op.create_table(
        "lead_eventos",
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "recibido",
                "seguir",
                "asignacion",
                "llamada",
                "mensaje",
                "opciones",
                "seguimiento",
                "observacion",
                "cita",
                "etapa",
                "datos",
                name="tipo_evento_lead",
            ),
            nullable=False,
        ),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("detalle", sa.Text(), nullable=True),
        sa.Column(
            "datos", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("cita_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["cita_id"],
            ["citas.id"],
            name=op.f("fk_lead_eventos_cita_id_citas"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_lead_eventos_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_lead_eventos_lead_id_leads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_eventos")),
    )
    op.create_index(op.f("ix_lead_eventos_cita_id"), "lead_eventos", ["cita_id"], unique=False)
    op.create_index(op.f("ix_lead_eventos_lead_id"), "lead_eventos", ["lead_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_lead_eventos_lead_id"), table_name="lead_eventos")
    op.drop_index(op.f("ix_lead_eventos_cita_id"), table_name="lead_eventos")
    op.drop_table("lead_eventos")
    op.drop_index(op.f("ix_lead_seguimientos_lead_id"), table_name="lead_seguimientos")
    op.drop_index(op.f("ix_lead_seguimientos_due_at"), table_name="lead_seguimientos")
    op.drop_table("lead_seguimientos")
    op.drop_index(op.f("ix_citas_scheduled_at"), table_name="citas")
    op.drop_index(op.f("ix_citas_lead_id"), table_name="citas")
    op.drop_index(op.f("ix_citas_asesor_id"), table_name="citas")
    op.drop_table("citas")
    op.drop_index("ix_leads_etapa_assigned", table_name="leads")
    op.drop_index(op.f("ix_leads_assigned_to_id"), table_name="leads")
    op.drop_table("leads")
    for name in (
        "tipo_evento_lead",
        "accion_seguimiento",
        "estado_cita",
        "tipo_cita",
        "motivo_perdida",
        "etapa_lead",
        "tipo_negocio",
        "fuente_lead",
    ):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
