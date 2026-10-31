"""Captaciones: registration, verification, corrections and publication.

Prototypes K12 (Verificar captaciones) and M15 (Nueva captación); decision «Captaciones ·
registro rápido y verificación» and the later correction rules:
- Two ways to register: «Registro rápido» (negocio, código, dirección) or «Formulario completo».
- A property code can't be registered twice («Inmueble ya registrado»).
- Every captación arrives «Por verificar». Coordinación / Gerencia approve or reject it
  (reasons: código inexistente, or the code doesn't match that address).
- Only approved ones count. A rejected one is corrected in place (code or address must
  change) and goes back to «Por verificar». Approved ones can be marked «Publicada».
- Captadores (Captación activity) see only their own; managers see and manage all.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Captacion, CaptacionEvento, User
from app.models.enums import (
    EstadoCaptacion,
    ModoCaptacion,
    MotivoRechazoCaptacion,
    TipoEventoCaptacion,
    TipoNegocio,
)
from app.services import fechas
from app.services.errors import ConflictError, DomainError, NotFoundError, PermissionDeniedError
from app.services.policies import can_capture, is_manager

E = EstadoCaptacion
MOTIVO_LABELS = {
    MotivoRechazoCaptacion.CODIGO_INEXISTENTE: "código inexistente",
    MotivoRechazoCaptacion.CODIGO_NO_CORRESPONDE: "el código no corresponde a esa dirección",
}
NEGOCIO_LABELS = {TipoNegocio.VENTA: "venta", TipoNegocio.ARRIENDO: "arriendo"}

# Required fields for «Formulario completo» (rápido only needs negocio, código, dirección).
CAMPOS_COMPLETO = (
    "tipo_inmueble",
    "barrio",
    "municipio",
    "precio",
    "propietario_nombre",
    "propietario_telefono",
)
DETAIL_FIELDS = (
    "tipo_inmueble",
    "barrio",
    "municipio",
    "precio",
    "area_m2",
    "habitaciones",
    "banos",
    "parqueadero",
    "propietario_nombre",
    "propietario_telefono",
    "observaciones",
)
_FIELD_LABELS = {
    "negocio": "negocio",
    "codigo_inmueble": "código",
    "direccion": "dirección",
    "tipo_inmueble": "tipo de inmueble",
    "barrio": "barrio",
    "municipio": "municipio",
    "precio": "precio",
    "area_m2": "área",
    "habitaciones": "habitaciones",
    "banos": "baños",
    "parqueadero": "parqueadero",
    "propietario_nombre": "propietario",
    "propietario_telefono": "teléfono del propietario",
    "observaciones": "observaciones",
}


def normalizar_codigo(codigo: str) -> str:
    return " ".join(codigo.split()).upper()


# ---------------------------------------------------------------- access


def get_captacion(db: Session, user: User, captacion_id: uuid.UUID) -> Captacion:
    cap = db.get(Captacion, captacion_id)
    if cap is None or not (is_manager(user) or cap.asesor_id == user.id):
        raise NotFoundError("Captación no encontrada.")
    return cap


def can_edit(user: User, cap: Captacion) -> bool:
    """Managers always; the captador while it isn't approved yet."""
    if is_manager(user):
        return True
    return cap.asesor_id == user.id and cap.estado != E.APROBADA


def _ensure_owner_or_manager(user: User, cap: Captacion) -> None:
    if not (is_manager(user) or cap.asesor_id == user.id):
        raise PermissionDeniedError("Esta captación es de otra persona.")


def _ensure_manager(user: User, msg: str) -> None:
    if not is_manager(user):
        raise PermissionDeniedError(msg)


# ---------------------------------------------------------------- queries


@dataclass(frozen=True)
class CaptacionFilters:
    estados: tuple[EstadoCaptacion, ...] = ()
    asesor_id: uuid.UUID | None = None
    negocio: TipoNegocio | None = None
    publicada: bool | None = None
    desde: date | None = None  # enviada_at, Bogotá days, inclusive
    hasta: date | None = None
    q: str | None = None
    limit: int = 300


