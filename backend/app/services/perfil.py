"""Mi perfil (Z01 / Z01-coord / Z01-aux / Z01-ger, M11; decision «Foto y nombre en el perfil»).

* Everyone changes their own **photo** and **password** here.
* The name and the other personal data (teléfono, cédula, fecha de ingreso) are only changed by
  Coordinación or Gerencia in «Usuarios»; each change is logged with before and after. The page
  says so, as the prototypes do.
* The cédula is always shown masked («••••••2210»).
* Password: the prototype sends a link by email; there is no email service yet, so it's changed
  here with the current password.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import Preoperacional, User
from app.models.enums import ActividadComercial, Cargo
from app.services import agenda, fechas
from app.services import users as users_svc
from app.services.errors import ConflictError, DomainError

AREA = {
    "ger": "Gerencia",
    "coo": "Coordinación",
    "aux": "Administrativa",
    "ate": "Atención y Preventa",
    "ase": "Comercial",
}
CARGO_TXT = {
    "ger": "Gerente",
    "coo": "Coordinador",
    "aux": "Auxiliar administrativa",
    "ate": "Atención y Preventa",
    "ase": "Asesor comercial",
}
REGLA_NOMBRE = {
    "ger": "Tu nombre se cambia desde «Usuarios».",
    "coo": "Tu nombre lo cambia Gerencia.",
    "aux": "Tu nombre lo cambia Gerencia.",
}
REGLA_OTROS = (
    "Tu nombre y tus demás datos los cambian Coordinación o Gerencia; si algo está mal, avísale "
    "a tu coordinador. Cada cambio queda registrado."
)
RESULTADOS = {
    "ase": "Ventas, arriendos, captación y calificaciones",
    "ate": "Indicadores, calificaciones, comisiones y bonos",
    "coo": "Resultado del equipo, monitoreo, plataformas, rutas y calificaciones",
}
ACT_LABELS = {
    ActividadComercial.CAPTACION: "Captación",
    ActividadComercial.VENTAS: "Ventas",
    ActividadComercial.ARRIENDOS: "Arriendos",
}
MAX_FOTO = 400_000  # characters of the data URL (~300 KB image)
_FOTO = re.compile(r"^data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$")


def _fecha(d) -> str:
    return f"{d.day} {fechas._MESES[d.month - 1]} {d.year}"


def _rol(u: User) -> str:
    return agenda.rol(u) or ("ase" if u.cargo == Cargo.ASESOR else "aux")


def perfil(db: Session, u: User) -> dict[str, Any]:
    r = _rol(u)
    datos: list[tuple[str, str]] = [
        ("Área", AREA[r]),
        ("Correo (usuario)", u.email),
        ("Teléfono", u.telefono or "Sin registrar"),
        ("Fecha de ingreso", _fecha(u.fecha_ingreso) if u.fecha_ingreso else "Sin registrar"),
    ]
    if r in ("ase", "ate"):
        coords = db.scalars(
            select(User.full_name)
            .where(User.is_active.is_(True), User.cargo == Cargo.COORDINACION)
            .order_by(User.full_name)
        ).all()
        datos.append(("Coordinador", ", ".join(coords) or "Sin coordinador"))
    elif r == "coo":
        equipo = [
            x
            for x in db.scalars(select(User).where(User.is_active.is_(True))).unique()
            if agenda.rol(x) in ("ase", "ate")
        ]
        datos.append(("Equipo a cargo", f"{len(equipo)} persona{'s' if len(equipo) != 1 else ''}"))
    elif r == "aux":
        datos.append(("Reporta a", "Gerencia"))
    else:
        datos.append(("Acceso", "Completo"))
    datos.append(("Cédula", users_svc.mask(u.documento) or "Sin registrar"))
    if r == "ase":
        p = db.scalar(
            select(Preoperacional)
            .where(Preoperacional.user_id == u.id)
            .order_by(Preoperacional.fecha.desc())
            .limit(1)
        )
        if p is not None:
            from app.services.preoperacional import MEDIO_LABELS

            datos.append(
                (
                    "Medio de transporte",
                    MEDIO_LABELS[p.medio] + (f" · placa {p.placa}" if p.placa else ""),
                )
            )

    from app.services import rendimiento as rend

    con_resultado = rend.perfil(u) is not None
    accesos = []
    if con_resultado:
        accesos.append(("Mis resultados", "/resultados"))
    if r != "ger":
        accesos.append(("Mis pagos y bonos", "/mis-pagos"))
    accesos += [
        ("Mi preoperacional", "/preoperacional"),
        (
            "Mi agenda" if r != "ger" else "Avisos y agenda",
            "/agenda" if r != "ger" else "/avisos?tab=agenda",
        ),
    ]
    return {
        "id": u.id,
        "full_name": u.full_name,
        "cargo_txt": CARGO_TXT[r],
        "area": AREA[r],
        "actividades": [ACT_LABELS[a] for a in u.actividades],
        "regla_nombre": REGLA_NOMBRE.get(r, REGLA_OTROS),
        "datos": [{"k": k, "v": v} for k, v in datos],
        "resultados": (
            {
                "href": "/resultados",
                "mes": fechas._MESES[fechas.local_date(fechas.now()).month - 1],
                "txt": RESULTADOS.get(r, "Tus indicadores y calificaciones"),
            }
            if con_resultado
            else None
        ),
        "accesos": [{"t": t, "href": h} for t, h in accesos],
        "politica_aceptada_at": u.politica_aceptada_at,
        "tiene_foto": bool(u.foto),
    }


def cambiar_foto(db: Session, u: User, foto: str | None) -> User:
    if foto is not None:
        if not _FOTO.match(foto):
            raise DomainError("La foto debe ser una imagen JPG, PNG o WebP.")
        if len(foto) > MAX_FOTO:
            raise DomainError("La foto es muy pesada: usa una de menos de 300 KB.")
    if u.foto == foto:
        return u
    users_svc.log_cambio(db, u, "foto", u.foto, foto, u)
    u.foto = foto
    db.flush()
    return u


def cambiar_password(db: Session, u: User, actual: str, nueva: str) -> None:
    if not verify_password(actual, u.hashed_password):
        raise DomainError("La contraseña actual no es correcta.")
    if len(nueva) < 8:
        raise DomainError("La nueva contraseña debe tener al menos 8 caracteres.")
    if nueva == actual:
        raise DomainError("La nueva contraseña debe ser distinta de la actual.")
    if nueva.strip().lower() == u.email.lower():
        raise DomainError("La contraseña no puede ser tu correo.")
    u.hashed_password = hash_password(nueva)
    users_svc.log_cambio(db, u, "password", None, "cambiada", u)
    db.flush()


def aceptar_politica(db: Session, u: User) -> User:
    if u.politica_aceptada_at is not None:
        raise ConflictError("Ya aceptaste la política de tratamiento de datos.")
    u.politica_aceptada_at = fechas.now()
    db.flush()
    return u
