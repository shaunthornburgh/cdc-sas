"""Negocios (X02): money received from a sale. The deal itself is `Cierre` (one per lead Ganado)."""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, String, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.user import User


class NegocioAbono(UUIDPrimaryKeyMixin, Base):
    """«Registrar dinero recibido» (G-033): each payment the client makes on a sale."""

    __tablename__ = "negocio_abonos"

    cierre_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cierres.id", ondelete="CASCADE"), index=True
    )
    valor: Mapped[int] = mapped_column(BigInteger)
    fecha: Mapped[date] = mapped_column(Date)
    momento: Mapped[str] = mapped_column(String(20))  # promesa · escritura · otro
    soporte: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )

    created_by: Mapped[User | None] = relationship(lazy="joined")
