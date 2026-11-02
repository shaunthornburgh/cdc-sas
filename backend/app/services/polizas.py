"""Pólizas (prototype X11; decisions G-087, G-075, G-072, G-084, G-034, F-020).

* **Who**: the Auxiliar administrativa and Gerencia see and manage the page. «Comparar pólizas» is
  only for Gerencia. Everyone else gets 403.
* **Only rentals** carry a policy (G-035): a policy hangs from a closed rental deal (NEG-…) and/or
  a rental property, or a short description for older contracts.
* **Flow**: registrar (en estudio, with the insurer's filing number) → aprobada / negada. A denied
  study can be retaken once more with a reason (G-084); if the second study is approved, the policy
  counts as «recuperada». Approved → contract signed → «Activar póliza» (date and policy number)
  within the insurer's deadline (G-087: days from the signature, warn N days before). Active →
  terminada when the contract ends.
* **Alerts** (G-087): approved policies with a signed contract and not yet active. «Por vencer»
  when the warning days are reached, «Vencida» after the deadline. The Auxiliar gets both in
  Avisos; Gerencia only the expired ones. The asesor who closed the deal is told when the policy
  is approved (G-034).
* **Cost**: canon × price of the policy (% of the rent), every month. The company pays it (F-020).
* **Insurers** (G-075, G-087): added by Gerencia or the Auxiliar with their first policy; can be
  deactivated; deleted only when no policy uses them (G-087's proposed rule), keeping who deleted
  them and when. Every change is a `PolizaEvento`, shown in «Registro de cambios».
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Aseguradora, Cierre, Inmueble, Lead, Poliza, PolizaEvento, PolizaTipo, User
from app.models.enums import Cargo, EstadoCierre, TipoNegocio
from app.services import fechas
from app.services.errors import ConflictError, DomainError, NotFoundError, PermissionDeniedError

COBERTURAS = {
    "can": "Canon",
    "adm": "Administración",
    "ser": "Servicios públicos",
    "dan": "Daños al inmueble",
    "jur": "Gastos jurídicos",
}
ESTADOS = {
    "en_estudio": ("En estudio", "pend"),
    "aprobada": ("Aprobada", "ok"),
    "negada": ("Negada", "bad"),
    "activa": ("Activa", "ok"),
    "terminada": ("Terminada", "gray"),
}
MAX_ESTUDIOS = 2  # the first study and one «Retomar el estudio»


# ---------------------------------------------------------------- access


def puede_ver(user: User) -> bool:
    return user.is_active and user.cargo in (Cargo.GERENCIA, Cargo.AUXILIAR_ADMINISTRATIVA)


def ensure(user: User) -> None:
    if not puede_ver(user):
        raise PermissionDeniedError(
            "Las pólizas las manejan la Auxiliar administrativa y Gerencia."
        )


def ensure_gerencia(user: User) -> None:
    if not (user.is_active and user.cargo == Cargo.GERENCIA):
        raise PermissionDeniedError("El comparador de pólizas es solo para Gerencia.")


def _cop(v: float | int | None) -> str:
    return "—" if v is None else "$" + f"{round(v):,}".replace(",", ".")


def _pct(v: Decimal | float) -> str:
    return f"{float(v):.1f}".replace(".", ",") + " %"


def _fd(d: date | None) -> str:
    if d is None:
        return "—"
    m = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    return f"{d.day} {m[d.month - 1]} {d.year}"


def hoy() -> date:
    return fechas.local_date(fechas.now())


def _evento(
    db: Session,
    actor: User,
    accion: str,
    registro: str,
    *,
    poliza: Poliza | None = None,
    aseguradora: Aseguradora | None = None,
    antes: Any = None,
    despues: Any = None,
) -> None:
    db.add(
        PolizaEvento(
            poliza_id=poliza.id if poliza else None,
            aseguradora_id=aseguradora.id if aseguradora else None,
            registro=registro[:200],
            accion=accion,
            antes=None if antes is None else str(antes)[:300],
            despues=None if despues is None else str(despues)[:300],
            actor_id=actor.id,
        )
    )


# ---------------------------------------------------------------- insurers


def aseguradoras(db: Session, *, incluir_eliminadas: bool = False) -> list[Aseguradora]:
    q = select(Aseguradora).order_by(Aseguradora.created_at, Aseguradora.nombre)
    if not incluir_eliminadas:
        q = q.where(Aseguradora.eliminada_at.is_(None))
    return list(db.scalars(q).unique())


def get_aseguradora(db: Session, user: User, id_: uuid.UUID) -> Aseguradora:
    ensure(user)
    a = db.get(Aseguradora, id_)
    if a is None or a.eliminada_at is not None:
        raise NotFoundError("Esa aseguradora no existe.")
    return a


def _n_polizas(db: Session, a: Aseguradora) -> int:
    return (
        db.scalar(
            select(func.count()).where(Poliza.aseguradora_id == a.id, Poliza.eliminada_at.is_(None))
        )
        or 0
    )


def _plazos(dias_max: Any, aviso: Any) -> tuple[int, int]:
    try:
        dm = int(dias_max)
        av = 10 if aviso in (None, "") else int(aviso)
    except (TypeError, ValueError) as e:
        raise DomainError("Revisa los días para activar y los días de aviso.") from e
    if not 1 <= dm <= 365:
        raise DomainError("Los días máximos para activar deben estar entre 1 y 365.")
    if not 0 <= av <= dm:
        raise DomainError("Los días de aviso no pueden ser mayores que el plazo para activar.")
    return dm, av


def _tipo_datos(data: dict[str, Any]) -> dict[str, Any]:
    nombre = (data.get("nombre") or "").strip()
    if len(nombre) < 2:
        raise DomainError("Escribe el nombre o tipo de póliza.")
    try:
        pct = Decimal(str(data.get("precio_pct")).replace(",", "."))
    except Exception as e:  # noqa: BLE001 - any bad number
        raise DomainError("El precio de la póliza debe ser un porcentaje mayor que 0.") from e
    if not Decimal("0") < pct <= Decimal("20"):
        raise DomainError("El precio de la póliza debe ser un porcentaje mayor que 0.")
    est = int(data.get("costo_estudio") or 0)
    resp = data.get("dias_respuesta")
    if est < 0 or (resp is not None and not 0 <= int(resp) <= 60):
        raise DomainError("Revisa el costo del estudio y los días de respuesta.")
    cob = [c for c in (data.get("coberturas") or []) if c in COBERTURAS] or ["can"]
    return {
        "nombre": nombre[:120],
        "precio_pct": pct,
        "costo_estudio": est,
        "dias_respuesta": None if resp is None else int(resp),
        "coberturas": list(dict.fromkeys(cob)),
    }


def crear_aseguradora(db: Session, data: dict[str, Any], *, actor: User) -> Aseguradora:
    """G-075 «+ Agregar aseguradora», with the first policy it offers."""
    ensure(actor)
    nombre = (data.get("nombre") or "").strip()
    if len(nombre) < 2:
        raise DomainError("Escribe el nombre de la aseguradora.")
    existe = db.scalar(
        select(Aseguradora.id).where(
            func.lower(Aseguradora.nombre) == nombre.lower(), Aseguradora.eliminada_at.is_(None)
        )
    )
    if existe:
        raise ConflictError("Ya existe una aseguradora con ese nombre.")
    dm, av = _plazos(data.get("dias_max"), data.get("aviso_dias"))
    tipo = _tipo_datos(data.get("poliza") or {})
    a = Aseguradora(
        nombre=nombre[:120],
        nit=(data.get("nit") or "").strip()[:40] or None,
        contacto=(data.get("contacto") or "").strip()[:120] or None,
        telefono=(data.get("telefono") or "").strip()[:200] or None,
        dias_max=dm,
        aviso_dias=av,
        created_by_id=actor.id,
    )
    db.add(a)
    db.flush()
    db.add(PolizaTipo(aseguradora_id=a.id, created_by_id=actor.id, **tipo))
    _evento(
        db,
        actor,
        "Agregó la aseguradora",
        a.nombre,
        aseguradora=a,
        despues=f"{tipo['nombre']} · {_pct(tipo['precio_pct'])} del canon · activar en {dm} días",
    )
    db.flush()
    db.refresh(a)
    return a


def agregar_tipo(db: Session, a: Aseguradora, data: dict[str, Any], *, actor: User) -> PolizaTipo:
    ensure(actor)
    datos = _tipo_datos(data)
    if any(t.nombre.lower() == datos["nombre"].lower() for t in a.productos):
        raise ConflictError(f"{a.nombre} ya tiene la póliza «{datos['nombre']}».")
    t = PolizaTipo(aseguradora_id=a.id, created_by_id=actor.id, **datos)
    db.add(t)
    _evento(
        db,
        actor,
        "Agregó una póliza",
        a.nombre,
        aseguradora=a,
        despues=f"{datos['nombre']} · {_pct(datos['precio_pct'])} del canon",
    )
    db.flush()
    db.refresh(a)
    return t


def editar_aseguradora(
    db: Session, a: Aseguradora, data: dict[str, Any], *, actor: User
) -> Aseguradora:
    """Deadline and warning days (X11 «Plazo máximo para activar»), contact data, active flag."""
    ensure(actor)
    if "dias_max" in data or "aviso_dias" in data:
        dm, av = _plazos(data.get("dias_max", a.dias_max), data.get("aviso_dias", a.aviso_dias))
        if (dm, av) != (a.dias_max, a.aviso_dias):
            _evento(
                db,
                actor,
                "Cambió el plazo para activar",
                a.nombre,
                aseguradora=a,
                antes=f"{a.dias_max} días · aviso {a.aviso_dias} antes",
                despues=f"{dm} días · aviso {av} antes",
            )
            a.dias_max, a.aviso_dias = dm, av
    for k, label, n in (
        ("nit", "NIT", 40),
        ("contacto", "Contacto", 120),
        ("telefono", "Teléfono o correo", 200),
    ):
        if k in data:
            v = (data[k] or "").strip()[:n] or None
            if v != getattr(a, k):
                _evento(
                    db,
                    actor,
                    f"Cambió {label}",
                    a.nombre,
                    aseguradora=a,
                    antes=getattr(a, k),
                    despues=v,
                )
                setattr(a, k, v)
    if "activa" in data and bool(data["activa"]) != a.activa:
        a.activa = bool(data["activa"])
        _evento(
            db,
            actor,
            "Activó la aseguradora" if a.activa else "Desactivó la aseguradora",
            a.nombre,
            aseguradora=a,
            despues="Activa" if a.activa else "Inactiva: no aparece en pólizas nuevas",
        )
    db.flush()
    return a


def eliminar_aseguradora(db: Session, a: Aseguradora, *, actor: User) -> None:
    """G-087: an insurer used by any policy can't be deleted, only deactivated."""
    ensure(actor)
    if n := _n_polizas(db, a):
        raise ConflictError(
            f"{a.nombre} tiene {n} póliza{'s' if n != 1 else ''}: no se puede eliminar para no "
            "perder su historial. Puedes desactivarla."
        )
    a.eliminada_at, a.eliminada_por_id, a.activa = fechas.now(), actor.id, False
    _evento(
        db,
        actor,
        "Eliminó la aseguradora",
        a.nombre,
        aseguradora=a,
        antes="Activa",
        despues="Eliminada",
    )
    db.flush()


