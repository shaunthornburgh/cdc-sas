"""Demo personal data for «Mi perfil» (Z01 / M11 example values), called from app.scripts.seed.

Fills teléfono, cédula and fecha de ingreso of the demo users that don't have them yet; the data
policy counts as accepted on the start date. Written directly (not as changes by someone), so the
change history starts empty.
"""

from datetime import date, datetime, time

from sqlalchemy.orm import Session

from app.services import fechas
from app.services.users import get_user_by_email

DATOS = {
    "gerencia": ("300 000 0001", "1000000001", date(2025, 10, 1)),
    "coordinacion": ("300 000 0050", "1088128812", date(2025, 10, 1)),
    "asesor": ("300 000 0021", "1020454521", date(2026, 2, 2)),
    "bruno": ("300 000 0034", "1036777730", date(2026, 3, 10)),
    "carla": ("300 000 0027", "1017456612", date(2026, 3, 16)),
    "diego": ("300 000 0029", "1152443309", date(2026, 4, 6)),
    "preventas": ("300 000 0042", "1040221187", date(2026, 4, 1)),
    "atencion": ("300 000 0041", "1039882210", date(2026, 4, 1)),
    "auxiliar": ("300 000 0060", "1001993307", date(2026, 6, 1)),
}


def seed_perfil(db: Session) -> int:
    n = 0
    for email, (tel, doc, ingreso) in DATOS.items():
        u = get_user_by_email(db, f"{email}@example.com")
        if u is None or u.fecha_ingreso is not None:
            continue
        u.telefono, u.documento, u.fecha_ingreso = tel, doc, ingreso
        u.politica_aceptada_at = datetime.combine(ingreso, time(9, 0), tzinfo=fechas.BOGOTA)
        n += 1
    db.flush()
    return n
