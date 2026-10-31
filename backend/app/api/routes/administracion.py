import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import Inmueble, Inventario, Reparacion, Solicitud, User
from app.models.enums import EstadoInmueble
from app.schemas.administracion import (
    AmbienteIn,
    AvanceIn,
    EstadoReparacionIn,
    EstadoSolicitudIn,
    InventarioCreate,
    InventarioRead,
    InventarioUpdate,
    ReparacionCreate,
    ReparacionRead,
    ReparacionUpdate,
    RespuestaIn,
    Resumen,
    SolicitudCreate,
    SolicitudRead,
    SolicitudUpdate,
)
from app.services import administracion as svc
from app.services import inmuebles as catalogo

# X14 «Administración de inmuebles»: inventories, repairs and owner / tenant requests.
router = APIRouter(prefix="/administracion-inmuebles", tags=["administracion-inmuebles"])


def _inm(i: Inmueble) -> dict[str, Any]:
    return {"id": i.id, "codigo": i.codigo, "titulo": catalogo.titulo(i)}


def _persona(u: User | None) -> dict[str, Any] | None:
    return {"id": u.id, "full_name": u.full_name} if u else None


def _eventos(r: svc.Registro) -> list[dict[str, Any]]:
    return [
        {
            "titulo": e.titulo,
            "detalle": e.detalle,
            "created_by_name": e.created_by.full_name if e.created_by else None,
            "created_at": e.created_at,
        }
        for e in r.eventos
    ]


def _inv(db, inv: Inventario, user: User) -> dict[str, Any]:
    rep = svc.reparacion_de(db, inv)
    return {
        "id": inv.id,
        "code": inv.code,
        "inmueble": _inm(inv.inmueble),
        "tipo": inv.tipo,
        "tipo_txt": svc.TIPO_INV_LABELS[inv.tipo],
        "fecha": inv.fecha,
        "referencia": inv.referencia,
        "responsable": _persona(inv.responsable),
        "estado": inv.estado,
        "estado_txt": svc.INV_LABELS[inv.estado],
        "firmado_at": inv.firmado_at,
        "ambientes": [
            {
                "id": a.id,
                "nombre": a.nombre,
                "estado": a.estado,
                "observacion": a.observacion,
                "fotos": a.fotos,
            }
            for a in inv.ambientes
        ],
        "novedades": len(svc.novedades(inv)),
        "fotos": sum(a.fotos for a in inv.ambientes),
        "reparacion_code": rep.code if rep else None,
        "puede_llenar": svc.can_work(user, inv)
        and inv.estado in (svc.IE.PROGRAMADO, svc.IE.REALIZADO),
        "puede_gestionar": svc.can_manage(user),
        "eventos": _eventos(inv),
    }


def _rep(rep: Reparacion, user: User) -> dict[str, Any]:
    abierta = rep.estado != svc.ME.TERMINADA
    return {
        "id": rep.id,
        "code": rep.code,
        "inmueble": _inm(rep.inmueble),
        "titulo": rep.titulo,
        "categoria": rep.categoria,
        "categoria_txt": svc.CAT_LABELS[rep.categoria],
        "prioridad": rep.prioridad,
        "solicitante": rep.solicitante,
        "fecha": rep.fecha,
        "estado": rep.estado,
        "estado_txt": svc.REP_LABELS[rep.estado],
        "proveedor": rep.proveedor,
        "valor": rep.valor,
        "paga": rep.paga,
        "paga_txt": svc.PAGA_LABELS[rep.paga],
        "fecha_fin": rep.fecha_fin,
        "dias": ((rep.fecha_fin or svc.hoy()) - rep.fecha).days,
        "responsable": _persona(rep.responsable),
        "inventario_code": rep.inventario.code if rep.inventario else None,
        "puede_avance": abierta and svc.can_work(user, rep),
        "puede_gestionar": abierta and svc.can_manage(user),
        "eventos": _eventos(rep),
    }


def _sol(sol: Solicitud, user: User) -> dict[str, Any]:
    viva = sol.estado in (svc.PE.ABIERTA, svc.PE.EN_TRAMITE)
    return {
        "id": sol.id,
        "code": sol.code,
        "inmueble": _inm(sol.inmueble),
        "tipo": sol.tipo,
        "tipo_txt": svc.TIPO_SOL_LABELS[sol.tipo],
        "de": sol.de,
        "de_txt": svc.DE_LABELS[sol.de],
        "nombre": sol.nombre,
        "canal": sol.canal,
        "canal_txt": svc.CANAL_LABELS[sol.canal],
        "descripcion": sol.descripcion,
        "prioridad": sol.prioridad,
        "fecha": sol.fecha,
        "estado": sol.estado,
        "estado_txt": svc.SOL_LABELS[sol.estado],
        "fuera_de_plazo": svc.fuera_de_plazo(sol),
        "dias_habiles": svc.dias_solicitud(sol),
        "plazo": svc.PLAZO_DIAS_HABILES,
        "responsable": _persona(sol.responsable),
        "respuesta": sol.respuesta,
        "fecha_respuesta": sol.fecha_respuesta,
        "puede_responder": viva and svc.can_work(user, sol),
        "puede_gestionar": sol.estado != svc.PE.CERRADA and svc.can_manage(user),
        "eventos": _eventos(sol),
    }