def aseguradoras_vista(db: Session, user: User) -> dict[str, Any]:
    ensure(user)
    todas = aseguradoras(db, incluir_eliminadas=True)
    uso = dict(
        db.execute(
            select(Poliza.aseguradora_id, func.count())
            .where(Poliza.eliminada_at.is_(None))
            .group_by(Poliza.aseguradora_id)
        ).all()
    )
    vivas = [a for a in todas if a.eliminada_at is None]

    def _tipo(t: PolizaTipo) -> dict[str, Any]:
        return {
            "id": t.id,
            "nombre": t.nombre,
            "precio_pct": float(t.precio_pct),
            "costo_estudio": t.costo_estudio,
            "dias_respuesta": t.dias_respuesta,
            "coberturas": t.coberturas,
        }

    return {
        "items": [
            {
                "id": a.id,
                "nombre": a.nombre,
                "nit": a.nit,
                "contacto": a.contacto,
                "telefono": a.telefono,
                "activa": a.activa,
                "dias_max": a.dias_max,
                "aviso_dias": a.aviso_dias,
                "ejemplo": a.ejemplo,
                "polizas": uso.get(a.id, 0),
                "puede_eliminar": uso.get(a.id, 0) == 0,
                "agregada": (
                    f"{a.created_by.full_name} · {fechas.fmt(a.created_at)}"
                    if a.created_by
                    else "Datos de ejemplo"
                ),
                "tipos": [_tipo(t) for t in a.productos],
            }
            for a in vivas
        ],
        "eliminadas": [
            {
                "nombre": a.nombre,
                "txt": f"Eliminada el {fechas.fmt(a.eliminada_at)} por "
                f"{a.eliminada_por.full_name if a.eliminada_por else '—'}"
                + (f" · la había agregado {a.created_by.full_name}" if a.created_by else ""),
            }
            for a in todas
            if a.eliminada_at is not None
        ],
        "coberturas": COBERTURAS,
        "historial": [
            {
                "accion": e.accion,
                "registro": e.registro,
                "antes": e.antes,
                "despues": e.despues,
                "actor": e.actor.full_name if e.actor else None,
                "at": e.created_at,
            }
            for e in db.scalars(
                select(PolizaEvento)
                .where(PolizaEvento.aseguradora_id.is_not(None))
                .order_by(PolizaEvento.created_at.desc())
                .limit(20)
            ).unique()
        ],
    }


