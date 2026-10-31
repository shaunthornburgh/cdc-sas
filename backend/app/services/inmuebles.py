"""Inmuebles: the property catalog.

Rules (the prototypes have no catalog screen, so these are documented simplifications):

* **Where they come from**: every captación approved by Coordinación becomes (or updates) the
  property with the same code, keeping the link and the captador. Coordinación and Gerencia can
  also register one by hand (e.g. properties the company already handled before the system).
  A quick captación (only code and address) creates a property with «datos incompletos».
* **Status**: disponible → separado → arrendado / vendido, or retirado. Only «disponible»
  properties are offered to clients («Enviar opciones»). Coordinación and Gerencia change it.
* **Who**: asesores, Atención y Preventa, the Auxiliar, Coordinación and Gerencia see the catalog.
  The owner's name and phone are only for Coordinación, Gerencia, the Auxiliar and the captador.
  The captador can complete the data of the properties they captured; everything else is for
  Coordinación and Gerencia. A property linked to a captación isn't deleted: it's «retirado».
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Captacion,
    Inmueble,
    InmuebleEvento,
    Inventario,
    Lead,
    LeadEvento,
    Reparacion,
    Solicitud,
    User,
)
from app.models.enums import (
    Cargo,
    EstadoCaptacion,
    EstadoInmueble,
    TipoEventoLead,
    TipoInmueble,
    TipoNegocio,
)
from app.services import fechas
from app.services.captaciones import normalizar_codigo
from app.services.errors import ConflictError, DomainError, NotFoundError, PermissionDeniedError
from app.services.pedidos import RANGOS, ZONAS
from app.services.policies import LEAD_FUNCIONES, has_commercial_activity, is_manager

S = EstadoInmueble
ESTADO_LABELS = {
    S.DISPONIBLE: "Disponible",
    S.SEPARADO: "Separado",
    S.ARRENDADO: "Arrendado",
    S.VENDIDO: "Vendido",
    S.RETIRADO: "Retirado",
}
TIPO_LABELS = {
    TipoInmueble.APARTAMENTO: "Apto",
    TipoInmueble.CASA: "Casa",
    TipoInmueble.LOCAL: "Local",
    TipoInmueble.OFICINA: "Oficina",
    TipoInmueble.LOTE: "Lote",
    TipoInmueble.BODEGA: "Bodega",
}
SIN_HABITACIONES = (
    TipoInmueble.LOCAL,
    TipoInmueble.LOTE,
    TipoInmueble.BODEGA,
    TipoInmueble.OFICINA,
)
EDITABLES = (
    "tipo_inmueble",
    "direccion",
    "zona",
    "barrio",
    "municipio",
    "precio",
    "administracion",
    "area_m2",
    "habitaciones",
    "banos",
    "parqueadero",
    "estrato",
    "descripcion",
    "propietario_nombre",
    "propietario_telefono",
)
CAMPO_LABELS = {
    "tipo_inmueble": "tipo",
    "direccion": "dirección",
    "zona": "zona",
    "barrio": "barrio",
    "municipio": "municipio",
    "precio": "precio",
    "administracion": "administración",
    "area_m2": "área",
    "habitaciones": "habitaciones",
    "banos": "baños",
    "parqueadero": "parqueadero",
    "estrato": "estrato",
    "descripcion": "descripción",
    "propietario_nombre": "propietario",
    "propietario_telefono": "teléfono del propietario",
    "negocio": "negocio",
    "codigo": "código",
}


# ---------------------------------------------------------------- access


def can_view(user: User) -> bool:
    return (
        is_manager(user)
        or user.cargo == Cargo.AUXILIAR_ADMINISTRATIVA
        or user.funcion in LEAD_FUNCIONES
        or has_commercial_activity(user)
    )


def ensure_view(user: User) -> None:
    if not can_view(user):
        raise PermissionDeniedError("No tienes acceso a los inmuebles.")


def can_edit(user: User, inm: Inmueble) -> bool:
    return is_manager(user) or (inm.captador_id is not None and inm.captador_id == user.id)


def ve_propietario(user: User, inm: Inmueble) -> bool:
    return (
        is_manager(user)
        or user.cargo == Cargo.AUXILIAR_ADMINISTRATIVA
        or (inm.captador_id is not None and inm.captador_id == user.id)
    )


def get_inmueble(db: Session, user: User, inmueble_id: uuid.UUID) -> Inmueble:
    ensure_view(user)
    inm = db.get(Inmueble, inmueble_id)
    if inm is None:
        raise NotFoundError("Ese inmueble no existe.")
    return inm


# ---------------------------------------------------------------- helpers


def titulo(inm: Inmueble) -> str:
    """«Apto Belén» (X14 style)."""
    tipo = TIPO_LABELS.get(inm.tipo_inmueble, "Inmueble") if inm.tipo_inmueble else "Inmueble"
    lugar = (
        inm.zona if inm.zona and inm.zona != "Otra zona" else (inm.barrio or inm.municipio or "")
    )
    return f"{tipo} {lugar}".strip()


def faltantes(inm: Inmueble) -> list[str]:
    """What's missing to offer it well («datos incompletos»)."""
    out = []
    if inm.tipo_inmueble is None:
        out.append("tipo")
    if not inm.zona:
        out.append("zona")
    if not inm.precio:
        out.append("precio")
    if not inm.area_m2:
        out.append("área")
    if inm.tipo_inmueble not in SIN_HABITACIONES and inm.habitaciones is None:
        out.append("habitaciones")
    if not inm.propietario_nombre:
        out.append("propietario")
    return out


