"""Administración de inmuebles (prototype X14).

Three record types, each linked to a property of the catalog:

* **Inventarios** (INV): move-in («entrega») or move-out («recepción»). The responsible asesor
  checks each room (bueno / regular / malo, a note, photos) on site, which makes it «realizado».
  Then the signatures of owner and tenant are registered: «firmado» if every room is fine,
  «con novedades» if not. From the findings a repair is created with one click.
* **Reparaciones** (MAN): recibida → cotizada → aprobada → en ejecución → terminada. Progress
  (provider, quote, who pays, comments) is logged. A finished repair is locked.
* **Solicitudes** (PQR): petición / queja / reclamo / sugerencia from an owner or tenant, with a
  response deadline in business days. Past it and unanswered, it's «fuera de plazo».

**Who** (X14 is a page of the Auxiliar and Gerencia; Coordinación also manages, as everywhere):
Coordinación, Gerencia and the Auxiliar see and manage everything. Anyone else who can see the
catalog only sees the records assigned to them, and works them: the asesor fills in their
inventory, the person following a repair logs progress, the person in charge of a request answers
it. Scheduling, assigning, status changes, signatures and deleting stay with the managers.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import (
    AdminEvento,
    Inmueble,
    Inventario,
    InventarioAmbiente,
    Reparacion,
    Solicitud,
    User,
)
from app.models.enums import (
    CanalSolicitud,
    Cargo,
    CategoriaReparacion,
    EstadoAmbiente,
    EstadoInventario,
    EstadoReparacion,
    EstadoSolicitud,
    PagaReparacion,
    Prioridad,
    Solicitante,
    TipoInventario,
    TipoSolicitud,
)
from app.services import fechas
from app.services import inmuebles as catalogo
from app.services.errors import ConflictError, DomainError, NotFoundError, PermissionDeniedError

# Response deadline for requests. X14 marks it «PENDIENTE DE CONFIGURACIÓN» and uses 15.
PLAZO_DIAS_HABILES = 15
# Rooms of a new inventory (X14's checklist).
AMBIENTES = (
    "Sala y comedor",
    "Cocina",
    "Baños",
    "Habitaciones",
    "Pisos y paredes",
    "Puertas y ventanas",
    "Instalaciones (agua, luz, gas)",
    "Llaves y controles",
)

IE, ME, PE = EstadoInventario, EstadoReparacion, EstadoSolicitud
TIPO_INV_LABELS = {
    TipoInventario.ENTREGA: "Entrega al inquilino",
    TipoInventario.RECEPCION: "Recepción al terminar",
}
INV_LABELS = {
    IE.PROGRAMADO: "Programado",
    IE.REALIZADO: "Realizado · falta firmar",
    IE.CON_NOVEDADES: "Con novedades",
    IE.FIRMADO: "Firmado",
}
AMB_LABELS = {
    EstadoAmbiente.BUENO: "Bueno",
    EstadoAmbiente.REGULAR: "Regular",
    EstadoAmbiente.MALO: "Malo",
}
REP_LABELS = {
    ME.RECIBIDA: "Recibida",
    ME.COTIZADA: "Cotizada",
    ME.APROBADA: "Aprobada",
    ME.EN_EJECUCION: "En ejecución",
    ME.TERMINADA: "Terminada",
}
CAT_LABELS = {
    CategoriaReparacion.PLOMERIA: "Plomería",
    CategoriaReparacion.ELECTRICO: "Eléctrico",
    CategoriaReparacion.HUMEDAD: "Humedad",
    CategoriaReparacion.CERRAJERIA: "Cerrajería",
    CategoriaReparacion.PINTURA: "Pintura",
    CategoriaReparacion.ELECTRODOMESTICOS: "Electrodomésticos",
    CategoriaReparacion.OTRO: "Otro",
}
PAGA_LABELS = {
    PagaReparacion.POR_DEFINIR: "Por definir",
    PagaReparacion.PROPIETARIO: "Propietario",
    PagaReparacion.INQUILINO: "Inquilino",
    PagaReparacion.EMPRESA: "Empresa",
    PagaReparacion.ASEGURADORA: "Aseguradora",
}
PRIORIDAD_LABELS = {Prioridad.NORMAL: "Normal", Prioridad.URGENTE: "Urgente"}
SOL_LABELS = {
    PE.ABIERTA: "Abierta",
    PE.EN_TRAMITE: "En trámite",
    PE.RESPONDIDA: "Respondida",
    PE.CERRADA: "Cerrada",
}
TIPO_SOL_LABELS = {
    TipoSolicitud.PETICION: "Petición",
    TipoSolicitud.QUEJA: "Queja",
    TipoSolicitud.RECLAMO: "Reclamo",
    TipoSolicitud.SUGERENCIA: "Sugerencia",
}
DE_LABELS = {Solicitante.PROPIETARIO: "Propietario", Solicitante.INQUILINO: "Inquilino"}
CANAL_LABELS = {
    CanalSolicitud.WHATSAPP: "WhatsApp",
    CanalSolicitud.LLAMADA: "Llamada",
    CanalSolicitud.CORREO: "Correo",
    CanalSolicitud.OFICINA: "Oficina",
}
ADMIN_CARGOS = (Cargo.GERENCIA, Cargo.COORDINACION, Cargo.AUXILIAR_ADMINISTRATIVA)

Registro = Inventario | Reparacion | Solicitud


# ---------------------------------------------------------------- access


def can_manage(user: User) -> bool:
    return user.is_active and user.cargo in ADMIN_CARGOS


def can_view(user: User) -> bool:
    """Managers see all; the rest of the catalog's users see what is assigned to them."""
    return can_manage(user) or catalogo.can_view(user)


