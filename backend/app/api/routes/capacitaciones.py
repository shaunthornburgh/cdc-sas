import calendar
import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.capacitaciones import (
    AprendizajeIn,
    CompletarIn,
    MotivoIn,
    ProgramarIn,
    RegistrarIn,
    ResponderIn,
)
from app.services import capacitaciones as svc
from app.services import fechas

# Z03 «Mis capacitaciones» (everyone) and X07 «Capacitaciones del equipo» (Auxiliar,
# Coordinación, Gerencia).
router = APIRouter(prefix="/capacitaciones", tags=["capacitaciones"])


@router.get("/mias", response_model=dict)
def mias(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return svc.mis(db, user)


@router.get("/equipo", response_model=dict)
def equipo(
    db: DbSession, user: CurrentUser, desde: date | None = None, hasta: date | None = None
) -> dict[str, Any]:
    """Default: this month."""
    h = fechas.local_date(fechas.now())
    d1 = desde or h.replace(day=1)
    d2 = hasta or h.replace(day=calendar.monthrange(h.year, h.month)[1])
    return svc.equipo(db, user, svc.Rango(d1, d2))


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def programar(body: ProgramarIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    c = svc.programar(db, body.model_dump(), actor=user)
    db.commit()
    return {"id": c.id, "code": c.code, "participantes": len(c.participantes)}


@router.post("/registrar", response_model=dict, status_code=status.HTTP_201_CREATED)
def registrar(body: RegistrarIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    c = svc.registrar(db, body.model_dump(), actor=user)
    db.commit()
    return {"id": c.id, "code": c.code}


@router.post("/{id_}/responder", response_model=dict)
def responder(
    id_: uuid.UUID, body: ResponderIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    c = svc.get(db, user, id_)
    p = svc.responder(
        db, c, acepta=body.acepta, motivo=body.motivo, detalle=body.detalle, actor=user
    )
    db.commit()
    e, cls, m = svc.estado_part(c, p)
    return {
        "id": c.id,
        "respuesta": p.respuesta,
        "estado_txt": e,
        "estado_cls": cls,
        "motivo_txt": m,
    }


@router.post("/{id_}/completar", response_model=dict)
def completar(
    id_: uuid.UUID, body: CompletarIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    c = svc.get(db, user, id_)
    svc.completar(db, c, body.asistentes, actor=user)
    db.commit()
    return {
        "id": c.id,
        "estado": c.estado,
        "participaron": sum(1 for p in c.participantes if p.asistio),
    }


@router.post("/{id_}/cancelar", response_model=dict)
def cancelar(id_: uuid.UUID, body: MotivoIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    c = svc.get(db, user, id_)
    svc.cancelar(db, c, body.motivo, actor=user)
    db.commit()
    return {"id": c.id, "estado": c.estado}


@router.post("/{id_}/aprendizaje", response_model=dict)
def aprendizaje(
    id_: uuid.UUID, body: AprendizajeIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    c = svc.get(db, user, id_)
    svc.aprendizaje(db, c, body.aprendio, body.observaciones, actor=user)
    db.commit()
    return {"id": c.id}