def zona_de(*lugares: str | None, direccion: str | None = None) -> str | None:
    """Barrio / municipio that is one of the zones; else a zone named in the address."""
    zonas = [z for z in ZONAS if z != "Otra zona"]
    for x in lugares:
        for z in zonas:
            if x and x.strip().lower() == z.lower():
                return z
    texto = (direccion or "").lower()
    return next((z for z in zonas if z.lower() in texto), None)


def _event(db: Session, inm: Inmueble, titulo_: str, actor: User | None, detalle=None, datos=None):
    db.add(
        InmuebleEvento(
            inmueble_id=inm.id,
            titulo=titulo_,
            detalle=detalle,
            datos=datos or {},
            created_by_id=actor.id if actor else None,
        )
    )


def _fmt(k: str, v: Any) -> str:
    if v is None or v == "":
        return "—"
    if k in ("precio", "administracion"):
        return "$" + f"{int(v):,}".replace(",", ".")
    if k == "parqueadero":
        return "sí" if v else "no"
    if k == "tipo_inmueble":
        return TIPO_LABELS.get(TipoInmueble(v), str(v))
    return str(v)


def _validate(data: dict[str, Any]) -> None:
    if "direccion" in data and len((data["direccion"] or "").strip()) < 5:
        raise DomainError("Escribe la dirección.")
    if data.get("zona") and data["zona"] not in ZONAS:
        raise DomainError("Elige una zona de la lista.")
    for k in ("precio", "administracion"):
        if data.get(k) is not None and data[k] < 0:
            raise DomainError("Los valores no pueden ser negativos.")
    if data.get("precio") == 0:
        raise DomainError("El precio debe ser mayor que $0.")
    if data.get("area_m2") is not None and data["area_m2"] <= 0:
        raise DomainError("El área debe ser mayor que 0.")
    for k, hi in (("habitaciones", 30), ("banos", 30), ("estrato", 6)):
        v = data.get(k)
        if v is not None and not (0 <= v <= hi) or (k == "estrato" and v == 0):
            raise DomainError(f"Revisa {CAMPO_LABELS[k]}.")


# ---------------------------------------------------------------- captaciones → inmuebles