def _base(user: User, f: CaptacionFilters):
    stmt = select(Captacion)
    if not is_manager(user):
        stmt = stmt.where(Captacion.asesor_id == user.id)
    if f.asesor_id:
        stmt = stmt.where(Captacion.asesor_id == f.asesor_id)
    if f.negocio:
        stmt = stmt.where(Captacion.negocio == f.negocio)
    if f.publicada is True:
        stmt = stmt.where(Captacion.publicada_at.is_not(None))
    elif f.publicada is False:
        stmt = stmt.where(Captacion.publicada_at.is_(None))
    if f.desde:
        stmt = stmt.where(Captacion.enviada_at >= fechas.start_of_day(f.desde))
    if f.hasta:
        stmt = stmt.where(Captacion.enviada_at < fechas.start_of_day(f.hasta + timedelta(days=1)))
    if f.q and (term := f.q.strip()):
        like = f"%{term}%"
        cond = or_(
            Captacion.codigo_inmueble.ilike(like),
            Captacion.direccion.ilike(like),
            Captacion.barrio.ilike(like),
            Captacion.propietario_nombre.ilike(like),
        )
        digits = term.upper().removeprefix("CAP-").lstrip("0")
        if digits.isdigit():
            cond = cond | (Captacion.numero == int(digits))
        stmt = stmt.where(cond)
    return stmt


def list_captaciones(
    db: Session, user: User, f: CaptacionFilters
) -> tuple[list[Captacion], dict[str, int]]:
    """Matching captaciones (newest first) and counts per estado for the same filters."""
    base = _base(user, f)
    counts = dict.fromkeys([e.value for e in E], 0)
    sub = base.subquery()
    for estado, n in db.execute(select(sub.c.estado, func.count()).group_by(sub.c.estado)):
        counts[E(estado).value] = n
    stmt = base
    if f.estados:
        stmt = stmt.where(Captacion.estado.in_(f.estados))
    order = (
        Captacion.enviada_at.asc()
        if f.estados == (E.POR_VERIFICAR,)
        else Captacion.enviada_at.desc()
    )
    rows = list(db.scalars(stmt.order_by(order).limit(f.limit)).unique())
    return rows, counts


def captadores(db: Session) -> list[User]:
    """People a captación can belong to (active, with Captación)."""
    users = db.scalars(select(User).where(User.is_active).order_by(User.full_name)).unique()
    return [u for u in users if can_capture(u)]


# ---------------------------------------------------------------- helpers


def _event(
    db: Session,
    cap: Captacion,
    tipo: TipoEventoCaptacion,
    titulo: str,
    actor: User | None,
    detalle: str | None = None,
) -> None:
    db.add(
        CaptacionEvento(
            captacion_id=cap.id,
            tipo=tipo,
            titulo=titulo,
            detalle=detalle,
            created_by_id=actor.id if actor else None,
        )
    )


def _ensure_codigo_libre(db: Session, codigo: str, exclude_id: uuid.UUID | None = None) -> None:
    stmt = select(Captacion).where(
        Captacion.codigo_inmueble == codigo, Captacion.estado != E.RECHAZADA
    )
    if exclude_id:
        stmt = stmt.where(Captacion.id != exclude_id)
    if other := db.scalars(stmt).unique().first():
        raise ConflictError(
            f"Inmueble ya registrado: el código {codigo} ya fue captado por "
            f"{other.asesor.full_name} el {fechas.fmt(other.enviada_at)} ({other.code}). "
            "No se puede enviar otra vez. Si crees que es un error, revisa el código."
        )


def _validate_completo(data: Mapping[str, Any]) -> None:
    missing = [_FIELD_LABELS[k] for k in CAMPOS_COMPLETO if data.get(k) in (None, "")]
    if missing:
        raise DomainError("Formulario completo: falta " + ", ".join(missing) + ".")


def _flush_unique(db: Session) -> None:
    """Turn a race on the unique code index into the friendly message."""
    try:
        db.flush()
    except IntegrityError as exc:
        if "uq_captaciones_codigo_vigente" in str(exc.orig):
            raise ConflictError(
                "Inmueble ya registrado: otro asesor acaba de enviar ese código."
            ) from None
        raise


def _gps_valid(gps: Mapping[str, Any] | None) -> bool:
    if not gps:
        return False
    lat, lng = gps.get("lat"), gps.get("lng")
    return lat is not None and lng is not None and -90 <= lat <= 90 and -180 <= lng <= 180


# ---------------------------------------------------------------- commands


