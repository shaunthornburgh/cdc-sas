import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import CurrentUser, DbSession
from app.models.enums import Cargo
from app.schemas.preoperacional import (
    ConfigIn,
    Equipo,
    Formulario,
    Historial,
    PreoperacionalIn,
    PreoperacionalRead,
    RevisionIn,
)
from app.services import preoperacional as service

# Everyone does the preoperacional (G-012); team views are for Coordinación / Gerencia.
router = APIRouter(prefix="/preoperacional", tags=["preoperacional"])


@router.get("/formulario", response_model=Formulario)
def formulario(db: DbSession, user: CurrentUser) -> dict:
    """Means of transport, the official questions and today's record (if already done)."""
    return {
        "activo": service.activo_para(db, user),
        "medios": service.MEDIO_LABELS,
        "preguntas": {k: list(v) for k, v in service.PREGUNTAS.items()},
        "hoy": service.hoy(),
        "registro_de_hoy": service.get_de_hoy(db, user),
        "destinatario": service.destinatario(user),
    }


@router.post("", response_model=PreoperacionalRead, status_code=201)
def registrar(body: PreoperacionalIn, db: DbSession, user: CurrentUser) -> object:
    pre = service.registrar(
        db,
        user,
        medio=body.medio,
        placa=body.placa,
        respuestas=body.respuestas,
        observaciones=body.observaciones,
    )
    db.commit()
    db.refresh(pre)
    return pre


@router.get("/mios", response_model=Historial)
def mi_historial(
    db: DbSession,
    user: CurrentUser,
    mes: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> dict:
    """«Mi historial y puntaje»: calendar, score of the month, novedades and missed days."""
    return service.mi_historial(db, user, mes)


@router.get("/equipo", response_model=Equipo)
def equipo(db: DbSession, user: CurrentUser, fecha: date | None = None) -> dict:
    """K09: everyone this person reviews, for one day, plus the month's automatic score."""
    return service.equipo(db, user, fecha)


@router.post("/{pre_id}/revisar", response_model=PreoperacionalRead)
def revisar(pre_id: uuid.UUID, body: RevisionIn, db: DbSession, user: CurrentUser) -> object:
    """«Marcar novedad como revisada» (Coordinación / Gerencia)."""
    pre = service.get_para_revisar(db, user, pre_id)
    service.revisar(db, pre, nota=body.nota, actor=user)
    db.commit()
    db.refresh(pre)
    return pre


@router.get("/config", response_model=dict[Cargo, bool])
def get_config(db: DbSession, _: CurrentUser) -> dict:
    return service.config(db)


@router.put("/config/{cargo}", response_model=dict[Cargo, bool])
def set_config(cargo: Cargo, body: ConfigIn, db: DbSession, user: CurrentUser) -> dict:
    """Gerencia turns the preoperacional on or off for a cargo."""
    out = service.set_config(db, cargo, body.activo, actor=user)
    db.commit()
    return out


@router.get("/export.csv")
def export_csv(
    db: DbSession,
    user: CurrentUser,
    mes: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    user_id: uuid.UUID | None = None,
) -> Response:
    """Download a month (optionally one person) — opens in Excel."""
    first, _ = service.mes_bounds(mes)
    body = service.export_csv(db, user, mes, user_id)
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="preoperacionales-{first:%Y-%m}.csv"'
        },
    )