# ---------------------------------------------------------------- policies


def _vivas():
    return select(Poliza).where(Poliza.eliminada_at.is_(None))


def get(db: Session, user: User, id_: uuid.UUID) -> Poliza:
    ensure(user)
    p = db.get(Poliza, id_)
    if p is None or p.eliminada_at is not None:
        raise NotFoundError("Esa póliza no existe.")
    return p


def registro(p: Poliza) -> str:
    partes = [p.cierre.code if p.cierre else None, inmueble_txt(p)]
    return " · ".join(x for x in partes if x)


def inmueble_txt(p: Poliza) -> str:
    if p.inmueble is not None:
        i = p.inmueble
        return f"{i.codigo} {(i.barrio or i.municipio or i.direccion)}"
    if p.descripcion:
        return p.descripcion
    if p.cierre is not None and p.cierre.lead.busca:
        return p.cierre.lead.busca
    return "—"


def costo_mes(p: Poliza) -> float:
    return p.canon * float(p.tipo.precio_pct) / 100


def _validar_tipo(db: Session, tipo_id: Any) -> PolizaTipo:
    t = db.get(PolizaTipo, tipo_id) if tipo_id else None
    if t is None or not t.activa or t.aseguradora.eliminada_at is not None:
        raise DomainError("Elige la aseguradora y el tipo de póliza.")
    if not t.aseguradora.activa:
        raise DomainError(f"{t.aseguradora.nombre} está inactiva: actívala o elige otra.")
    return t