def create_captacion(
    db: Session,
    data: Mapping[str, Any],
    *,
    actor: User | None,
    asesor_id: uuid.UUID | None = None,
    gps: Mapping[str, Any] | None = None,
) -> Captacion:
    """Register and send to verification. `actor=None` for scripts (seed)."""
    target_id = asesor_id or (actor.id if actor else None)
    if target_id is None:
        raise DomainError("Falta el asesor de la captación.")
    if actor is not None and target_id != actor.id:
        _ensure_manager(
            actor, "Solo Coordinación o Gerencia registran captaciones de otra persona."
        )
    asesor = db.get(User, target_id)
    if asesor is None or not can_capture(asesor):
        raise DomainError("La captación debe ser de una persona activa con Captación activa.")

    modo = data["modo"]
    if modo == ModoCaptacion.COMPLETO:
        _validate_completo(data)
    codigo = normalizar_codigo(data["codigo_inmueble"])
    _ensure_codigo_libre(db, codigo)

    cap = Captacion(
        negocio=data["negocio"],
        codigo_inmueble=codigo,
        direccion=data["direccion"].strip(),
        modo=modo,
        asesor_id=asesor.id,
        asesor=asesor,
        created_by_id=actor.id if actor else None,
        enviada_at=fechas.now(),
        **{k: data.get(k) for k in DETAIL_FIELDS},
    )
    # GPS only from the captador's own device (a manager registering for someone isn't there).
    if (actor is None or actor.id == asesor.id) and _gps_valid(gps):
        cap.gps_lat = gps["lat"]
        cap.gps_lng = gps["lng"]
        cap.gps_precision_m = gps.get("precision_m")
        cap.gps_at = fechas.now()
    db.add(cap)
    _flush_unique(db)

    modo_txt = "Registro rápido" if modo == ModoCaptacion.RAPIDO else "Formulario completo"
    por = "" if actor is None or actor.id == asesor.id else f" Registrada por {actor.full_name}."
    _event(
        db,
        cap,
        TipoEventoCaptacion.ENVIADA,
        f"Enviada a verificación · {modo_txt}",
        actor or asesor,
        f"{codigo} · {cap.direccion}.{por}",
    )
    db.flush()
    return cap


def update_captacion(
    db: Session, cap: Captacion, changes: Mapping[str, Any], *, actor: User
) -> Captacion:
    """Edit data. The captador can't touch an approved captación; reassign is separate."""
    if not can_edit(actor, cap):
        if cap.asesor_id == actor.id:
            raise PermissionDeniedError(
                "La captación ya está aprobada. Pide a Coordinación cualquier cambio."
            )
        raise PermissionDeniedError("Esta captación es de otra persona.")
    if (
        cap.estado == E.RECHAZADA
        and not is_manager(actor)
        and ("codigo_inmueble" in changes or "direccion" in changes)
    ):
        raise DomainError("Para cambiar el código o la dirección usa «Corregir y volver a enviar».")

    data = dict(changes)
    if "codigo_inmueble" in data:
        data["codigo_inmueble"] = normalizar_codigo(data["codigo_inmueble"])
        if data["codigo_inmueble"] != cap.codigo_inmueble and cap.estado != E.RECHAZADA:
            _ensure_codigo_libre(db, data["codigo_inmueble"], exclude_id=cap.id)
    if "direccion" in data:
        data["direccion"] = data["direccion"].strip()

    changed = [k for k, v in data.items() if hasattr(cap, k) and getattr(cap, k) != v]
    merged = {k: data.get(k, getattr(cap, k)) for k in (*CAMPOS_COMPLETO, "modo")}
    if merged["modo"] == ModoCaptacion.COMPLETO:
        _validate_completo(merged)  # validate before touching the row
    for k in changed:
        setattr(cap, k, data[k])
    if changed:
        _event(
            db,
            cap,
            TipoEventoCaptacion.EDITADA,
            "Datos actualizados",
            actor,
            "Cambió: " + ", ".join(_FIELD_LABELS.get(k, k) for k in changed) + ".",
        )
    _flush_unique(db)
    return cap


def delete_captacion(db: Session, cap: Captacion, *, actor: User) -> None:
    """Managers always; the captador only while it is still «Por verificar» (withdraw it)."""
    if not is_manager(actor):
        if cap.asesor_id != actor.id:
            raise PermissionDeniedError("Esta captación es de otra persona.")
        if cap.estado != E.POR_VERIFICAR:
            raise PermissionDeniedError(
                "Solo puedes retirar una captación que aún está por verificar."
            )
    db.delete(cap)
    db.flush()


