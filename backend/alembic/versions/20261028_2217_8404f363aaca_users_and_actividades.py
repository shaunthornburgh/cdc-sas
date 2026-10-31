"""users and actividades

Revision ID: 8404f363aaca
Revises:
Create Date: 2026-10-28 22:17:29.275561

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8404f363aaca"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# An independent function (Atención al Cliente / Pre-ventas) and commercial activities
# are mutually exclusive. The app checks this too; the trigger is the backstop.
FUNCION_VS_ACTIVIDADES_FN = """
CREATE FUNCTION enforce_funcion_vs_actividades() RETURNS trigger AS $$
BEGIN
    IF TG_TABLE_NAME = 'user_actividades' THEN
        IF EXISTS (SELECT 1 FROM users WHERE id = NEW.user_id AND funcion IS NOT NULL) THEN
            RAISE EXCEPTION 'user % has an independent function; commercial activities not allowed',
                NEW.user_id USING ERRCODE = 'check_violation';
        END IF;
    ELSIF NEW.funcion IS NOT NULL
          AND EXISTS (SELECT 1 FROM user_actividades WHERE user_id = NEW.id) THEN
        RAISE EXCEPTION 'user % has commercial activities; independent function not allowed',
            NEW.id USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column(
            "cargo",
            sa.Enum(
                "gerencia",
                "coordinacion",
                "asesor",
                "auxiliar_administrativa",
                "atencion_cliente",
                name="cargo",
            ),
            nullable=False,
        ),
        sa.Column(
            "funcion",
            sa.Enum("atencion_cliente", "pre_ventas", name="funcion_independiente"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.CheckConstraint(
            "cargo <> 'atencion_cliente' OR (funcion IS NOT NULL AND funcion = 'atencion_cliente')",
            name=op.f("ck_users_atencion_cliente_funcion"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_table(
        "user_actividades",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "actividad",
            sa.Enum("captacion", "ventas", "arriendos", name="actividad_comercial"),
            nullable=False,
        ),
        sa.Column("granted_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_id"],
            ["users.id"],
            name=op.f("fk_user_actividades_granted_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_actividades_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "actividad", name=op.f("pk_user_actividades")),
    )

    op.execute(FUNCION_VS_ACTIVIDADES_FN)
    op.execute(
        "CREATE TRIGGER trg_user_actividades_funcion BEFORE INSERT OR UPDATE ON user_actividades "
        "FOR EACH ROW EXECUTE FUNCTION enforce_funcion_vs_actividades()"
    )
    op.execute(
        "CREATE TRIGGER trg_users_funcion BEFORE INSERT OR UPDATE OF funcion ON users "
        "FOR EACH ROW EXECUTE FUNCTION enforce_funcion_vs_actividades()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_users_funcion ON users")
    op.execute("DROP TRIGGER IF EXISTS trg_user_actividades_funcion ON user_actividades")
    op.execute("DROP FUNCTION IF EXISTS enforce_funcion_vs_actividades()")
    op.drop_table("user_actividades")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    sa.Enum(name="actividad_comercial").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="funcion_independiente").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="cargo").drop(op.get_bind(), checkfirst=True)