def _canon(v: Any) -> int:
    try:
        c = int(v)
    except (TypeError, ValueError) as e:
        raise DomainError("Escribe el canon mensual.") from e
    if not 100_000 <= c <= 200_000_000:
        raise DomainError("Revisa el canon mensual.")
    return c


def crear(db: Session, data: dict[str, Any], *, actor: User) -> Poliza:
    """Register the study of a rental policy (G-030: entity and filing number)."""
    ensure(actor)
    cierre = inm = None
    if data.get("cierre_id"):
        cierre = db.get(Cierre, data["cierre_id"])
        if cierre is None:
            raise NotFoundError("Ese negocio no existe.")
        if cierre.negocio != TipoNegocio.ARRIENDO:
            raise DomainError("Las ventas no llevan póliza: solo los arriendos.")
        if cierre.estado == EstadoCierre.CAIDO:
            raise DomainError(f"{cierre.code} es un negocio caído.")
        if db.scalar(_vivas().where(Poliza.cierre_id == cierre.id).limit(1)) is not None:
            raise ConflictError(f"{cierre.code} ya tiene póliza.")
    if data.get("inmueble_id"):
        inm = db.get(Inmueble, data["inmueble_id"])
        if inm is None:
            raise NotFoundError("Ese inmueble no existe.")
        if inm.negocio != TipoNegocio.ARRIENDO:
            raise DomainError("Las ventas no llevan póliza: elige un inmueble en arriendo.")
    desc = (data.get("descripcion") or "").strip()[:200] or None
    if cierre is None and inm is None and not desc:
        raise DomainError("Elige el negocio o el inmueble de la póliza.")
    t = _validar_tipo(db, data.get("tipo_id"))
    canon = _canon(data.get("canon") or (inm.precio if inm else None))
    f = data.get("estudio_fecha") or hoy()
    if f > hoy():
        raise DomainError("La fecha del estudio no puede ser futura.")
    p = Poliza(
        cierre_id=cierre.id if cierre else None,
        inmueble_id=inm.id if inm else None,
        descripcion=desc,
        tipo_id=t.id,
        aseguradora_id=t.aseguradora_id,
        canon=canon,
        radicado=(data.get("radicado") or "").strip()[:80] or None,
        estudio_fecha=f,
        seguro_inmueble=bool(data.get("seguro_inmueble")),
        created_by_id=actor.id,
    )
    db.add(p)
    db.flush()
    db.refresh(p)
    _evento(
        db,
        actor,
        "Registró el estudio de la póliza",
        f"{registro(p)} · {t.aseguradora.nombre}",
        poliza=p,
        despues=f"En estudio · {t.nombre} · canon {_cop(canon)}"
        + (f" · radicado {p.radicado}" if p.radicado else ""),
    )
    db.flush()
    return p


