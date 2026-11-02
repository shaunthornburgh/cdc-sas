"""agenda_completa

Revision ID: 9234372d70ed
Revises: 7035a992a9db
Create Date: 2026-11-01 21:11:20.993743

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9234372d70ed"
down_revision: str | None = "7035a992a9db"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agenda_items", sa.Column("creado_por_id", sa.Uuid(), nullable=True))
    op.add_column("agenda_items", sa.Column("motivo", sa.String(length=500), nullable=True))
    op.add_column(
        "agenda_items", sa.Column("respondida_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "agenda_items", sa.Column("eliminado_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("agenda_items", sa.Column("eliminado_por_id", sa.Uuid(), nullable=True))
    op.alter_column(
        "agenda_items",
        "estado",
        existing_type=sa.VARCHAR(length=10),
        type_=sa.String(length=12),
        existing_nullable=False,
    )
    op.create_foreign_key(
        op.f("fk_agenda_items_creado_por_id_users"),
        "agenda_items",
        "users",
        ["creado_por_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_agenda_items_eliminado_por_id_users"),
        "agenda_items",
        "users",
        ["eliminado_por_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Until now every item was added by its owner.
    op.execute("UPDATE agenda_items SET creado_por_id = user_id WHERE creado_por_id IS NULL")


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_agenda_items_eliminado_por_id_users"), "agenda_items", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_agenda_items_creado_por_id_users"), "agenda_items", type_="foreignkey"
    )
    op.alter_column(
        "agenda_items",
        "estado",
        existing_type=sa.String(length=12),
        type_=sa.VARCHAR(length=10),
        existing_nullable=False,
    )
    op.execute("DELETE FROM agenda_items WHERE eliminado_at IS NOT NULL")
    op.execute(
        "UPDATE agenda_items SET estado = 'pendiente' WHERE estado IN ('rechazada', 'justificada')"
    )
    op.drop_column("agenda_items", "eliminado_por_id")
    op.drop_column("agenda_items", "eliminado_at")
    op.drop_column("agenda_items", "respondida_at")
    op.drop_column("agenda_items", "motivo")
    op.drop_column("agenda_items", "creado_por_id")
