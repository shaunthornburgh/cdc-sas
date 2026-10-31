import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.user import User


class RendimientoConfig(UUIDPrimaryKeyMixin, Base):
    """Weights and goals of one person from a month on (until a later row replaces them).

    ``pesos``: area key → % (sums to 100). ``metas``: area key → goal for the month.
    """

    __tablename__ = "rendimiento_config"
    __table_args__ = (UniqueConstraint("user_id", "periodo", name="uq_rendimiento_config_periodo"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    periodo: Mapped[date] = mapped_column(Date)  # first day of the month
    pesos: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict, server_default="{}")
    metas: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict, server_default="{}")
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )


class Calificacion(UUIDPrimaryKeyMixin, Base):
    """A 1–5 rating of one indicator for one person and month («Calificaciones (1 a 5)»)."""

    __tablename__ = "calificaciones"
    __table_args__ = (
        UniqueConstraint("user_id", "periodo", "indicador", name="uq_calificacion"),
        CheckConstraint("valor BETWEEN 1 AND 5", name="valor_1_5"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    periodo: Mapped[date] = mapped_column(Date)
    indicador: Mapped[str] = mapped_column(String(40))
    valor: Mapped[int] = mapped_column(SmallInteger)
    calificado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )

    calificado_por: Mapped[User | None] = relationship(
        foreign_keys=[calificado_por_id], lazy="joined"
    )


class RendimientoCambio(UUIDPrimaryKeyMixin, Base):
    """Change log («Registro de cambios»): who changed weights, goals or ratings, before / after."""

    __tablename__ = "rendimiento_cambios"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[str] = mapped_column(String(20))  # pesos · metas · calificaciones
    periodo: Mapped[date] = mapped_column(Date)
    antes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    despues: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )

    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="joined")