def editar(db: Session, p: Poliza, data: dict[str, Any], *, actor: User) -> Poliza:
    ensure(actor)
    reg = f"{registro(p)} · {p.aseguradora.nombre}"
    if "tipo_id" in data and data["tipo_id"] and data["tipo_id"] != p.tipo_id:
        if p.estado not in ("en_estudio", "negada"):
            raise DomainError("La aseguradora solo se cambia mientras la póliza está en estudio.")
        t = _validar_tipo(db, data["tipo_id"])
        _evento(
            db,
            actor,
            "Cambió la aseguradora o el tipo",
            reg,
            poliza=p,
            antes=f"{p.aseguradora.nombre} · {p.tipo.nombre}",
            despues=f"{t.aseguradora.nombre} · {t.nombre}",
        )
        p.tipo_id, p.aseguradora_id = t.id, t.aseguradora_id
    if "canon" in data and data["canon"] is not None:
        c = _canon(data["canon"])
        if c != p.canon:
            _evento(
                db, actor, "Cambió el canon", reg, poliza=p, antes=_cop(p.canon), despues=_cop(c)
            )
            p.canon = c
    if "radicado" in data:
        v = (data["radicado"] or "").strip()[:80] or None
        if v != p.radicado:
            _evento(db, actor, "Cambió el radicado", reg, poliza=p, antes=p.radicado, despues=v)
            p.radicado = v
    if "seguro_inmueble" in data and bool(data["seguro_inmueble"]) != p.seguro_inmueble:
        p.seguro_inmueble = bool(data["seguro_inmueble"])
        _evento(
            db,
            actor,
            "Seguro del inmueble",
            reg,
            poliza=p,
            despues="Sí" if p.seguro_inmueble else "No",
        )
    db.flush()
    db.refresh(p)
    return p


def decidir(db: Session, p: Poliza, aprobada: bool, motivo: str | None, *, actor: User) -> Poliza:
    """The insurer answered the study (G-034: an approved policy is notified to the asesor)."""
    ensure(actor)
    if p.estado != "en_estudio":
        raise ConflictError("Solo se decide una póliza en estudio.")
    motivo = (motivo or "").strip()
    if not aprobada and len(motivo) < 3:
        raise DomainError("Escribe por qué se negó el estudio.")
    p.estado = "aprobada" if aprobada else "negada"
    p.decision_fecha = hoy()
    p.motivo_negada = None if aprobada else motivo[:300]
    p.recuperada = aprobada and p.estudios > 1
    _evento(
        db,
        actor,
        ("Aprobó la póliza" + (" · póliza recuperada" if p.recuperada else ""))
        if aprobada
        else "Registró la póliza negada",
        f"{registro(p)} · {p.aseguradora.nombre}",
        poliza=p,
        antes="En estudio",
        despues="Aprobada" if aprobada else f"Negada · {motivo[:200]}",
    )
    db.flush()
    return p


def retomar(db: Session, p: Poliza, motivo: str, *, actor: User) -> Poliza:
    """G-084 «Retomar el estudio»: the insured or co-signer changed, or the client was convinced."""
    ensure(actor)
    if p.estado != "negada":
        raise ConflictError("Solo se retoma el estudio de una póliza negada.")
    if p.estudios >= MAX_ESTUDIOS:
        raise ConflictError("Esta póliza ya tuvo un segundo estudio.")
    motivo = (motivo or "").strip()
    if len(motivo) < 3:
        raise DomainError("Escribe por qué se retoma el estudio.")
    p.estado, p.estudios, p.retomada_motivo = "en_estudio", p.estudios + 1, motivo[:300]
    p.decision_fecha = None
    _evento(
        db,
        actor,
        "Retomó el estudio",
        f"{registro(p)} · {p.aseguradora.nombre}",
        poliza=p,
        antes="Negada",
        despues=f"En estudio (segundo) · {motivo[:200]}",
    )
    db.flush()
    return p


def firmar(db: Session, p: Poliza, fecha: date, *, actor: User) -> Poliza:
    """The rental contract was signed: from here runs the insurer's deadline to activate."""
    ensure(actor)
    if p.estado != "aprobada":
        raise ConflictError("La firma del contrato se registra con la póliza aprobada.")
    if fecha > hoy():
        raise DomainError("La fecha de firma no puede ser futura.")
    if p.decision_fecha and fecha < p.estudio_fecha:
        raise DomainError("La firma no puede ser anterior al estudio.")
    antes = _fd(p.firma_fecha) if p.firma_fecha else None
    p.firma_fecha = fecha
    _evento(
        db,
        actor,
        "Registró la firma del contrato",
        f"{registro(p)} · {p.aseguradora.nombre}",
        poliza=p,
        antes=antes,
        despues=_fd(fecha),
    )
    db.flush()
    return p


