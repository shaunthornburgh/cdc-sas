import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.polizas import (
    ActivarIn,
    AseguradoraIn,
    AseguradoraPatch,
    DecidirIn,
    FechaIn,
    MotivoIn,
    PolizaIn,
    PolizaPatch,
    TipoIn,
)
from app.services import polizas as svc

# X11 «Pólizas» (Auxiliar administrativa y Gerencia; «Comparar pólizas» solo Gerencia).
router = APIRouter(prefix="/polizas", tags=["polizas"])


def _rango(desde: date | None, hasta: date | None) -> svc.Rango:
    """Default: from January 1st to today, as X11 opens."""
    h = svc.hoy()
    return svc.Rango(desde or date(h.year, 1, 1), hasta or h)


@router.get("", response_model=dict)
def tablero(
    db: DbSession,
    user: CurrentUser,
    desde: date | None = None,
    hasta: date | None = None,
    aseguradora_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    return svc.tablero(db, user, _rango(desde, hasta), aseguradora_id) | {
        "gerencia": user.cargo == "gerencia"
    }


@router.get("/opciones", response_model=dict)
def opciones(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return svc.opciones(db, user)


@router.get("/comparar", response_model=dict)
def comparar(
    db: DbSession, user: CurrentUser, desde: date | None = None, hasta: date | None = None
) -> dict[str, Any]:
    return svc.comparar(db, user, _rango(desde, hasta))


# ---- insurers


@router.get("/aseguradoras", response_model=dict)
def aseguradoras(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return svc.aseguradoras_vista(db, user)


@router.post("/aseguradoras", response_model=dict, status_code=status.HTTP_201_CREATED)
def crear_aseguradora(body: AseguradoraIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    a = svc.crear_aseguradora(db, body.model_dump(), actor=user)
    db.commit()
    return {"id": a.id, "nombre": a.nombre}


@router.patch("/aseguradoras/{id_}", response_model=dict)
def editar_aseguradora(
    id_: uuid.UUID, body: AseguradoraPatch, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    a = svc.get_aseguradora(db, user, id_)
    svc.editar_aseguradora(db, a, body.model_dump(exclude_unset=True), actor=user)
    db.commit()
    return {"id": a.id, "activa": a.activa, "dias_max": a.dias_max, "aviso_dias": a.aviso_dias}


@router.post("/aseguradoras/{id_}/tipos", response_model=dict, status_code=status.HTTP_201_CREATED)
def agregar_tipo(id_: uuid.UUID, body: TipoIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    a = svc.get_aseguradora(db, user, id_)
    t = svc.agregar_tipo(db, a, body.model_dump(), actor=user)
    db.commit()
    return {"id": t.id, "nombre": t.nombre}


@router.delete("/aseguradoras/{id_}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_aseguradora(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> None:
    a = svc.get_aseguradora(db, user, id_)
    svc.eliminar_aseguradora(db, a, actor=user)
    db.commit()


# ---- policies


def _out(db, p) -> dict[str, Any]:
    return svc._fila(p, svc.hoy()) | {"historial": svc.historial(db, p)}


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def crear(body: PolizaIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    p = svc.crear(db, body.model_dump(), actor=user)
    db.commit()
    return _out(db, p)


@router.get("/{id_}", response_model=dict)
def ver(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return _out(db, svc.get(db, user, id_))


@router.patch("/{id_}", response_model=dict)
def editar(id_: uuid.UUID, body: PolizaPatch, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    p = svc.get(db, user, id_)
    svc.editar(db, p, body.model_dump(exclude_unset=True), actor=user)
    db.commit()
    return _out(db, p)


@router.post("/{id_}/decidir", response_model=dict)
def decidir(id_: uuid.UUID, body: DecidirIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    p = svc.get(db, user, id_)
    svc.decidir(db, p, body.aprobada, body.motivo, actor=user)
    db.commit()
    return _out(db, p)


@router.post("/{id_}/retomar", response_model=dict)
def retomar(id_: uuid.UUID, body: MotivoIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    p = svc.get(db, user, id_)
    svc.retomar(db, p, body.motivo, actor=user)
    db.commit()
    return _out(db, p)


@router.post("/{id_}/firma", response_model=dict)
def firma(id_: uuid.UUID, body: FechaIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    p = svc.get(db, user, id_)
    svc.firmar(db, p, body.fecha, actor=user)
    db.commit()
    return _out(db, p)


@router.post("/{id_}/activar", response_model=dict)
def activar(id_: uuid.UUID, body: ActivarIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    p = svc.get(db, user, id_)
    svc.activar(db, p, body.fecha, body.numero, body.soporte, actor=user)
    db.commit()
    return _out(db, p)


@router.post("/{id_}/terminar", response_model=dict)
def terminar(id_: uuid.UUID, body: FechaIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    p = svc.get(db, user, id_)
    svc.terminar(db, p, body.fecha, actor=user)
    db.commit()
    return _out(db, p)


@router.post("/{id_}/eliminar", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(id_: uuid.UUID, body: MotivoIn, db: DbSession, user: CurrentUser) -> None:
    p = svc.get(db, user, id_)
    svc.eliminar(db, p, body.motivo, actor=user)
    db.commit()
