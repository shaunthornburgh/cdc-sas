"""novedades

Revision ID: 191ea5bc3ba3
Revises: 738115d532c7
Create Date: 2026-10-31 19:40:16.201542

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "191ea5bc3ba3"
down_revision: str | None = "738115d532c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_ENUMS = {
    "tipo_novedad": ("incapacidad", "permiso_no_remunerado", "permiso_remunerado"),
    "estado_novedad": ("registrada", "anulada"),
}


def upgrade() -> None:
    bind = op.get_bind()
    for name, values in NEW_ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)
    op.create_table(
        "novedades",
        sa.Column("numero", sa.Integer(), sa.Identity(always=False, start=1), nullable=False),
        sa.Column("empleado_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", postgresql.ENUM(name="tipo_novedad", create_type=False), nullable=False),
        sa.Column("desde", sa.Date(), nullable=False),
        sa.Column("hasta", sa.Date(), nullable=False),
        sa.Column("observacion", sa.String(length=500), nullable=True),
        sa.Column("soportes", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column(
            "estado",
            postgresql.ENUM(name="estado_novedad", create_type=False),
            server_default="registrada",
            nullable=False,
        ),
        sa.Column("registrada_por_id", sa.Uuid(), nullable=True),
        sa.Column("anulada_por_id", sa.Uuid(), nullable=True),
        sa.Column("anulada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo_anulacion", sa.String(length=300), nullable=True),
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
        sa.CheckConstraint("hasta >= desde", name=op.f("ck_novedades_fechas")),
        sa.ForeignKeyConstraint(
            ["anulada_por_id"],
            ["users.id"],
            name=op.f("fk_novedades_anulada_por_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["empleado_id"],
            ["users.id"],
            name=op.f("fk_novedades_empleado_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["registrada_por_id"],
            ["users.id"],
            name=op.f("fk_novedades_registrada_por_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_novedades")),
        sa.UniqueConstraint("numero", name=op.f("uq_novedades_numero")),
    )
    op.create_index(op.f("ix_novedades_desde"), "novedades", ["desde"], unique=False)
    op.create_index(op.f("ix_novedades_empleado_id"), "novedades", ["empleado_id"], unique=False)
    op.create_index(op.f("ix_novedades_estado"), "novedades", ["estado"], unique=False)
    op.create_index(op.f("ix_novedades_hasta"), "novedades", ["hasta"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_novedades_hasta"), table_name="novedades")
    op.drop_index(op.f("ix_novedades_estado"), table_name="novedades")
    op.drop_index(op.f("ix_novedades_empleado_id"), table_name="novedades")
    op.drop_index(op.f("ix_novedades_desde"), table_name="novedades")
    op.drop_table("novedades")
    bind = op.get_bind()
    for name in NEW_ENUMS:
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
