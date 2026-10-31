"""actividad eventos

Revision ID: 77dec08323d2
Revises: 8404f363aaca
Create Date: 2026-10-28 22:35:45.481058

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "77dec08323d2"
down_revision: str | None = "8404f363aaca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Created in 8404f363aaca; reuse it instead of creating it again.
actividad_comercial = postgresql.ENUM(name="actividad_comercial", create_type=False)


def upgrade() -> None:
    op.create_table(
        "actividad_eventos",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("actividad", actividad_comercial, nullable=False),
        sa.Column("activada", sa.Boolean(), nullable=False),
        sa.Column("changed_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"],
            ["users.id"],
            name=op.f("fk_actividad_eventos_changed_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_actividad_eventos_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_actividad_eventos")),
    )
    op.create_index(
        op.f("ix_actividad_eventos_user_id"), "actividad_eventos", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_actividad_eventos_user_id"), table_name="actividad_eventos")
    op.drop_table("actividad_eventos")