def ensure_view(user: User) -> None:
    if not can_view(user):
        raise PermissionDeniedError("No tienes acceso a la administración de inmuebles.")


def ensure_manage(user: User, que: str = "Esta acción") -> None:
    if not can_manage(user):
        raise PermissionDeniedError(f"{que} es de Coordinación, Gerencia o la Auxiliar.")


def es_responsable(user: User, r: Registro) -> bool:
    return r.responsable_id is not None and r.responsable_id == user.id


def can_see(user: User, r: Registro) -> bool:
    return can_manage(user) or es_responsable(user, r)


def can_work(user: User, r: Registro) -> bool:
    """Fill in the inventory, log repair progress, answer the request."""
    return can_manage(user) or es_responsable(user, r)


def _get(db: Session, model: type, user: User, id_: uuid.UUID, que: str):
    ensure_view(user)
    r = db.get(model, id_)
    if r is None or not can_see(user, r):  # don't reveal records that aren't theirs
        raise NotFoundError(f"{que} no existe.")
    return r


def get_inventario(db: Session, user: User, id_: uuid.UUID) -> Inventario:
    return _get(db, Inventario, user, id_, "Ese inventario")


def get_reparacion(db: Session, user: User, id_: uuid.UUID) -> Reparacion:
    return _get(db, Reparacion, user, id_, "Esa reparación")


def get_solicitud(db: Session, user: User, id_: uuid.UUID) -> Solicitud:
    return _get(db, Solicitud, user, id_, "Esa solicitud")


def responsables(db: Session) -> list[User]:
    """Who can be put in charge: managers of this module and anyone who can see the catalog."""
    users = db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.full_name))
    return [u for u in users.unique() if can_view(u)]


def _inmueble(db: Session, id_: uuid.UUID | None) -> Inmueble:
    inm = db.get(Inmueble, id_) if id_ else None
    if inm is None:
        raise DomainError("Elige el inmueble.")
    return inm


def _responsable(db: Session, id_: uuid.UUID | None, *, required: bool = False) -> User | None:
    if id_ is None:
        if required:
            raise DomainError("Elige el responsable.")
        return None
    u = db.get(User, id_)
    if u is None or not u.is_active or not can_view(u):
        raise DomainError("Ese responsable no puede atender registros de inmuebles.")
    return u


# ---------------------------------------------------------------- helpers


def hoy() -> date:
    return fechas.local_date(fechas.now())


def dias_habiles(desde: date, hasta: date) -> int:
    """Monday-to-Friday days after `desde` up to `hasta` (holidays not counted: simplification)."""
    n, d = 0, desde
    while d < hasta:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def dias_solicitud(s: Solicitud, ref: date | None = None) -> int:
    fin = s.fecha_respuesta if s.estado in (PE.RESPONDIDA, PE.CERRADA) else None
    return dias_habiles(s.fecha, fin or ref or hoy())


def fuera_de_plazo(s: Solicitud, ref: date | None = None) -> bool:
    return s.estado in (PE.ABIERTA, PE.EN_TRAMITE) and dias_solicitud(s, ref) > PLAZO_DIAS_HABILES


