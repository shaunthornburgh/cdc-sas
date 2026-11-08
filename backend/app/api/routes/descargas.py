import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, DbSession
from app.services import descargas as svc

# X10 «Descargas del personal» (Auxiliar administrativa, Gerencia, Coordinación).
router = APIRouter(prefix="/descargas", tags=["descargas"])


def _filtros(
    tipo: str,
    desde: date,
    hasta: date,
    alcance: str,
    grupo: str | None,
    user_id: uuid.UUID | None,
) -> svc.Filtros:
    return svc.Filtros(
        tipo=tipo, desde=desde, hasta=hasta, alcance=alcance, grupo=grupo, user_id=user_id
    )


@router.get("", response_model=dict)
def opciones(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return svc.opciones(db, user)


@router.get("/{tipo}/vista-previa", response_model=dict)
def vista_previa(
    tipo: str,
    db: DbSession,
    user: CurrentUser,
    desde: date,
    hasta: date,
    alcance: str = "tod",
    grupo: str | None = None,
    user_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    return svc.vista_previa(db, user, _filtros(tipo, desde, hasta, alcance, grupo, user_id))


@router.get("/{tipo}.csv")
def descargar(
    tipo: str,
    db: DbSession,
    user: CurrentUser,
    desde: date,
    hasta: date,
    alcance: str = "tod",
    grupo: str | None = None,
    user_id: uuid.UUID | None = None,
) -> Response:
    """The file (opens in Excel). Every download is logged."""
    content, nombre, filas = svc.descargar(
        db, user, _filtros(tipo, desde, hasta, alcance, grupo, user_id)
    )
    db.commit()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{nombre}"',
            "X-Filas": str(filas),
            "Access-Control-Expose-Headers": "Content-Disposition, X-Filas",
        },
    )