def activar(
    db: Session, p: Poliza, fecha: date, numero: str, soporte: bool, *, actor: User
) -> Poliza:
    """X11 «Activar póliza»: date and policy number; it moves to «Contratos activos»."""
    ensure(actor)
    if p.estado != "aprobada" or p.firma_fecha is None:
        raise ConflictError("Se activa una póliza aprobada y con el contrato firmado.")
    numero = (numero or "").strip()
    if not numero:
        raise DomainError("Completa la fecha de activación y el número de póliza.")
    if fecha > hoy() or fecha < p.firma_fecha:
        raise DomainError("La fecha de activación debe estar entre la firma del contrato y hoy.")
    tarde = fecha > p.firma_fecha + timedelta(days=p.aseguradora.dias_max)
    p.estado, p.activada_fecha, p.numero_poliza, p.soporte = "activa", fecha, numero[:80], soporte
    _evento(
        db,
        actor,
        "Activó la póliza",
        f"{registro(p)} · {p.aseguradora.nombre}",
        poliza=p,
        antes="Aprobada · por activar",
        despues=f"Activa desde {_fd(fecha)} · {numero[:60]}"
        + (" · fuera del plazo" if tarde else ""),
    )
    db.flush()
    return p


def terminar(db: Session, p: Poliza, fecha: date, *, actor: User) -> Poliza:
    ensure(actor)
    if p.estado != "activa":
        raise ConflictError("Solo se termina una póliza activa.")
    if p.activada_fecha and fecha < p.activada_fecha:
        raise DomainError("La fecha de terminación no puede ser anterior a la activación.")
    p.estado, p.terminada_fecha = "terminada", fecha
    _evento(
        db,
        actor,
        "Terminó la póliza",
        f"{registro(p)} · {p.aseguradora.nombre}",
        poliza=p,
        antes="Activa",
        despues=f"Terminada el {_fd(fecha)}",
    )
    db.flush()
    return p


def eliminar(db: Session, p: Poliza, motivo: str, *, actor: User) -> None:
    """G-087: anything added can be deleted, keeping who and when. Active ones are ended first."""
    ensure(actor)
    if p.estado == "activa":
        raise ConflictError("Una póliza activa no se elimina: termínala cuando acabe el contrato.")
    motivo = (motivo or "").strip()
    if len(motivo) < 3:
        raise DomainError("Escribe por qué se elimina.")
    p.eliminada_at, p.eliminada_por_id, p.eliminada_motivo = fechas.now(), actor.id, motivo[:300]
    _evento(
        db,
        actor,
        "Eliminó la póliza",
        f"{registro(p)} · {p.aseguradora.nombre}",
        poliza=p,
        antes=ESTADOS[p.estado][0],
        despues=f"Eliminada · {motivo[:200]}",
    )
    db.flush()


# ---------------------------------------------------------------- alerts


def alerta(p: Poliza, d: date) -> dict[str, Any] | None:
    """None unless the policy is approved, signed and not active. st: v (vencida) · p · o."""
    if p.estado != "aprobada" or p.firma_fecha is None:
        return None
    a = p.aseguradora
    dias = (d - p.firma_fecha).days
    falta = a.dias_max - dias
    st = "v" if falta < 0 else ("p" if falta <= a.aviso_dias else "o")
    return {
        "dias": dias,
        "falta": falta,
        "max": p.firma_fecha + timedelta(days=a.dias_max),
        "st": st,
    }


def por_activar(db: Session) -> list[tuple[Poliza, dict[str, Any]]]:
    d = hoy()
    ps = db.scalars(
        _vivas().where(Poliza.estado == "aprobada", Poliza.firma_fecha.is_not(None))
    ).unique()
    out = [(p, alerta(p, d)) for p in ps]
    return sorted([(p, a) for p, a in out if a], key=lambda x: x[1]["falta"])


# ---------------------------------------------------------------- views


@dataclass
class Rango:
    d1: date
    d2: date


