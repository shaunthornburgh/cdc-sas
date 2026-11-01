from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.models import ConfigEvento
from app.schemas.configuracion import Marca, MarcaIn, Pagina, Pagos, Pendiente, PendienteIn
from app.services import configuracion as svc

# Z02 «Configuración».
router = APIRouter(prefix="/configuracion", tags=["configuracion"])


def _ev(e: ConfigEvento) -> dict[str, Any]:
    return {
        "id": e.id,
        "seccion": e.seccion,
        "seccion_txt": svc.SECCION_LABELS.get(e.seccion, e.seccion),
        "actor_name": e.actor.full_name if e.actor else None,
        "antes": e.antes,
        "despues": e.despues,
        "detalle": e.detalle,
        "created_at": e.created_at,
    }


@router.get("/marca", response_model=Marca)
def marca(db: DbSession) -> dict[str, Any]:
    """Public: the login page shows the brand before anyone signs in."""
    return svc.get(db, "marca")


@router.get("", response_model=Pagina)
def pagina(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    svc.ensure_view(user)
    ger = svc.can_edit(user)
    return {
        "gerencia": ger,
        "marca": svc.get(db, "marca"),
        "pagos": svc.pagos(db),
        **{
            s: svc.get(db, s) if ger else None
            for s in ("tarifas", "automatizaciones", "idioma", "leads", "produccion")
        },
        "pendientes": svc.pendientes(db) if ger else [],
        "opciones": svc.OPCIONES,
        "idiomas": svc.IDIOMAS,
        "idiomas_disponibles": list(svc.IDIOMAS_DISPONIBLES),
        "cambios": [_ev(e) for e in svc.cambios(db)] if ger else [],
    }


@router.put("/marca", response_model=Marca)
def guardar_marca(body: MarcaIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    out = svc.guardar(db, "marca", body.model_dump(exclude_unset=True), actor=user)
    db.commit()
    return out


@router.post("/marca/restaurar", response_model=Marca)
def restaurar_marca(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    out = svc.restaurar_marca(db, actor=user)
    db.commit()
    return out


@router.put("/pagos", response_model=Pagos)
def guardar_pagos(body: Pagos, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    out = svc.guardar_pagos(db, body.model_dump(), actor=user)
    db.commit()
    return out


@router.put("/{seccion}", response_model=dict)
def guardar(seccion: str, body: dict[str, Any], db: DbSession, user: CurrentUser) -> dict[str, Any]:
    """tarifas · automatizaciones · idioma · leads (validated per section in the service)."""
    if seccion == "marca":
        return guardar_marca(MarcaIn(**body), db, user)
    out = svc.guardar(db, seccion, body, actor=user)
    db.commit()
    return out


@router.put("/pendientes/{clave}", response_model=list[Pendiente])
def marcar(clave: str, body: PendienteIn, db: DbSession, user: CurrentUser) -> list[dict[str, Any]]:
    out = svc.marcar_pendiente(db, clave, body.resuelto, actor=user)
    db.commit()
    return out


@router.post("/uso-real", response_model=dict)
def uso_real(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    out = svc.activar_uso_real(db, actor=user)
    db.commit()
    return out
