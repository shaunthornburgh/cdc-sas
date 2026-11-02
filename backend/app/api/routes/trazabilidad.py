import uuid
from dataclasses import asdict
from datetime import date
from typing import Any

from fastapi import APIRouter, Query, Response

from app.api.deps import CurrentUser, DbSession
from app.models.enums import Cargo
from app.schemas.trazabilidad import Lista, Opciones
from app.services import trazabilidad as svc

# G06 «Registro de cambios» (antes «Trazabilidad»).
router = APIRouter(prefix="/registro-cambios", tags=["registro de cambios"])


def _filtros(desde, hasta, modulo, usuario_id, q) -> svc.Filtros:
    d1, d2 = svc.rango_defecto()
    return svc.Filtros(desde or d1, hasta or d2, modulo or None, usuario_id, q)


@router.get("/opciones", response_model=Opciones)
def opciones(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    svc.ensure_view(user)
    d1, d2 = svc.rango_defecto()
    return {
        "modulos": svc.modulos_de(user),
        "usuarios": [{"id": u.id, "full_name": u.full_name} for u in svc.actores(db)],
        "desde": d1,
        "hasta": d2,
        "alcance": None
        if user.cargo == Cargo.GERENCIA
        else "Ves los cambios de la operación de tu equipo. Comisiones, bonos, pagos, salarios, "
        "negocios y la configuración solo los ve Gerencia.",
    }


@router.get("", response_model=Lista)
def listar(
    db: DbSession,
    user: CurrentUser,
    desde: date | None = None,
    hasta: date | None = None,
    modulo: str | None = None,
    usuario_id: uuid.UUID | None = None,
    q: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    f = _filtros(desde, hasta, modulo, usuario_id, q)
    filas = svc.consultar(db, user, f)
    return {
        "items": [asdict(x) for x in filas[offset : offset + limit]],
        "total": len(filas),
        "desde": f.desde,
        "hasta": f.hasta,
        "gerencia": user.cargo == Cargo.GERENCIA,
    }


@router.get("/export.csv")
def export_csv(
    db: DbSession,
    user: CurrentUser,
    desde: date | None = None,
    hasta: date | None = None,
    modulo: str | None = None,
    usuario_id: uuid.UUID | None = None,
    q: str | None = None,
) -> Response:
    f = _filtros(desde, hasta, modulo, usuario_id, q)
    content, _ = svc.export_csv(db, user, f)
    db.commit()
    nombre = f"CDC_Registro_de_cambios_{f.desde}_a_{f.hasta}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