def novedades(inv: Inventario) -> list[InventarioAmbiente]:
    return [a for a in inv.ambientes if a.estado in (EstadoAmbiente.REGULAR, EstadoAmbiente.MALO)]


def reparacion_de(db: Session, inv: Inventario) -> Reparacion | None:
    return db.scalar(select(Reparacion).where(Reparacion.inventario_id == inv.id))


def _texto(v: str | None, msg: str, minimo: int = 3) -> str:
    v = (v or "").strip()
    if len(v) < minimo:
        raise DomainError(msg)
    return v


def _evento(db: Session, r: Registro, titulo: str, actor: User | None, detalle: str | None = None):
    campo = {Inventario: "inventario_id", Reparacion: "reparacion_id", Solicitud: "solicitud_id"}
    ev = AdminEvento(
        titulo=titulo,
        detalle=detalle,
        created_by_id=actor.id if actor else None,
        **{campo[type(r)]: r.id},
    )
    db.add(ev)
    r.eventos.append(ev)


def _cop(v: int | None) -> str:
    return "$" + f"{int(v):,}".replace(",", ".") if v else "—"


def _fmt_fecha(d: date) -> str:
    return f"{d.day} {fechas._MESES[d.month - 1]} {d.year}"


def _cambios(r: Any, data: dict[str, Any], permitidos: tuple[str, ...]) -> list[str]:
    """Apply simple field changes; returns the labels of what changed."""
    if extra := set(data) - set(permitidos):
        raise DomainError(f"No se puede cambiar «{sorted(extra)[0]}».")
    out = []
    for k, v in data.items():
        if isinstance(v, str):
            v = v.strip() or None
        if getattr(r, k) != v:
            setattr(r, k, v)
            out.append(k)
    return out


# ---------------------------------------------------------------- list filters & KPIs


@dataclass
class Filtros:
    desde: date | None = None
    hasta: date | None = None
    estado: str | None = None
    inmueble_id: uuid.UUID | None = None


def _filtrar(q: Select, model: type, user: User, f: Filtros, estados: type) -> Select:
    if not can_manage(user):
        q = q.where(model.responsable_id == user.id)
    if f.desde and f.hasta and f.desde > f.hasta:
        raise DomainError("La fecha «Desde» no puede ser posterior a «Hasta».")
    if f.desde:
        q = q.where(model.fecha >= f.desde)
    if f.hasta:
        q = q.where(model.fecha <= f.hasta)
    if f.inmueble_id:
        q = q.where(model.inmueble_id == f.inmueble_id)
    if f.estado and f.estado != "fuera_de_plazo":
        try:
            q = q.where(model.estado == estados(f.estado))
        except ValueError:
            raise DomainError("Estado no válido.") from None
    return q.order_by(model.fecha.desc(), model.numero.desc())


def list_inventarios(db: Session, user: User, f: Filtros) -> list[Inventario]:
    ensure_view(user)
    return list(db.scalars(_filtrar(select(Inventario), Inventario, user, f, IE)).unique())


def list_reparaciones(db: Session, user: User, f: Filtros) -> list[Reparacion]:
    ensure_view(user)
    return list(db.scalars(_filtrar(select(Reparacion), Reparacion, user, f, ME)).unique())


def list_solicitudes(db: Session, user: User, f: Filtros) -> list[Solicitud]:
    ensure_view(user)
    rows = list(db.scalars(_filtrar(select(Solicitud), Solicitud, user, f, PE)).unique())
    if f.estado == "fuera_de_plazo":
        rows = [s for s in rows if fuera_de_plazo(s)]
    return rows


