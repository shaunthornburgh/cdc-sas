import uuid
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.integraciones import AgregarIn, AjustesIn, DatosIn
from app.services import fechas
from app.services import integraciones as svc

# G07 «Integraciones» (solo Gerencia).
router = APIRouter(prefix="/integraciones", tags=["integraciones"])


def _rango(desde: date | None, hasta: date | None) -> tuple[date, date]:
    """Default: the last three months, as G07 opens on a quarter."""
    hoy = fechas.local_date(fechas.now())
    return desde or (hoy - timedelta(days=89)), hasta or hoy


@router.get("", response_model=dict)
def tablero(
    db: DbSession, user: CurrentUser, desde: date | None = None, hasta: date | None = None
) -> dict[str, Any]:
    d1, d2 = _rango(desde, hasta)
    out = svc.tablero(db, user, d1, d2)
    db.commit()  # the catalog may have been created
    out["como"] = svc.COMO
    out["grupos_txt"] = svc.GRUPOS
    return out


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def agregar(body: AgregarIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    i = svc.agregar(db, body.model_dump(), actor=user)
    db.commit()
    d1, d2 = _rango(None, None)
    return svc.detalle(db, user, i, d1, d2)


@router.get("/{id_}", response_model=dict)
def detalle(
    id_: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    desde: date | None = None,
    hasta: date | None = None,
) -> dict[str, Any]:
    d1, d2 = _rango(desde, hasta)
    i = svc.get(db, user, id_)
    out = svc.detalle(db, user, i, d1, d2)
    out["historial"] = [
        {
            "accion": e.accion,
            "antes": e.antes,
            "despues": e.despues,
            "actor": e.actor.full_name if e.actor else None,
            "at": e.created_at,
        }
        for e in svc.historial(db, i)
    ]
    return out


@router.put("/{id_}/datos", response_model=dict)
def guardar(id_: uuid.UUID, body: DatosIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    i = svc.get(db, user, id_)
    svc.guardar_datos(db, i, body.valores, actor=user)
    db.commit()
    return {"estado": i.estado, "estado_txt": svc.ESTADOS[i.estado][0]}


@router.post("/{id_}/probar", response_model=dict)
def probar(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    i = svc.get(db, user, id_)
    ok, txt = svc.probar(db, i, actor=user)
    db.commit()
    return {"ok": ok, "txt": txt}


@router.post("/{id_}/desconectar", response_model=dict)
def desconectar(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    i = svc.get(db, user, id_)
    svc.desconectar(db, i, actor=user)
    db.commit()
    return {"estado": i.estado, "estado_txt": svc.ESTADOS[i.estado][0]}


@router.patch("/{id_}", response_model=dict)
def ajustes(id_: uuid.UUID, body: AjustesIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    i = svc.get(db, user, id_)
    svc.ajustes(db, i, body.model_dump(exclude_unset=True), actor=user)
    db.commit()
    return {"costo_mensual": i.costo_mensual, "como": i.como, "avisar_falla": i.avisar_falla}