def desde_captacion(db: Session, cap: Captacion, actor: User | None) -> Inmueble:
    """An approved captación creates its property, or fills the gaps of an existing one."""
    codigo = normalizar_codigo(cap.codigo_inmueble)
    inm = db.scalar(select(Inmueble).where(Inmueble.codigo == codigo))
    datos = {
        "tipo_inmueble": cap.tipo_inmueble,
        "direccion": cap.direccion,
        "zona": zona_de(cap.barrio, cap.municipio, direccion=cap.direccion),
        "barrio": cap.barrio,
        "municipio": cap.municipio,
        "precio": cap.precio,
        "area_m2": cap.area_m2,
        "habitaciones": cap.habitaciones,
        "banos": cap.banos,
        "parqueadero": cap.parqueadero,
        "descripcion": cap.observaciones,
        "propietario_nombre": cap.propietario_nombre,
        "propietario_telefono": cap.propietario_telefono,
    }
    if inm is None:
        inm = Inmueble(
            codigo=codigo,
            negocio=cap.negocio,
            captacion_id=cap.id,
            captador_id=cap.asesor_id,
            created_by_id=actor.id if actor else None,
            estado=S.DISPONIBLE,
            estado_at=fechas.now(),
            **datos,
        )
        db.add(inm)
        db.flush()
        _event(
            db,
            inm,
            f"Registrado desde la captación {cap.code} aprobada",
            actor,
            f"Lo captó {cap.asesor.full_name}.",
        )
    else:
        llenos = []
        for k, v in datos.items():
            if v is not None and getattr(inm, k) in (None, ""):
                setattr(inm, k, v)
                llenos.append(CAMPO_LABELS[k])
        if inm.captacion_id is None:
            inm.captacion_id = cap.id
            inm.captador_id = cap.asesor_id
        _event(
            db,
            inm,
            f"Vinculado a la captación {cap.code} aprobada",
            actor,
            "Completó: " + ", ".join(llenos) + "." if llenos else None,
        )
    db.flush()
    return inm


def sincronizar_captaciones(db: Session) -> int:
    """Approved captaciones that don't have their property yet (older data, seeds)."""
    linked = select(Inmueble.captacion_id).where(Inmueble.captacion_id.is_not(None))
    caps = db.scalars(
        select(Captacion).where(
            Captacion.estado == EstadoCaptacion.APROBADA, Captacion.id.not_in(linked)
        )
    ).unique()
    n = 0
    for cap in caps:
        desde_captacion(db, cap, cap.verificado_por)
        n += 1
    return n


# ---------------------------------------------------------------- list & KPIs


@dataclass
class Filtros:
    vista: str = "todos"  # todos · mios (captador)
    estado: str | None = None  # an EstadoInmueble value, «vigentes» (not withdrawn) or None (all)
    negocio: TipoNegocio | None = None
    tipo: TipoInmueble | None = None
    zona: str | None = None
    rango: str | None = None
    precio_min: int | None = None
    precio_max: int | None = None
    habitaciones: int | None = None  # at least
    incompletos: bool = False
    q: str | None = None


def _base(user: User, f: Filtros) -> Select:
    q = select(Inmueble)
    if f.vista == "mios":
        q = q.where(Inmueble.captador_id == user.id)
    if f.estado == "vigentes":
        q = q.where(Inmueble.estado != S.RETIRADO)
    elif f.estado:
        try:
            q = q.where(Inmueble.estado == S(f.estado))
        except ValueError:
            raise DomainError("Estado no válido.") from None
    if f.negocio:
        q = q.where(Inmueble.negocio == f.negocio)
    if f.tipo:
        q = q.where(Inmueble.tipo_inmueble == f.tipo)
    if f.zona:
        q = q.where(Inmueble.zona == f.zona)
    if f.rango:
        if f.rango not in RANGOS:
            raise DomainError("Rango de precio no válido.")
        neg, lo, hi = RANGOS[f.rango]
        q = q.where(Inmueble.negocio == neg, Inmueble.precio >= lo)
        if hi is not None:
            q = q.where(Inmueble.precio <= hi)
    if f.precio_min is not None:
        q = q.where(Inmueble.precio >= f.precio_min)
    if f.precio_max is not None:
        q = q.where(Inmueble.precio <= f.precio_max)
    if f.habitaciones:
        q = q.where(Inmueble.habitaciones >= f.habitaciones)
    if f.q and (t := f.q.strip()):
        like = f"%{t}%"
        q = q.where(
            or_(
                Inmueble.codigo.ilike(like),
                Inmueble.direccion.ilike(like),
                Inmueble.barrio.ilike(like),
                Inmueble.municipio.ilike(like),
                Inmueble.zona.ilike(like),
            )
        )
    return q


def list_inmuebles(db: Session, user: User, f: Filtros) -> list[Inmueble]:
    ensure_view(user)
    rows = list(
        db.scalars(_base(user, f).order_by(Inmueble.estado_at.desc(), Inmueble.codigo)).unique()
    )
    if f.incompletos:
        rows = [i for i in rows if faltantes(i)]
    return rows