def kpis(db: Session, user: User) -> dict[str, Any]:
    """X14's six KPI cards (over everything the user can see, not the date filter)."""
    ensure_view(user)
    vacio = Filtros()
    inv = list_inventarios(db, user, vacio)
    rep = list_reparaciones(db, user, vacio)
    sol = list_solicitudes(db, user, vacio)
    d = hoy()
    abiertas = [r for r in rep if r.estado != ME.TERMINADA]
    terminadas = [r for r in rep if r.estado == ME.TERMINADA and r.fecha_fin]
    sol_ab = [s for s in sol if s.estado in (PE.ABIERTA, PE.EN_TRAMITE)]
    return {
        "inventarios_semana": sum(
            1 for i in inv if i.estado == IE.PROGRAMADO and 0 <= (i.fecha - d).days <= 7
        ),
        "inventarios_novedades": sum(1 for i in inv if i.estado == IE.CON_NOVEDADES),
        "inventarios": len(inv),
        "reparaciones_abiertas": len(abiertas),
        "reparaciones_urgentes": sum(1 for r in abiertas if r.prioridad == Prioridad.URGENTE),
        "reparacion_dias_promedio": round(
            sum((r.fecha_fin - r.fecha).days for r in terminadas) / len(terminadas), 1
        )
        if terminadas
        else 0,
        "solicitudes_abiertas": len(sol_ab),
        "solicitudes_fuera_plazo": sum(1 for s in sol_ab if fuera_de_plazo(s, d)),
    }


def operaciones_de(db: Session, inm: Inmueble) -> bool:
    """Does the property have inventories, repairs or requests? (it can't be deleted then)"""
    return any(
        db.scalar(select(m.id).where(m.inmueble_id == inm.id).limit(1))
        for m in (Inventario, Reparacion, Solicitud)
    )


# ---------------------------------------------------------------- inventarios


def crear_inventario(db: Session, data: dict[str, Any], *, actor: User) -> Inventario:
    ensure_manage(actor, "Programar inventarios")
    inm = _inmueble(db, data.get("inmueble_id"))
    resp = _responsable(db, data.get("responsable_id"), required=True)
    if data.get("fecha") is None:
        raise DomainError("Elige la fecha.")
    inv = Inventario(
        inmueble_id=inm.id,
        tipo=data["tipo"],
        fecha=data["fecha"],
        referencia=_texto(data.get("referencia"), "Escribe la referencia (contrato y cliente)."),
        responsable_id=resp.id,
        estado=IE.PROGRAMADO,
        created_by_id=actor.id,
    )
    inv.inmueble = inm
    inv.responsable = resp
    inv.ambientes = [InventarioAmbiente(orden=i, nombre=n) for i, n in enumerate(AMBIENTES)]
    db.add(inv)
    db.flush()
    _evento(db, inv, f"Programado por {actor.full_name}", actor, f"Responsable: {resp.full_name}.")
    catalogo._event(
        db, inm, f"Inventario {inv.code} programado", actor, TIPO_INV_LABELS[inv.tipo] + "."
    )
    db.flush()
    return inv


def actualizar_inventario(
    db: Session, inv: Inventario, data: dict[str, Any], *, actor: User
) -> Inventario:
    ensure_manage(actor, "Reprogramar inventarios")
    if inv.estado != IE.PROGRAMADO:
        raise ConflictError("El inventario ya se realizó: no se reprograma.")
    if "responsable_id" in data:
        resp = _responsable(db, data["responsable_id"], required=True)
        inv.responsable = resp
    if "referencia" in data:
        data["referencia"] = _texto(data["referencia"], "Escribe la referencia.")
    if "fecha" in data and data["fecha"] is None:
        raise DomainError("Elige la fecha.")
    cambios = _cambios(inv, data, ("tipo", "fecha", "referencia", "responsable_id"))
    if cambios:
        partes = []
        if "fecha" in cambios:
            partes.append(f"fecha: {_fmt_fecha(inv.fecha)}")
        if "responsable_id" in cambios:
            partes.append(f"responsable: {inv.responsable.full_name}")
        _evento(db, inv, "Reprogramado", actor, " · ".join(partes) or None)
        db.flush()
    return inv


def marcar_ambiente(
    db: Session, inv: Inventario, ambiente_id: uuid.UUID, data: dict[str, Any], *, actor: User
) -> Inventario:
    """The responsible asesor checks a room. Fixes are allowed until the signatures."""
    if not can_work(actor, inv):
        raise PermissionDeniedError("Solo el responsable o la administración llenan el inventario.")
    if inv.estado in (IE.FIRMADO, IE.CON_NOVEDADES):
        raise ConflictError("El inventario ya está firmado: no se cambia.")
    amb = next((a for a in inv.ambientes if a.id == ambiente_id), None)
    if amb is None:
        raise NotFoundError("Ese ambiente no es de este inventario.")
    # Work out the new values and validate before touching the row.
    estado = data["estado"] if "estado" in data else amb.estado
    if "observacion" in data:
        obs = (data["observacion"] or "").strip() or None
    else:  # «Bueno» clears an old note unless a new one is sent
        obs = None if estado == EstadoAmbiente.BUENO else amb.observacion
    fotos = data["fotos"] if data.get("fotos") is not None else amb.fotos
    if not 0 <= fotos <= 50:
        raise DomainError("Revisa el número de fotos.")
    if estado in (EstadoAmbiente.REGULAR, EstadoAmbiente.MALO) and not obs:
        raise DomainError(f"Escribe qué encontraste en «{amb.nombre}».")
    amb.estado, amb.observacion, amb.fotos = estado, obs, fotos
    if inv.estado == IE.PROGRAMADO and amb.estado is not None:
        inv.estado = IE.REALIZADO
        _evento(db, inv, f"Realizado por {actor.full_name}", actor)
    db.flush()
    return inv