def _fila(p: Poliza, d: date) -> dict[str, Any]:
    e, cls = ESTADOS[p.estado]
    a = alerta(p, d)
    if p.estado == "aprobada":
        e = "Aprobada · falta la firma" if p.firma_fecha is None else "Aprobada · por activar"
        cls = "ok" if p.firma_fecha is None else "warn"
    meses = None
    if p.estado == "activa" and p.activada_fecha:
        m = int((d - p.activada_fecha).days // 30.4)
        meses = "menos de 1 mes" if m < 1 else f"{m} {'mes' if m == 1 else 'meses'}"
    return {
        "id": p.id,
        "negocio": p.cierre.code if p.cierre else None,
        "asesor": p.cierre.cerrador.full_name if p.cierre and p.cierre.cerrador else None,
        "inmueble": inmueble_txt(p),
        "inmueble_id": p.inmueble_id,
        "aseguradora": p.aseguradora.nombre,
        "aseguradora_id": p.aseguradora_id,
        "tipo": p.tipo.nombre,
        "tipo_id": p.tipo_id,
        "precio_pct": float(p.tipo.precio_pct),
        "canon": p.canon,
        "costo_mes": round(costo_mes(p)),
        "estado": p.estado,
        "estado_txt": e,
        "estado_cls": cls,
        "radicado": p.radicado,
        "estudio_fecha": p.estudio_fecha,
        "decision_fecha": p.decision_fecha,
        "motivo_negada": p.motivo_negada,
        "estudios": p.estudios,
        "puede_retomar": p.estado == "negada" and p.estudios < MAX_ESTUDIOS,
        "retomada_motivo": p.retomada_motivo,
        "recuperada": p.recuperada,
        "firma_fecha": p.firma_fecha,
        "activada_fecha": p.activada_fecha,
        "numero_poliza": p.numero_poliza,
        "soporte": p.soporte,
        "seguro_inmueble": p.seguro_inmueble,
        "terminada_fecha": p.terminada_fecha,
        "tiempo_activa": meses,
        "alerta": a,
    }


def tablero(db: Session, user: User, r: Rango, aseguradora_id: uuid.UUID | None) -> dict[str, Any]:
    ensure(user)
    if r.d1 > r.d2:
        raise DomainError("La fecha «Desde» no puede ser posterior a «Hasta».")
    d = hoy()
    ases = aseguradoras(db)
    todas = list(db.scalars(_vivas().order_by(Poliza.created_at.desc())).unique())
    ok_e = (lambda p: p.aseguradora_id == aseguradora_id) if aseguradora_id else (lambda p: True)
    activas = [p for p in todas if p.estado == "activa" and ok_e(p)]
    en_rango = lambda p: p.activada_fecha is not None and r.d1 <= p.activada_fecha <= r.d2  # noqa: E731
    nuevas = [p for p in todas if en_rango(p) and ok_e(p)]
    ale = por_activar(db)
    n_v = sum(1 for _, a in ale if a["st"] == "v")
    n_p = sum(1 for _, a in ale if a["st"] == "p")
    por_e = []
    for a in ases:
        if aseguradora_id and a.id != aseguradora_id:
            continue
        act = [p for p in activas if p.aseguradora_id == a.id]
        if not a.activa and not act:
            continue
        vig = [p.activada_fecha for p in act if p.activada_fecha]
        por_e.append(
            {
                "id": a.id,
                "nombre": a.nombre,
                "tipos": " · ".join(t.nombre for t in a.productos) or "—",
                "activas": len(act),
                "costo_mes": round(sum(costo_mes(p) for p in act)),
                "precio_prom": round(sum(float(p.tipo.precio_pct) for p in act) / len(act), 2)
                if act
                else None,
                "activa_desde": min(vig) if vig else None,
                "plazo": f"{a.dias_max} días · aviso {a.aviso_dias} antes",
                "nuevas": sum(1 for p in nuevas if p.aseguradora_id == a.id),
            }
        )
    tramite = [p for p in todas if p.estado in ("en_estudio", "aprobada", "negada") and ok_e(p)]
    return {
        "desde": r.d1,
        "hasta": r.d2,
        "kpis": {
            "activas": len(activas),
            "costo_mes": round(sum(costo_mes(p) for p in activas)),
            "canon_mes": sum(p.canon for p in activas),
            "nuevas": len(nuevas),
            "por_activar": len(ale),
            "vencidas": n_v,
            "por_vencer": n_p,
            "en_estudio": sum(1 for p in todas if p.estado == "en_estudio"),
            "recuperadas": sum(
                1
                for p in todas
                if p.recuperada and p.decision_fecha and r.d1 <= p.decision_fecha <= r.d2
            ),
        },
        "por_aseguradora": por_e,
        "contratos": [
            _fila(p, d)
            for p in sorted(nuevas, key=lambda p: p.activada_fecha, reverse=True)
            if p.estado == "activa"
        ],
        "activas_total": len(activas),
        "alertas": [_fila(p, d) for p, _ in ale],
        "tramite": [_fila(p, d) for p in tramite],
        "terminadas": [_fila(p, d) for p in todas if p.estado == "terminada" and ok_e(p)][:20],
    }


def opciones(db: Session, user: User) -> dict[str, Any]:
    """What the «Registrar póliza» form offers: rental deals without a policy, rental properties
    and the active insurers with their policies."""
    ensure(user)
    con_poliza = select(Poliza.cierre_id).where(
        Poliza.eliminada_at.is_(None), Poliza.cierre_id.is_not(None)
    )
    cierres = db.scalars(
        select(Cierre)
        .join(Lead, Lead.id == Cierre.lead_id)
        .where(
            Cierre.negocio == TipoNegocio.ARRIENDO,
            Cierre.estado == EstadoCierre.CERRADO,
            Cierre.id.not_in(con_poliza),
        )
        .order_by(Cierre.numero.desc())
    ).unique()
    inms = db.scalars(
        select(Inmueble).where(Inmueble.negocio == TipoNegocio.ARRIENDO).order_by(Inmueble.codigo)
    ).unique()
    return {
        "negocios": [
            {
                "id": c.id,
                "t": f"{c.code} · {c.lead.full_name} · {c.lead.busca or 'arriendo'}",
                "asesor": c.cerrador.full_name if c.cerrador else None,
            }
            for c in cierres
        ],
        "inmuebles": [
            {
                "id": i.id,
                "t": f"{i.codigo} · {i.barrio or i.municipio or i.direccion}",
                "canon": i.precio,
            }
            for i in inms
        ],
        "aseguradoras": [
            {
                "id": a.id,
                "nombre": a.nombre,
                "tipos": [
                    {"id": t.id, "nombre": t.nombre, "precio_pct": float(t.precio_pct)}
                    for t in a.productos
                    if t.activa
                ],
            }
            for a in aseguradoras(db)
            if a.activa
        ],
    }


def historial(db: Session, p: Poliza) -> list[dict[str, Any]]:
    return [
        {
            "accion": e.accion,
            "antes": e.antes,
            "despues": e.despues,
            "actor": e.actor.full_name if e.actor else None,
            "at": e.created_at,
        }
        for e in db.scalars(
            select(PolizaEvento)
            .where(PolizaEvento.poliza_id == p.id)
            .order_by(PolizaEvento.created_at.desc())
        ).unique()
    ]


def comparar(db: Session, user: User, r: Rango) -> dict[str, Any]:
    """G-072 «Comparar pólizas» (Gerencia): one card per insurer policy, with real usage."""
    ensure_gerencia(user)
    if r.d1 > r.d2:
        raise DomainError("La fecha «Desde» no puede ser posterior a «Hasta».")
    ps = list(db.scalars(_vivas()).unique())
    hace_30 = hoy() - timedelta(days=30)
    cards = []
    for a in aseguradoras(db):
        if not a.activa:
            continue
        for t in a.productos:
            if not t.activa:
                continue
            mias = [p for p in ps if p.tipo_id == t.id]
            act = [p for p in mias if p.estado == "activa"]
            dec = [p for p in mias if p.decision_fecha and r.d1 <= p.decision_fecha <= r.d2]
            apr = sum(1 for p in dec if p.estado != "negada")
            cards.append(
                {
                    "id": t.id,
                    "aseguradora_id": a.id,
                    "aseguradora": a.nombre,
                    "tipo": t.nombre,
                    "precio_pct": float(t.precio_pct),
                    "costo_estudio": t.costo_estudio,
                    "dias_respuesta": t.dias_respuesta,
                    "coberturas": t.coberturas,
                    "aprobados": apr,
                    "estudios": len(dec),
                    "aprobacion": round(100 * apr / len(dec)) if dec else None,
                    "negados": len(dec) - apr,
                    "activas": len(act),
                    "con_seguro": sum(1 for p in act if p.seguro_inmueble),
                    "canon_mes": sum(p.canon for p in act),
                    "nueva": not mias and a.created_at.date() >= hace_30,
                    "inmuebles": [
                        {
                            "c": p.cierre.code if p.cierre else "—",
                            "d": inmueble_txt(p),
                            "v": p.canon,
                        }
                        for p in act[:5]
                    ],
                }
            )
    return {"desde": r.d1, "hasta": r.d2, "cards": cards, "coberturas": COBERTURAS}


# ---------------------------------------------------------------- for other modules


def aprobadas_de(db: Session, asesor: User, desde: date) -> list[Poliza]:
    """Approved policies of the asesor's deals since a date (G-034 notification)."""
    return list(
        db.scalars(
            _vivas()
            .join(Cierre, Cierre.id == Poliza.cierre_id)
            .where(
                Cierre.cerrador_id == asesor.id,
                Poliza.decision_fecha >= desde,
                or_(Poliza.estado == "aprobada", Poliza.estado == "activa"),
            )
        ).unique()
    )
