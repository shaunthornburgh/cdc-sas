import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.models import Inmueble, User
from app.models.enums import TipoInmueble, TipoNegocio
from app.schemas.inmuebles import (
    EstadoIn,
    InmuebleCreate,
    InmuebleList,
    InmuebleRead,
    InmuebleUpdate,
    Opciones,
    OpcionLead,
)
from app.services import inmuebles as service
from app.services import leads as lead_service
from app.services.pedidos import RANGOS
from app.services.policies import is_manager

# Property catalog: everyone in the commercial team sees it; Coordinación and Gerencia manage it.
router = APIRouter(prefix="/inmuebles", tags=["inmuebles"])

RANGO_LABELS = {
    "arr_2m": "Arriendo hasta $2.000.000",
    "arr_2_5m": "Arriendo $2.000.000 a $5.000.000",
    "ven_500m": "Venta hasta $500.000.000",
    "ven_mas_500m": "Venta más de $500.000.000",
}


def _read(inm: Inmueble, user: User) -> dict[str, Any]:
    ve = service.ve_propietario(user, inm)
    out = {c: getattr(inm, c) for c in InmuebleRead.model_fields if hasattr(inm, c)}
    return out | {
        "titulo": service.titulo(inm),
        "propietario_nombre": inm.propietario_nombre if ve else None,
        "propietario_telefono": inm.propietario_telefono if ve else None,
        "ve_propietario": ve,
        "estado_txt": service.ESTADO_LABELS[inm.estado],
        "faltantes": service.faltantes(inm),
        "captacion_code": inm.captacion.code if inm.captacion else None,
        "captador_name": inm.captador.full_name if inm.captador else None,
        "can_edit": service.can_edit(user, inm),
        "eventos": [
            {
                "titulo": e.titulo,
                "detalle": e.detalle,
                "created_by_name": e.created_by.full_name if e.created_by else None,
                "created_at": e.created_at,
            }
            for e in inm.eventos
        ],
    }


@router.get("/opciones", response_model=Opciones)
def opciones(user: CurrentUser) -> dict[str, Any]:
    service.ensure_view(user)
    return {
        "zonas": list(service.ZONAS),
        "rangos": {k: RANGO_LABELS[k] for k in RANGOS},
        "estados": {k.value: v for k, v in service.ESTADO_LABELS.items()},
        "puede_crear": is_manager(user),
    }


@router.get("", response_model=InmuebleList)
def listar(
    db: DbSession,
    user: CurrentUser,
    vista: Annotated[str, Query(pattern="^(todos|mios)$")] = "todos",
    estado: str | None = "vigentes",
    negocio: TipoNegocio | None = None,
    tipo: TipoInmueble | None = None,
    zona: str | None = None,
    rango: str | None = None,
    precio_min: Annotated[int | None, Query(ge=0)] = None,
    precio_max: Annotated[int | None, Query(ge=0)] = None,
    habitaciones: Annotated[int | None, Query(ge=0, le=30)] = None,
    incompletos: bool = False,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> dict[str, Any]:
    service.ensure_view(user)
    if service.sincronizar_captaciones(db):  # approved captaciones from before this module
        db.commit()
    f = service.Filtros(
        vista=vista,
        estado=None if estado == "todos" else estado,
        negocio=negocio,
        tipo=tipo,
        zona=zona,
        rango=rango,
        precio_min=precio_min,
        precio_max=precio_max,
        habitaciones=habitaciones,
        incompletos=incompletos,
        q=q,
    )
    return {
        "items": [_read(i, user) for i in service.list_inmuebles(db, user, f)],
        "kpis": service.kpis(db, user),
    }


@router.post("", response_model=InmuebleRead, status_code=status.HTTP_201_CREATED)
def crear(body: InmuebleCreate, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    inm = service.crear(db, body.model_dump(exclude_unset=True), actor=user)
    db.commit()
    db.refresh(inm)
    return _read(inm, user)


@router.get("/para-lead/{lead_id}", response_model=list[OpcionLead])
def para_lead(lead_id: uuid.UUID, db: DbSession, user: CurrentUser) -> list[dict[str, Any]]:
    """«Enviar opciones» (C02): available properties for this lead, marking those already sent."""
    lead = lead_service.get_lead(db, user, lead_id)
    out = []
    for inm, ya in service.opciones_para_lead(db, user, lead):
        bits = [inm.direccion]
        if inm.precio:
            bits.append("$" + f"{inm.precio:,}".replace(",", "."))
        if inm.habitaciones:
            bits.append(f"{inm.habitaciones} hab.")
        if inm.area_m2:
            bits.append(f"{float(inm.area_m2):g} m²")
        out.append(
            {
                "id": inm.id,
                "codigo": inm.codigo,
                "titulo": service.titulo(inm),
                "detalle": " · ".join(bits),
                "ya_enviado": ya,
            }
        )
    return out


@router.get("/{inmueble_id}", response_model=InmuebleRead)
def detalle(inmueble_id: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return _read(service.get_inmueble(db, user, inmueble_id), user)


@router.patch("/{inmueble_id}", response_model=InmuebleRead)
def actualizar(
    inmueble_id: uuid.UUID, body: InmuebleUpdate, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    inm = service.get_inmueble(db, user, inmueble_id)
    service.actualizar(db, inm, body.model_dump(exclude_unset=True), actor=user)
    db.commit()
    db.refresh(inm)
    return _read(inm, user)


@router.post("/{inmueble_id}/estado", response_model=InmuebleRead)
def estado(
    inmueble_id: uuid.UUID, body: EstadoIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    inm = service.get_inmueble(db, user, inmueble_id)
    service.cambiar_estado(db, inm, body.estado, nota=body.nota, actor=user)
    db.commit()
    db.refresh(inm)
    return _read(inm, user)


@router.delete("/{inmueble_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(inmueble_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Response:
    inm = service.get_inmueble(db, user, inmueble_id)
    service.eliminar(db, inm, actor=user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