def _labels(m: dict) -> dict[str, str]:
    return {k.value: v for k, v in m.items()}


@router.get("/resumen", response_model=Resumen)
def resumen(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    """KPIs, and the lists / labels the forms need."""
    svc.ensure_view(user)
    manager = svc.can_manage(user)
    inms = (
        db.scalars(
            select(Inmueble)
            .where(Inmueble.estado != EstadoInmueble.RETIRADO)
            .order_by(Inmueble.codigo)
        ).unique()
        if manager
        else []
    )
    return {
        "kpis": svc.kpis(db, user),
        "puede_gestionar": manager,
        "plazo": svc.PLAZO_DIAS_HABILES,
        "inmuebles": [_inm(i) for i in inms],
        "responsables": [_persona(u) for u in svc.responsables(db)] if manager else [],
        "labels": {
            "tipo_inventario": _labels(svc.TIPO_INV_LABELS),
            "estado_inventario": _labels(svc.INV_LABELS),
            "estado_ambiente": _labels(svc.AMB_LABELS),
            "estado_reparacion": _labels(svc.REP_LABELS),
            "categoria": _labels(svc.CAT_LABELS),
            "paga": _labels(svc.PAGA_LABELS),
            "prioridad": _labels(svc.PRIORIDAD_LABELS),
            "estado_solicitud": _labels(svc.SOL_LABELS),
            "tipo_solicitud": _labels(svc.TIPO_SOL_LABELS),
            "de": _labels(svc.DE_LABELS),
            "canal": _labels(svc.CANAL_LABELS),
        },
    }


def _filtros(desde, hasta, estado, inmueble_id) -> svc.Filtros:
    return svc.Filtros(desde=desde, hasta=hasta, estado=estado or None, inmueble_id=inmueble_id)


# ---------------------------------------------------------------- inventarios


@router.get("/inventarios", response_model=list[InventarioRead])
def inventarios(
    db: DbSession,
    user: CurrentUser,
    desde: date | None = None,
    hasta: date | None = None,
    estado: str | None = None,
    inmueble_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    rows = svc.list_inventarios(db, user, _filtros(desde, hasta, estado, inmueble_id))
    return [_inv(db, i, user) for i in rows]


@router.post("/inventarios", response_model=InventarioRead, status_code=status.HTTP_201_CREATED)
def crear_inventario(body: InventarioCreate, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    inv = svc.crear_inventario(db, body.model_dump(), actor=user)
    db.commit()
    db.refresh(inv)
    return _inv(db, inv, user)


@router.get("/inventarios/{id_}", response_model=InventarioRead)
def inventario(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return _inv(db, svc.get_inventario(db, user, id_), user)


@router.patch("/inventarios/{id_}", response_model=InventarioRead)
def actualizar_inventario(
    id_: uuid.UUID, body: InventarioUpdate, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    inv = svc.get_inventario(db, user, id_)
    svc.actualizar_inventario(db, inv, body.model_dump(exclude_unset=True), actor=user)
    db.commit()
    db.refresh(inv)
    return _inv(db, inv, user)


@router.patch("/inventarios/{id_}/ambientes/{ambiente_id}", response_model=InventarioRead)
def ambiente(
    id_: uuid.UUID, ambiente_id: uuid.UUID, body: AmbienteIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    inv = svc.get_inventario(db, user, id_)
    svc.marcar_ambiente(db, inv, ambiente_id, body.model_dump(exclude_unset=True), actor=user)
    db.commit()
    db.refresh(inv)
    return _inv(db, inv, user)


@router.post("/inventarios/{id_}/firmar", response_model=InventarioRead)
def firmar(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    inv = svc.get_inventario(db, user, id_)
    svc.firmar_inventario(db, inv, actor=user)
    db.commit()
    db.refresh(inv)
    return _inv(db, inv, user)


@router.post(
    "/inventarios/{id_}/reparacion",
    response_model=ReparacionRead,
    status_code=status.HTTP_201_CREATED,
)
def reparacion_desde_inventario(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    inv = svc.get_inventario(db, user, id_)
    rep = svc.reparacion_desde_inventario(db, inv, actor=user)
    db.commit()
    db.refresh(rep)
    return _rep(rep, user)


@router.delete("/inventarios/{id_}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_inventario(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> Response:
    svc.eliminar_inventario(db, svc.get_inventario(db, user, id_), actor=user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- reparaciones


@router.get("/reparaciones", response_model=list[ReparacionRead])
def reparaciones(
    db: DbSession,
    user: CurrentUser,
    desde: date | None = None,
    hasta: date | None = None,
    estado: str | None = None,
    inmueble_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    rows = svc.list_reparaciones(db, user, _filtros(desde, hasta, estado, inmueble_id))
    return [_rep(r, user) for r in rows]


@router.post("/reparaciones", response_model=ReparacionRead, status_code=status.HTTP_201_CREATED)
def crear_reparacion(body: ReparacionCreate, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    rep = svc.crear_reparacion(db, body.model_dump(), actor=user)
    db.commit()
    db.refresh(rep)
    return _rep(rep, user)


@router.get("/reparaciones/{id_}", response_model=ReparacionRead)
def reparacion(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return _rep(svc.get_reparacion(db, user, id_), user)


@router.patch("/reparaciones/{id_}", response_model=ReparacionRead)
def actualizar_reparacion(
    id_: uuid.UUID, body: ReparacionUpdate, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    rep = svc.get_reparacion(db, user, id_)
    svc.actualizar_reparacion(db, rep, body.model_dump(exclude_unset=True), actor=user)
    db.commit()
    db.refresh(rep)
    return _rep(rep, user)


@router.post("/reparaciones/{id_}/avance", response_model=ReparacionRead)
def avance(id_: uuid.UUID, body: AvanceIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    rep = svc.get_reparacion(db, user, id_)
    svc.avance_reparacion(db, rep, body.model_dump(exclude_unset=True), actor=user)
    db.commit()
    db.refresh(rep)
    return _rep(rep, user)


@router.post("/reparaciones/{id_}/estado", response_model=ReparacionRead)
def estado_reparacion(
    id_: uuid.UUID, body: EstadoReparacionIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    rep = svc.get_reparacion(db, user, id_)
    svc.estado_reparacion(db, rep, body.estado, nota=body.nota, actor=user)
    db.commit()
    db.refresh(rep)
    return _rep(rep, user)


@router.delete("/reparaciones/{id_}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_reparacion(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> Response:
    svc.eliminar_reparacion(db, svc.get_reparacion(db, user, id_), actor=user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- solicitudes


@router.get("/solicitudes", response_model=list[SolicitudRead])
def solicitudes(
    db: DbSession,
    user: CurrentUser,
    desde: date | None = None,
    hasta: date | None = None,
    estado: str | None = None,
    inmueble_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    rows = svc.list_solicitudes(db, user, _filtros(desde, hasta, estado, inmueble_id))
    return [_sol(s, user) for s in rows]


@router.post("/solicitudes", response_model=SolicitudRead, status_code=status.HTTP_201_CREATED)
def crear_solicitud(body: SolicitudCreate, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    sol = svc.crear_solicitud(db, body.model_dump(), actor=user)
    db.commit()
    db.refresh(sol)
    return _sol(sol, user)


@router.get("/solicitudes/{id_}", response_model=SolicitudRead)
def solicitud(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return _sol(svc.get_solicitud(db, user, id_), user)


@router.patch("/solicitudes/{id_}", response_model=SolicitudRead)
def actualizar_solicitud(
    id_: uuid.UUID, body: SolicitudUpdate, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    sol = svc.get_solicitud(db, user, id_)
    svc.actualizar_solicitud(db, sol, body.model_dump(exclude_unset=True), actor=user)
    db.commit()
    db.refresh(sol)
    return _sol(sol, user)


@router.post("/solicitudes/{id_}/responder", response_model=SolicitudRead)
def responder(
    id_: uuid.UUID, body: RespuestaIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    sol = svc.get_solicitud(db, user, id_)
    svc.responder_solicitud(db, sol, body.respuesta, actor=user)
    db.commit()
    db.refresh(sol)
    return _sol(sol, user)


@router.post("/solicitudes/{id_}/estado", response_model=SolicitudRead)
def estado_solicitud(
    id_: uuid.UUID, body: EstadoSolicitudIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    sol = svc.get_solicitud(db, user, id_)
    svc.estado_solicitud(db, sol, body.estado, nota=body.nota, actor=user)
    db.commit()
    db.refresh(sol)
    return _sol(sol, user)


@router.delete("/solicitudes/{id_}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_solicitud(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> Response:
    svc.eliminar_solicitud(db, svc.get_solicitud(db, user, id_), actor=user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
