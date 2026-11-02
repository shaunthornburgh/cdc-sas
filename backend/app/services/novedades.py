"""Novedades del personal (prototype K13 «Ausencias y permisos»).

* **Types** (K13): incapacidad, permiso no remunerado, permiso remunerado. The first two are
  discounted from the salary; the paid permit is only counted.
* **Days**: calendar days from «desde» to «hasta», both included (K13: «1 y 2 oct» = 2 días).
* **Who**: Coordinación and the Auxiliar register them; Gerencia sees them (K13 hides the button
  for Gerencia: «le llega a Gerencia»). A mistake is «anulada» with a reason, never deleted.
* **Salary**: each unconfirmed pay period («por confirmar») gets the discount and a short summary
  in its «novedades». Daily rate = monthly salary / 30, capped at the period's salary. A period
  the Auxiliar already confirmed or Gerencia already paid isn't touched: the response warns
  about it so it's adjusted by hand.
* **«Del preoperacional»** tab: the preoperacionales with a novedad, reviewed with the existing
  «Marcar como revisada» (Coordinación / Gerencia, same rules as K09).
"""

from __future__ import annotations

import calendar
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LiquidacionSalario, Novedad, Preoperacional, SalarioConfig, User
from app.models.enums import (
    NOVEDADES_DESCONTABLES,
    Cargo,
    EstadoNovedad,
    EstadoSalario,
    TipoNovedad,
)
from app.services import fechas
from app.services import preoperacional as preop
from app.services.errors import ConflictError, DomainError, NotFoundError, PermissionDeniedError

TIPO_LABELS = {
    TipoNovedad.INCAPACIDAD: "Incapacidad",
    TipoNovedad.PERMISO_NO_REMUNERADO: "Permiso no remunerado",
    TipoNovedad.PERMISO_REMUNERADO: "Permiso remunerado",
}
TIPO_AYUDA = {
    TipoNovedad.INCAPACIDAD: "Adjunta el certificado de incapacidad.",
    TipoNovedad.PERMISO_NO_REMUNERADO: "Se descuenta del pago del mes.",
    TipoNovedad.PERMISO_REMUNERADO: "No se descuenta; solo se cuenta.",
}
ESTADO_LABELS = {EstadoNovedad.REGISTRADA: "Registrada", EstadoNovedad.ANULADA: "Anulada"}
REGISTRAN = (Cargo.COORDINACION, Cargo.AUXILIAR_ADMINISTRATIVA)
VEN = (*REGISTRAN, Cargo.GERENCIA)
MAX_DIAS = 180
DIAS_MES_SALARIO = 30


# ---------------------------------------------------------------- access


def can_view(user: User) -> bool:
    return user.is_active and user.cargo in VEN


def can_register(user: User) -> bool:
    return user.is_active and user.cargo in REGISTRAN


def ensure_view(user: User) -> None:
    if not can_view(user):
        raise PermissionDeniedError(
            "Las novedades del personal las ven Coordinación, Gerencia y la Auxiliar."
        )


def ensure_register(user: User) -> None:
    if not can_register(user):
        raise PermissionDeniedError("Las novedades las registran Coordinación y la Auxiliar.")


def empleados(db: Session) -> list[User]:
    """Who can have an absence: every active person except Gerencia (as in K13's list)."""
    return list(
        db.scalars(
            select(User)
            .where(User.is_active.is_(True), User.cargo != Cargo.GERENCIA)
            .order_by(User.full_name)
        ).unique()
    )


def get_novedad(db: Session, user: User, id_: uuid.UUID) -> Novedad:
    ensure_view(user)
    n = db.get(Novedad, id_)
    if n is None:
        raise NotFoundError("Esa novedad no existe.")
    return n


# ---------------------------------------------------------------- helpers


def hoy() -> date:
    return fechas.local_date(fechas.now())


def _overlap(a1: date, a2: date, b1: date, b2: date) -> int:
    """Days shared by two inclusive ranges."""
    return max(0, (min(a2, b2) - max(a1, b1)).days + 1)


def dias_en(n: Novedad, d1: date, d2: date) -> int:
    return _overlap(n.desde, n.hasta, d1, d2)


def fmt_rango(d1: date, d2: date) -> str:
    """«2 oct» · «1 y 2 oct» · «28 sep al 3 oct» (K13 style)."""
    m = fechas._MESES
    if d1 == d2:
        return f"{d1.day} {m[d1.month - 1]}"
    if d1.month == d2.month and d1.year == d2.year:
        sep = " y " if (d2 - d1).days == 1 else " al "
        return f"{d1.day}{sep}{d2.day} {m[d2.month - 1]}"
    return f"{d1.day} {m[d1.month - 1]} al {d2.day} {m[d2.month - 1]}"


def _dias_txt(n: int) -> str:
    return f"{n} día{'s' if n != 1 else ''}"


# ---------------------------------------------------------------- list & KPIs