def firmar_inventario(db: Session, inv: Inventario, *, actor: User) -> Inventario:
    ensure_manage(actor, "Registrar las firmas")
    if inv.estado != IE.REALIZADO:
        raise ConflictError(
            "Primero se revisan los ambientes."
            if inv.estado == IE.PROGRAMADO
            else "Las firmas ya están registradas."
        )
    if faltan := [a.nombre for a in inv.ambientes if a.estado is None]:
        raise DomainError("Falta revisar: " + ", ".join(faltan) + ".")
    nov = novedades(inv)
    inv.estado = IE.CON_NOVEDADES if nov else IE.FIRMADO
    inv.firmado_at = fechas.now()
    _evento(
        db,
        inv,
        f"Firmas registradas por {actor.full_name}",
        actor,
        "Firmado por propietario e inquilino"
        + (f" con {len(nov)} novedad{'es' if len(nov) != 1 else ''}." if nov else "."),
    )
    catalogo._event(
        db,
        inv.inmueble,
        f"Inventario {inv.code} firmado" + (" con novedades" if nov else ""),
        actor,
    )
    db.flush()
    return inv


def reparacion_desde_inventario(db: Session, inv: Inventario, *, actor: User) -> Reparacion:
    ensure_manage(actor, "Crear reparaciones")
    nov = novedades(inv)
    if not nov:
        raise DomainError("Este inventario no tiene novedades.")
    if inv.estado == IE.PROGRAMADO:
        raise ConflictError("El inventario aún no se ha realizado.")
    if ya := reparacion_de(db, inv):
        raise ConflictError(f"Ya se creó la reparación {ya.code} con estas novedades.")
    rep = crear_reparacion(
        db,
        {
            "inmueble_id": inv.inmueble_id,
            "titulo": " · ".join(f"{a.nombre}: {a.observacion}" for a in nov)[:500],
            "categoria": CategoriaReparacion.OTRO,
            "prioridad": Prioridad.NORMAL,
            "solicitante": f"Inventario de {'entrega' if inv.tipo == TipoInventario.ENTREGA else 'recepción'} {inv.code}",  # noqa: E501
            "fecha": hoy(),
            "responsable_id": actor.id,
        },
        actor=actor,
        inventario=inv,
    )
    _evento(db, inv, f"Se creó la reparación {rep.code} con las novedades", actor)
    db.flush()
    return rep


def eliminar_inventario(db: Session, inv: Inventario, *, actor: User) -> None:
    ensure_manage(actor, "Eliminar inventarios")
    if inv.estado != IE.PROGRAMADO:
        raise ConflictError("Solo se elimina un inventario programado que aún no se ha hecho.")
    db.delete(inv)
    db.flush()


# ---------------------------------------------------------------- reparaciones


def crear_reparacion(
    db: Session, data: dict[str, Any], *, actor: User, inventario: Inventario | None = None
) -> Reparacion:
    ensure_manage(actor, "Registrar reparaciones")
    inm = _inmueble(db, data.get("inmueble_id"))
    resp = _responsable(db, data.get("responsable_id"))
    if data.get("fecha") is None:
        raise DomainError("Elige la fecha.")
    rep = Reparacion(
        inmueble_id=inm.id,
        titulo=_texto(data.get("titulo"), "Escribe qué hay que reparar."),
        categoria=data["categoria"],
        prioridad=data.get("prioridad") or Prioridad.NORMAL,
        solicitante=(data.get("solicitante") or "").strip() or f"Registrada por {actor.full_name}",
        fecha=data["fecha"],
        estado=ME.RECIBIDA,
        responsable_id=resp.id if resp else actor.id,
        inventario_id=inventario.id if inventario else None,
        created_by_id=actor.id,
    )
    rep.inmueble = inm
    db.add(rep)
    db.flush()
    _evento(
        db,
        rep,
        f"Creada desde el inventario {inventario.code}" if inventario else "Recibida",
        actor,
        "Prioridad urgente." if rep.prioridad == Prioridad.URGENTE else None,
    )
    catalogo._event(db, inm, f"Reparación {rep.code}: {rep.titulo[:120]}", actor)
    db.flush()
    return rep