def kpis(db: Session, user: User) -> dict[str, int]:
    ensure_view(user)
    month_start = fechas.start_of_day(fechas.local_date(fechas.now()).replace(day=1))

    def n(*conds) -> int:
        return db.scalar(select(func.count()).select_from(Inmueble).where(*conds)) or 0

    todos = list(db.scalars(select(Inmueble).where(Inmueble.estado != S.RETIRADO)).unique())
    return {
        "disponibles": n(Inmueble.estado == S.DISPONIBLE),
        "arriendo": n(Inmueble.estado == S.DISPONIBLE, Inmueble.negocio == TipoNegocio.ARRIENDO),
        "venta": n(Inmueble.estado == S.DISPONIBLE, Inmueble.negocio == TipoNegocio.VENTA),
        "separados": n(Inmueble.estado == S.SEPARADO),
        "cerrados_mes": n(
            Inmueble.estado.in_((S.ARRENDADO, S.VENDIDO)), Inmueble.estado_at >= month_start
        ),
        "incompletos": sum(1 for i in todos if faltantes(i)),
        "mios": n(Inmueble.captador_id == user.id),
    }


# ---------------------------------------------------------------- commands


def crear(db: Session, data: dict[str, Any], *, actor: User) -> Inmueble:
    if not is_manager(actor):
        raise PermissionDeniedError(
            "Los inmuebles los registran Coordinación y Gerencia. Si captaste uno, regístralo en "
            "«Nueva captación»: al aprobarse queda en el catálogo."
        )
    codigo = normalizar_codigo(data.get("codigo") or "")
    if len(codigo) < 3:
        raise DomainError("Escribe el código del inmueble.")
    if db.scalar(select(Inmueble.id).where(Inmueble.codigo == codigo)):
        raise ConflictError(f"El inmueble {codigo} ya está registrado.")
    pend = db.scalar(
        select(Captacion).where(
            func.upper(Captacion.codigo_inmueble) == codigo,
            Captacion.estado == EstadoCaptacion.POR_VERIFICAR,
        )
    )
    if pend is not None:
        raise ConflictError(
            f"Hay una captación por verificar con ese código ({pend.code}): al aprobarla se crea."
        )
    campos = {k: data.get(k) for k in EDITABLES if k in data}
    _validate(campos | {"direccion": data.get("direccion")})
    inm = Inmueble(
        codigo=codigo,
        negocio=data["negocio"],
        created_by_id=actor.id,
        estado=S.DISPONIBLE,
        estado_at=fechas.now(),
        **campos,
    )
    db.add(inm)
    db.flush()
    _event(db, inm, f"Registrado a mano por {actor.full_name}", actor)
    db.flush()
    return inm


def actualizar(db: Session, inm: Inmueble, changes: dict[str, Any], *, actor: User) -> Inmueble:
    if not can_edit(actor, inm):
        raise PermissionDeniedError(
            "Solo Coordinación, Gerencia o quien captó el inmueble pueden cambiar sus datos."
        )
    manager = is_manager(actor)
    if not manager and ({"negocio", "codigo"} & set(changes)):
        raise PermissionDeniedError(
            "El código y el tipo de negocio los cambian Coordinación o Gerencia."
        )
    permitidos = set(EDITABLES) | ({"negocio", "codigo"} if manager else set())
    if extra := set(changes) - permitidos:
        raise DomainError(f"No se puede cambiar «{sorted(extra)[0]}».")
    _validate(changes)
    if "codigo" in changes:
        nuevo = normalizar_codigo(changes["codigo"] or "")
        if len(nuevo) < 3:
            raise DomainError("Escribe el código del inmueble.")
        if nuevo != inm.codigo and db.scalar(select(Inmueble.id).where(Inmueble.codigo == nuevo)):
            raise ConflictError(f"El inmueble {nuevo} ya está registrado.")
        changes["codigo"] = nuevo
    antes, despues = {}, {}
    for k, v in changes.items():
        cur = getattr(inm, k)
        if isinstance(cur, Decimal) and v is not None:
            v = Decimal(str(v))
        if isinstance(v, str):
            v = v.strip() or None
        if cur != v:
            antes[k], despues[k] = cur, v
            setattr(inm, k, v)
    if not despues:
        return inm
    _event(
        db,
        inm,
        "Datos actualizados",
        actor,
        " · ".join(
            f"{CAMPO_LABELS[k]}: {_fmt(k, antes[k])} → {_fmt(k, despues[k])}" for k in despues
        ),
        {
            "antes": {k: _json(v) for k, v in antes.items()},
            "despues": {k: _json(v) for k, v in despues.items()},
        },
    )
    db.flush()
    return inm


