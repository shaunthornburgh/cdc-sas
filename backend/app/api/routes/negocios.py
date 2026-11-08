import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.models.enums import TipoNegocio
from app.schemas.negocios import (
    AbonoIn,
    CaidaIn,
    ConfirmarIn,
    EtapaIn,
    MotivoIn,
    NegocioPatch,
    SolicitarIn,
)
from app.services import negocios as svc

# X02 «Negocios» (Auxiliar, Gerencia, Coordinación read-only) and M16 (the asesor's own deals).
router = APIRouter(prefix="/negocios", tags=["negocios"])


def _desde_default(h: date) -> date:
    """First day of the month, four months back (X02 opens on July–October)."""
    m = h.month - 3
    y = h.year + (m - 1) // 12 if m < 1 else h.year
    m = (m - 1) % 12 + 1
    return date(y, m, 1)


@router.get("", response_model=dict)
def tablero(
    db: DbSession,
    user: CurrentUser,
    desde: date | None = None,
    hasta: date | None = None,
    tipo: TipoNegocio | None = None,
) -> dict[str, Any]:
    h = svc.hoy()
    data = svc.tablero(db, user, desde or _desde_default(h), hasta or h, tipo)
    db.commit()  # deals created by the sync with the leads «Ganado»
    return data


@router.get("/{id_}", response_model=dict)
def ver(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return svc.detalle(db, user, svc.get(db, user, id_))


@router.patch("/{id_}", response_model=dict)
def editar(id_: uuid.UUID, body: NegocioPatch, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    c = svc.get(db, user, id_)
    svc.editar(db, c, body.model_dump(exclude_unset=True), actor=user)
    db.commit()
    return svc.detalle(db, user, c)


@router.post("/{id_}/etapa", response_model=dict)
def etapa(id_: uuid.UUID, body: EtapaIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    c = svc.get(db, user, id_)
    svc.pasar_etapa(db, c, body.model_dump(), actor=user)
    db.commit()
    return svc.detalle(db, user, c)


@router.post("/{id_}/solicitar", response_model=dict)
def solicitar(
    id_: uuid.UUID, body: SolicitarIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    c = svc.get(db, user, id_)
    svc.solicitar(db, c, body.nota, actor=user)
    db.commit()
    return svc.detalle(db, user, c)


@router.post("/{id_}/confirmar", response_model=dict)
def confirmar(
    id_: uuid.UUID, body: ConfirmarIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    c = svc.get(db, user, id_)
    res = svc.confirmar(
        db,
        c,
        fecha=body.fecha,
        contrato_adjunto=body.contrato_adjunto,
        observacion=body.observacion,
        actor=user,
    )
    db.commit()
    return svc.detalle(db, user, c) | {"resultado": res}


@router.post("/{id_}/devolver", response_model=dict)
def devolver(id_: uuid.UUID, body: MotivoIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    c = svc.get(db, user, id_)
    svc.devolver(db, c, body.motivo, actor=user)
    db.commit()
    return svc.detalle(db, user, c)


@router.post("/{id_}/caida", response_model=dict)
def caida(id_: uuid.UUID, body: CaidaIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    c = svc.get(db, user, id_)
    res = svc.caida(db, c, body.motivo, body.observacion, actor=user)
    db.commit()
    return svc.detalle(db, user, c) | {"resultado": res}


@router.post("/{id_}/caida/descartar", response_model=dict)
def descartar_caida(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    c = svc.get(db, user, id_)
    svc.descartar_caida(db, c, actor=user)
    db.commit()
    return svc.detalle(db, user, c)


@router.post("/{id_}/abonos", response_model=dict, status_code=status.HTTP_201_CREATED)
def abono(id_: uuid.UUID, body: AbonoIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    c = svc.get(db, user, id_)
    svc.abono(db, c, body.model_dump(), actor=user)
    db.commit()
    return svc.detalle(db, user, c)