@dataclass
class Filtros:
    desde: date
    hasta: date
    tipo: TipoNovedad | None = None
    empleado_id: uuid.UUID | None = None
    anuladas: bool = False


def mes_actual() -> tuple[date, date]:
    d = hoy()
    return d.replace(day=1), d.replace(day=calendar.monthrange(d.year, d.month)[1])


def listar(db: Session, user: User, f: Filtros) -> list[Novedad]:
    ensure_view(user)
    if f.desde > f.hasta:
        raise DomainError("La fecha «Desde» no puede ser posterior a «Hasta».")
    q = select(Novedad).where(Novedad.desde <= f.hasta, Novedad.hasta >= f.desde)
    if not f.anuladas:
        q = q.where(Novedad.estado == EstadoNovedad.REGISTRADA)
    if f.tipo:
        q = q.where(Novedad.tipo == f.tipo)
    if f.empleado_id:
        q = q.where(Novedad.empleado_id == f.empleado_id)
    return list(db.scalars(q.order_by(Novedad.desde.desc(), Novedad.numero.desc())).unique())


def resumen(rows: list[Novedad], d1: date, d2: date) -> dict[str, int]:
    """K13's three cards: days of each type inside the range (registered ones only)."""
    out = {t.value: 0 for t in TipoNovedad}
    for n in rows:
        if n.estado == EstadoNovedad.REGISTRADA:
            out[n.tipo.value] += dias_en(n, d1, d2)
    return out


# ---------------------------------------------------------------- commands


def crear(db: Session, data: dict[str, Any], *, actor: User) -> tuple[Novedad, list[str]]:
    ensure_register(actor)
    emp = db.get(User, data.get("empleado_id"))
    if emp is None or not emp.is_active or emp.cargo == Cargo.GERENCIA:
        raise DomainError("Elige el empleado.")
    desde, hasta = data.get("desde"), data.get("hasta")
    if desde is None or hasta is None:
        raise DomainError("Elige las fechas «Desde» y «Hasta».")
    if hasta < desde:
        raise DomainError("La fecha «Hasta» no puede ser anterior a «Desde».")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise DomainError(f"Una novedad no puede pasar de {MAX_DIAS} días: regístrala por partes.")
    choque = db.scalar(
        select(Novedad).where(
            Novedad.empleado_id == emp.id,
            Novedad.estado == EstadoNovedad.REGISTRADA,
            Novedad.desde <= hasta,
            Novedad.hasta >= desde,
        )
    )
    if choque is not None:
        raise ConflictError(
            f"{emp.full_name} ya tiene {TIPO_LABELS[choque.tipo].lower()} del "
            f"{fmt_rango(choque.desde, choque.hasta)} ({choque.code})."
        )
    n = Novedad(
        empleado_id=emp.id,
        tipo=data["tipo"],
        desde=desde,
        hasta=hasta,
        observacion=(data.get("observacion") or "").strip() or None,
        soportes=data.get("soportes") or 0,
        estado=EstadoNovedad.REGISTRADA,
        registrada_por_id=actor.id,
    )
    n.empleado = emp
    n.registrada_por = actor
    db.add(n)
    db.flush()
    avisos = recalcular_salarios(db, n)
    return n, avisos


def actualizar(db: Session, n: Novedad, data: dict[str, Any], *, actor: User) -> Novedad:
    """Only the note and the attachments change. Wrong dates or type: annul and register again."""
    ensure_register(actor)
    if n.estado == EstadoNovedad.ANULADA:
        raise ConflictError("La novedad está anulada.")
    if extra := set(data) - {"observacion", "soportes"}:
        raise DomainError(
            f"No se puede cambiar «{sorted(extra)[0]}»: anúlala y regístrala de nuevo."
        )
    if "observacion" in data:
        n.observacion = (data["observacion"] or "").strip() or None
    if data.get("soportes") is not None:
        if not 0 <= data["soportes"] <= 20:
            raise DomainError("Revisa el número de soportes.")
        n.soportes = data["soportes"]
    db.flush()
    return n


def anular(
    db: Session, n: Novedad, motivo: str | None, *, actor: User
) -> tuple[Novedad, list[str]]:
    ensure_register(actor)
    if n.estado == EstadoNovedad.ANULADA:
        raise ConflictError("La novedad ya está anulada.")
    motivo = (motivo or "").strip()
    if len(motivo) < 3:
        raise DomainError("Escribe por qué se anula.")
    n.estado = EstadoNovedad.ANULADA
    n.anulada_por_id = actor.id
    n.anulada_por = actor
    n.anulada_at = fechas.now()
    n.motivo_anulacion = motivo
    db.flush()
    return n, recalcular_salarios(db, n)


# ---------------------------------------------------------------- salary («Salarios del mes»)


def ventana(periodo: date, corte: int) -> tuple[date, date]:
    """Days a pay period covers: 1st cut 1–15, 2nd cut 16–end of month."""
    fin = calendar.monthrange(periodo.year, periodo.month)[1]
    return (
        (periodo, periodo.replace(day=15))
        if corte == 1
        else (
            periodo.replace(day=16),
            periodo.replace(day=fin),
        )
    )