def actualizar_reparacion(
    db: Session, rep: Reparacion, data: dict[str, Any], *, actor: User
) -> Reparacion:
    ensure_manage(actor, "Editar reparaciones")
    if rep.estado == ME.TERMINADA:
        raise ConflictError("La reparación ya terminó: no se cambia.")
    if "responsable_id" in data:
        _responsable(db, data["responsable_id"])
    if "titulo" in data:
        data["titulo"] = _texto(data["titulo"], "Escribe qué hay que reparar.")
    if "fecha" in data and data["fecha"] is None:
        raise DomainError("Elige la fecha.")
    cambios = _cambios(
        rep, data, ("titulo", "categoria", "prioridad", "fecha", "responsable_id", "solicitante")
    )
    if cambios:
        _evento(db, rep, "Datos actualizados", actor)
        db.flush()
    return rep


def avance_reparacion(
    db: Session, rep: Reparacion, data: dict[str, Any], *, actor: User
) -> Reparacion:
    """«Registrar avance»: provider, quote, who pays, and / or a comment."""
    if not can_work(actor, rep):
        raise PermissionDeniedError("Solo quien sigue la reparación o la administración.")
    if rep.estado == ME.TERMINADA:
        raise ConflictError("La reparación ya terminó.")
    partes = []
    if (prov := (data.get("proveedor") or "").strip()) and prov != rep.proveedor:
        rep.proveedor = prov
        partes.append(prov)
    if (val := data.get("valor")) is not None:
        if val <= 0:
            raise DomainError("El valor debe ser mayor que $0.")
        if val != rep.valor:
            rep.valor = val
            partes.append(_cop(val))
    if (paga := data.get("paga")) is not None and paga != rep.paga:
        rep.paga = paga
        partes.append(f"paga: {PAGA_LABELS[paga].lower()}")
    if com := (data.get("comentario") or "").strip():
        partes.append(com)
    if not partes:
        raise DomainError("Escribe el avance.")
    _evento(db, rep, "Avance", actor, " · ".join(partes))
    db.flush()
    return rep


def estado_reparacion(
    db: Session, rep: Reparacion, estado: EstadoReparacion, *, nota: str | None, actor: User
) -> Reparacion:
    ensure_manage(actor, "Cambiar el estado de una reparación")
    if rep.estado == ME.TERMINADA:
        raise ConflictError("La reparación ya terminó.")
    if estado == rep.estado:
        return rep
    if estado != ME.RECIBIDA and not (rep.proveedor and rep.valor):
        raise DomainError("Registra primero el proveedor y el valor de la cotización.")
    if estado == ME.TERMINADA and rep.paga == PagaReparacion.POR_DEFINIR:
        raise DomainError("Define quién paga antes de terminarla.")
    antes = rep.estado
    rep.estado = estado
    rep.fecha_fin = hoy() if estado == ME.TERMINADA else None
    _evento(
        db, rep, f"{REP_LABELS[antes]} → {REP_LABELS[estado]}", actor, (nota or "").strip() or None
    )
    if estado == ME.TERMINADA:
        catalogo._event(db, rep.inmueble, f"Reparación {rep.code} terminada", actor)
    db.flush()
    return rep


def eliminar_reparacion(db: Session, rep: Reparacion, *, actor: User) -> None:
    ensure_manage(actor, "Eliminar reparaciones")
    if rep.estado != ME.RECIBIDA:
        raise ConflictError("Solo se elimina una reparación recién recibida (sin cotizar).")
    db.delete(rep)
    db.flush()


# ---------------------------------------------------------------- solicitudes


