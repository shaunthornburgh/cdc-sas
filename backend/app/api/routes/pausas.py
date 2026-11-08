import calendar
import uuid
from datetime import date, time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession
from app.services import fechas
from app.services import pausas as svc

# G11 «Pausas activas»: everyone marks theirs from the Inicio; the Auxiliar, Coordinación and
# Gerencia see the team.
router = APIRouter(prefix="/pausas-activas", tags=["pausas activas"])


class HorarioIn(BaseModel):
    hora_manana: time
    hora_tarde: time
    minutos: int


class MensajeIn(BaseModel):
    mensaje: str = Field(max_length=300)


def _mes(desde: date | None, hasta: date | None) -> tuple[date, date]:
    """Default: this month."""
    h = fechas.local_date(fechas.now())
    return (
        desde or h.replace(day=1),
        hasta or h.replace(day=calendar.monthrange(h.year, h.month)[1]),
    )


@router.get("/ahora", response_model=dict)
def ahora(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    """The Inicio banner: the pause on screen now (if any) and today's two."""
    return svc.ahora(db, user)


@router.post("/realizada", response_model=dict)
def realizada(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    p = svc.marcar(db, user)
    db.commit()
    return {"turno": p.turno, "realizada_at": p.realizada_at}


@router.get("/mias", response_model=dict)
def mias(
    db: DbSession, user: CurrentUser, desde: date | None = None, hasta: date | None = None
) -> dict[str, Any]:
    return svc.mias(db, user, *_mes(desde, hasta))


@router.get("/equipo", response_model=dict)
def equipo(
    db: DbSession,
    user: CurrentUser,
    desde: date | None = None,
    hasta: date | None = None,
    user_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    return svc.equipo(db, user, *_mes(desde, hasta), user_id)


@router.put("/horario", response_model=dict)
def horario(body: HorarioIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    c = svc.set_horario(db, body.hora_manana, body.hora_tarde, body.minutos, actor=user)
    db.commit()
    return {"hora_manana": c.hora_manana, "hora_tarde": c.hora_tarde, "minutos": c.minutos}


@router.put("/mensaje", response_model=dict)
def mensaje(body: MensajeIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    c = svc.set_mensaje(db, body.mensaje, actor=user)
    db.commit()
    return {"mensaje": c.mensaje}