def aplicar(db: Session, liq: LiquidacionSalario, mensual: int) -> None:
    """Set the discount and summary of an unconfirmed pay period from the registered novedades."""
    if liq.estado != EstadoSalario.POR_CONFIRMAR:
        return
    d1, d2 = ventana(liq.periodo, liq.corte)
    rows = db.scalars(
        select(Novedad).where(
            Novedad.empleado_id == liq.user_id,
            Novedad.estado == EstadoNovedad.REGISTRADA,
            Novedad.desde <= d2,
            Novedad.hasta >= d1,
        )
    ).unique()
    dias = {t: 0 for t in TipoNovedad}
    for n in rows:
        dias[n.tipo] += dias_en(n, d1, d2)
    descontar = sum(dias[t] for t in NOVEDADES_DESCONTABLES)
    # Asistencia (G-048): impuntualidad and rejected early exits are discounted by the minute;
    # accepted horas extra are listed (their value is PENDIENTE: contador).
    from app.services import asistencia

    min_desc, min_extra = asistencia.para_salario(db, liq.user_id, d1, d2)
    por_minuto = mensual / DIAS_MES_SALARIO / asistencia.HORAS_DIA / 60
    liq.descuento = min(
        liq.salario_corte, round(mensual / DIAS_MES_SALARIO * descontar + por_minuto * min_desc)
    )
    partes = [f"{TIPO_LABELS[t]} {_dias_txt(d)}" for t, d in dias.items() if d]
    if min_desc:
        partes.append(f"Impuntualidad {asistencia.dur_txt(min_desc)}")
    if min_extra:
        partes.append(f"Horas extra {asistencia.dur_txt(min_extra)} (valor pendiente)")
    liq.novedades = " · ".join(partes)[:300] or None


def recalcular_salarios(db: Session, n: Novedad) -> list[str]:
    """Update the pay periods the novedad touches. Returns warnings for closed ones."""
    cfg = db.get(SalarioConfig, n.empleado_id)
    avisos: list[str] = []
    liqs = db.scalars(
        select(LiquidacionSalario).where(
            LiquidacionSalario.user_id == n.empleado_id,
            LiquidacionSalario.periodo >= n.desde.replace(day=1),
            LiquidacionSalario.periodo <= n.hasta.replace(day=1),
        )
    ).unique()
    for liq in liqs:
        d1, d2 = ventana(liq.periodo, liq.corte)
        if not dias_en(n, d1, d2):
            continue
        if liq.estado == EstadoSalario.POR_CONFIRMAR:
            if cfg is not None:
                aplicar(db, liq, cfg.salario_mensual)
        elif n.tipo in NOVEDADES_DESCONTABLES:
            n_corte = "1.er" if liq.corte == 1 else "2.º"
            mes = fechas._MESES[liq.periodo.month - 1]
            estado = "pagado" if liq.estado == EstadoSalario.PAGADO else "confirmado"
            avisos.append(
                f"El salario del {n_corte} corte de {mes} ya está {estado}: ajústalo a mano."
            )
    db.flush()
    return avisos


# ---------------------------------------------------------------- «Del preoperacional»


def preoperacionales(db: Session, user: User, d1: date, d2: date) -> list[Preoperacional]:
    """Preoperacionales with a novedad in the range: Gerencia and the Auxiliar see everyone's,
    Coordinación those it reviews (K09)."""
    ensure_view(user)
    q = select(Preoperacional).where(
        Preoperacional.tiene_novedad.is_(True),
        Preoperacional.fecha >= d1,
        Preoperacional.fecha <= d2,
    )
    rows = list(
        db.scalars(
            q.order_by(Preoperacional.fecha.desc(), Preoperacional.realizado_at.desc())
        ).unique()
    )
    allowed = preop.reviewer_cargos(user)
    if user.cargo == Cargo.COORDINACION and allowed is not None:
        rows = [p for p in rows if p.user.cargo in allowed]
    return rows


def puede_revisar(user: User, p: Preoperacional) -> bool:
    allowed = preop.reviewer_cargos(user)
    return allowed is not None and p.user.cargo in allowed and p.revisado_at is None


def texto_preop(p: Preoperacional) -> str:
    """«NO en: ¿Frenos…? · Observación: «frenos con ruido»» (K13)."""
    partes = []
    if p.respuestas_no:
        resp = p.respuestas or []
        partes.append(
            "NO en: "
            + "; ".join(resp[i - 1].get("pregunta", f"pregunta {i}") for i in p.respuestas_no)
        )
    if p.observaciones:
        partes.append(f"Observación: «{p.observaciones.strip().rstrip('.')}»")
    return " · ".join(partes) or "Novedad reportada"


def sin_revisar(db: Session, user: User, d1: date, d2: date) -> int:
    return sum(1 for p in preoperacionales(db, user, d1, d2) if p.revisado_at is None)