def _json(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if hasattr(v, "value"):
        return v.value
    return v


def cambiar_estado(
    db: Session, inm: Inmueble, estado: EstadoInmueble, *, nota: str | None, actor: User
) -> Inmueble:
    if not is_manager(actor):
        raise PermissionDeniedError("El estado del inmueble lo cambian Coordinación o Gerencia.")
    if estado == inm.estado:
        return inm
    if estado == S.ARRENDADO and inm.negocio == TipoNegocio.VENTA:
        raise DomainError("Un inmueble en venta se marca «Vendido», no «Arrendado».")
    if estado == S.VENDIDO and inm.negocio == TipoNegocio.ARRIENDO:
        raise DomainError("Un inmueble en arriendo se marca «Arrendado», no «Vendido».")
    nota = (nota or "").strip() or None
    if estado in (S.SEPARADO, S.RETIRADO) and not nota:
        raise DomainError("Escribe el motivo (quién lo separó o por qué se retira).")
    antes = inm.estado
    inm.estado = estado
    inm.estado_at = fechas.now()
    _event(
        db,
        inm,
        f"{ESTADO_LABELS[antes]} → {ESTADO_LABELS[estado]}",
        actor,
        nota,
        {"antes": antes.value, "despues": estado.value},
    )
    db.flush()
    return inm


def eliminar(db: Session, inm: Inmueble, *, actor: User) -> None:
    if not is_manager(actor):
        raise PermissionDeniedError("Solo Coordinación o Gerencia eliminan inmuebles.")
    if inm.captacion_id is not None:
        raise ConflictError(
            "Este inmueble viene de una captación aprobada: no se elimina, márcalo «Retirado»."
        )
    if db.scalar(
        select(LeadEvento.id)
        .where(LeadEvento.datos["inmuebles"].astext.contains(inm.codigo))
        .limit(1)
    ):
        raise ConflictError("Ya se envió como opción a un cliente: márcalo «Retirado».")
    if any(
        db.scalar(select(m.id).where(m.inmueble_id == inm.id).limit(1))
        for m in (Inventario, Reparacion, Solicitud)
    ):
        raise ConflictError(
            "Tiene inventarios, reparaciones o solicitudes registrados: márcalo «Retirado»."
        )
    db.delete(inm)
    db.flush()


# ---------------------------------------------------------------- «Enviar opciones» (C02)


def enviados_al_lead(db: Session, lead: Lead) -> set[str]:
    codes: set[str] = set()
    for datos in db.scalars(
        select(LeadEvento.datos).where(
            LeadEvento.lead_id == lead.id, LeadEvento.tipo == TipoEventoLead.OPCIONES
        )
    ):
        codes.update((datos or {}).get("inmuebles", []))
    return codes


def opciones_para_lead(db: Session, user: User, lead: Lead) -> list[tuple[Inmueble, bool]]:
    """Available properties for the lead's business type, flagging those already sent."""
    ensure_view(user)
    q = select(Inmueble).where(Inmueble.estado == S.DISPONIBLE)
    if lead.negocio:
        q = q.where(Inmueble.negocio == lead.negocio)
    ya = enviados_al_lead(db, lead)
    rows = list(db.scalars(q.order_by(Inmueble.codigo)).unique())
    if lead.zona:  # the lead's zone first
        z = lead.zona.lower()
        rows.sort(
            key=lambda i: 0 if (i.zona or "").lower() in z or z in (i.zona or "").lower() else 1
        )
    return [(i, i.codigo in ya) for i in rows]


def para_enviar(db: Session, ids: list[uuid.UUID]) -> list[Inmueble]:
    """Validate the properties picked in «Enviar opciones»."""
    out = []
    for i in dict.fromkeys(ids):
        inm = db.get(Inmueble, i)
        if inm is None:
            raise DomainError("Uno de los inmuebles elegidos no existe.")
        if inm.estado != S.DISPONIBLE:
            raise DomainError(
                f"{inm.codigo} está {ESTADO_LABELS[inm.estado].lower()}: no se puede ofrecer."
            )
        out.append(inm)
    return out


def registrar_envio(db: Session, inms: list[Inmueble], lead: Lead, medio: str, actor: User) -> None:
    for inm in inms:
        _event(
            db, inm, f"Enviado como opción a {lead.code} · {lead.full_name}", actor, f"Por {medio}."
        )