def crear_solicitud(db: Session, data: dict[str, Any], *, actor: User) -> Solicitud:
    ensure_manage(actor, "Registrar solicitudes")
    inm = _inmueble(db, data.get("inmueble_id"))
    resp = _responsable(db, data.get("responsable_id"))
    if data.get("fecha") is None:
        raise DomainError("Elige la fecha.")
    if data["fecha"] > hoy():
        raise DomainError("La fecha de recibido no puede ser futura.")
    sol = Solicitud(
        inmueble_id=inm.id,
        tipo=data["tipo"],
        de=data["de"],
        nombre=(data.get("nombre") or "").strip() or None,
        canal=data["canal"],
        descripcion=_texto(data.get("descripcion"), "Escribe qué pide o de qué se queja."),
        prioridad=data.get("prioridad") or Prioridad.NORMAL,
        fecha=data["fecha"],
        estado=PE.ABIERTA,
        responsable_id=resp.id if resp else actor.id,
        created_by_id=actor.id,
    )
    sol.inmueble = inm
    db.add(sol)
    db.flush()
    _evento(
        db,
        sol,
        f"Recibida por {CANAL_LABELS[sol.canal]}",
        actor,
        f"Registrada por {actor.full_name}.",
    )
    db.flush()
    return sol


def actualizar_solicitud(
    db: Session, sol: Solicitud, data: dict[str, Any], *, actor: User
) -> Solicitud:
    ensure_manage(actor, "Editar solicitudes")
    if sol.estado == PE.CERRADA:
        raise ConflictError("La solicitud está cerrada.")
    if "responsable_id" in data:
        _responsable(db, data["responsable_id"])
    if "descripcion" in data:
        data["descripcion"] = _texto(data["descripcion"], "Escribe qué pide o de qué se queja.")
    if "fecha" in data and (data["fecha"] is None or data["fecha"] > hoy()):
        raise DomainError("Revisa la fecha.")
    cambios = _cambios(
        sol,
        data,
        ("tipo", "de", "nombre", "canal", "descripcion", "prioridad", "fecha", "responsable_id"),
    )
    if cambios:
        _evento(db, sol, "Datos actualizados", actor)
        db.flush()
    return sol


def responder_solicitud(db: Session, sol: Solicitud, respuesta: str, *, actor: User) -> Solicitud:
    if not can_work(actor, sol):
        raise PermissionDeniedError("Solo el responsable o la administración responden.")
    if sol.estado not in (PE.ABIERTA, PE.EN_TRAMITE):
        raise ConflictError("La solicitud ya fue respondida o cerrada.")
    sol.respuesta = _texto(respuesta, "Escribe la respuesta.", 5)
    sol.estado = PE.RESPONDIDA
    sol.fecha_respuesta = hoy()
    sol.respondida_por_id = actor.id
    _evento(db, sol, f"Respondida por {actor.full_name}", actor, sol.respuesta)
    db.flush()
    return sol


def estado_solicitud(
    db: Session, sol: Solicitud, estado: EstadoSolicitud, *, nota: str | None, actor: User
) -> Solicitud:
    """«En trámite» or «Cerrar». «Respondida» is set by answering it."""
    ensure_manage(actor, "Cambiar el estado de una solicitud")
    if sol.estado == PE.CERRADA:
        raise ConflictError("La solicitud ya está cerrada.")
    if estado == PE.RESPONDIDA:
        raise DomainError("Para marcarla «Respondida», envía la respuesta.")
    if estado == PE.ABIERTA:
        raise DomainError("Una solicitud no vuelve a «Abierta».")
    if estado == PE.EN_TRAMITE and sol.estado != PE.ABIERTA:
        raise ConflictError("Solo una solicitud abierta pasa a «En trámite».")
    if estado == sol.estado:
        return sol
    nota = (nota or "").strip() or None
    if estado == PE.CERRADA and sol.estado != PE.RESPONDIDA and not nota:
        raise DomainError("Para cerrarla sin respuesta, escribe el motivo.")
    antes = sol.estado
    sol.estado = estado
    if estado == PE.CERRADA and sol.fecha_respuesta is None:
        sol.fecha_respuesta = hoy()  # the clock stops
    _evento(db, sol, f"{SOL_LABELS[antes]} → {SOL_LABELS[estado]}", actor, nota)
    db.flush()
    return sol


def eliminar_solicitud(db: Session, sol: Solicitud, *, actor: User) -> None:
    ensure_manage(actor, "Eliminar solicitudes")
    if sol.estado != PE.ABIERTA or sol.respuesta:
        raise ConflictError("Solo se elimina una solicitud abierta sin gestión. Ciérrala.")
    db.delete(sol)
    db.flush()