def verificar(
    db: Session,
    cap: Captacion,
    estado: EstadoCaptacion,
    *,
    motivo: MotivoRechazoCaptacion | None,
    observacion: str | None,
    actor: User,
) -> Captacion:
    """Approve or reject («Verificar captaciones»). Only from «Por verificar»."""
    _ensure_manager(actor, "Solo Coordinación o Gerencia verifican captaciones.")
    if estado == E.POR_VERIFICAR:
        raise DomainError("Una captación vuelve a «Por verificar» cuando el asesor la corrige.")
    if cap.estado != E.POR_VERIFICAR:
        raise DomainError(
            f"{cap.code} ya fue verificada "
            f"({'aprobada' if cap.estado == E.APROBADA else 'rechazada'})."
        )
    if estado == E.RECHAZADA and motivo is None:
        raise DomainError("Elige el motivo del rechazo.")
    observacion = (observacion or "").strip() or None
    cap.estado = estado
    cap.verificado_por_id = actor.id
    cap.verificado_por = actor
    cap.verificado_at = fechas.now()
    if estado == E.APROBADA:
        cap.motivo_rechazo = None
        cap.observacion_rechazo = None
        _event(
            db,
            cap,
            TipoEventoCaptacion.APROBADA,
            f"Aprobada por {actor.full_name}",
            actor,
            f"Suma una captación de {NEGOCIO_LABELS[cap.negocio]} a {cap.asesor.full_name}.",
        )
        from app.services import inmuebles  # noqa: PLC0415 (inmuebles imports this module)

        db.flush()
        inmuebles.desde_captacion(db, cap, actor)  # it joins the property catalog
    else:
        cap.motivo_rechazo = motivo
        cap.observacion_rechazo = observacion
        detalle = f"Motivo: {MOTIVO_LABELS[motivo]}." + (f" «{observacion}»" if observacion else "")
        _event(
            db,
            cap,
            TipoEventoCaptacion.RECHAZADA,
            f"Rechazada por {actor.full_name}",
            actor,
            detalle + f" {cap.asesor.full_name} debe corregirla y volver a enviarla.",
        )
    db.flush()
    return cap


def reenviar(
    db: Session, cap: Captacion, *, codigo_inmueble: str, direccion: str, actor: User
) -> Captacion:
    """«Corregir y volver a enviar»: same captación, code or address must change."""
    _ensure_owner_or_manager(actor, cap)
    if cap.estado != E.RECHAZADA:
        raise DomainError("Solo se corrige una captación rechazada.")
    codigo = normalizar_codigo(codigo_inmueble)
    direccion = direccion.strip()
    if codigo == cap.codigo_inmueble and direccion == cap.direccion:
        raise DomainError("Cambia el código o la dirección antes de volver a enviar.")
    _ensure_codigo_libre(db, codigo, exclude_id=cap.id)
    antes = f"{cap.codigo_inmueble}, {cap.direccion}"
    cap.codigo_inmueble = codigo
    cap.direccion = direccion
    cap.estado = E.POR_VERIFICAR
    cap.reenvios += 1
    cap.enviada_at = fechas.now()
    cap.verificado_por_id = None
    cap.verificado_por = None
    cap.verificado_at = None
    _flush_unique(db)
    _event(
        db,
        cap,
        TipoEventoCaptacion.REENVIADA,
        "Corregida y reenviada a verificación",
        actor,
        f"Antes: {antes}. Ahora: {codigo}, {direccion}.",
    )
    db.flush()
    return cap


def publicar(db: Session, cap: Captacion, *, actor: User) -> Captacion:
    _ensure_owner_or_manager(actor, cap)
    if cap.estado != E.APROBADA:
        raise DomainError("Solo se marca como publicada una captación aprobada.")
    if cap.publicada_at is None:
        cap.publicada_at = fechas.now()
        _event(db, cap, TipoEventoCaptacion.PUBLICADA, "Marcada como publicada", actor)
        db.flush()
    return cap


def reasignar(db: Session, cap: Captacion, asesor_id: uuid.UUID, *, actor: User) -> Captacion:
    _ensure_manager(actor, "Solo Coordinación o Gerencia reasignan captaciones.")
    if asesor_id == cap.asesor_id:
        return cap
    new = db.get(User, asesor_id)
    if new is None or not can_capture(new):
        raise DomainError("El nuevo responsable debe tener Captación activa.")
    antes = cap.asesor.full_name
    cap.asesor_id = new.id
    cap.asesor = new
    _event(
        db,
        cap,
        TipoEventoCaptacion.REASIGNADA,
        f"Reasignada a {new.full_name}",
        actor,
        f"Antes: {antes}.",
    )
    from app.models import Inmueble  # noqa: PLC0415

    for inm in db.scalars(select(Inmueble).where(Inmueble.captacion_id == cap.id)):
        inm.captador_id = new.id
    db.flush()
    return cap


def aprobacion_pct(counts: Mapping[str, int]) -> int | None:
    """% approved of the verified ones (K12-ger «% de aprobación»)."""
    verified = counts.get(E.APROBADA.value, 0) + counts.get(E.RECHAZADA.value, 0)
    return round(100 * counts.get(E.APROBADA.value, 0) / verified) if verified else None
