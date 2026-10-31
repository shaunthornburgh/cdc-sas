"""Create demo users for local development. Safe to run repeatedly.

    python -m app.scripts.seed

All users get the password in SEED_PASSWORD (default: CasaDolce2026!).
"""

import os
import sys

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.enums import ActividadComercial as A
from app.models.enums import Cargo, FuncionIndependiente
from app.scripts.seed_administracion import seed_administracion
from app.scripts.seed_captaciones import seed_captaciones
from app.scripts.seed_compensacion import seed_compensacion
from app.scripts.seed_inmuebles import seed_inmuebles
from app.scripts.seed_leads import seed_leads
from app.scripts.seed_novedades import seed_novedades
from app.scripts.seed_pedidos import seed_pedidos
from app.scripts.seed_preoperacional import seed_preoperacional
from app.scripts.seed_rendimiento import seed_rendimiento
from app.services.users import create_user, get_user_by_email

DEFAULT_PASSWORD = "CasaDolce2026!"

DEMO_USERS = [
    dict(email="gerencia@example.com", full_name="Gerencia Demo", cargo=Cargo.GERENCIA),
    dict(email="coordinacion@example.com", full_name="Coordinación Demo", cargo=Cargo.COORDINACION),
    dict(
        email="asesor@example.com",
        full_name="Asesor Demo",
        cargo=Cargo.ASESOR,
        actividades=[A.CAPTACION, A.VENTAS],
    ),
    dict(
        email="bruno@example.com",
        full_name="Bruno Captación Demo",
        cargo=Cargo.ASESOR,
        actividades=[A.CAPTACION],
    ),
    dict(
        email="carla@example.com",
        full_name="Carla Arriendos Demo",
        cargo=Cargo.ASESOR,
        actividades=[A.ARRIENDOS],
    ),
    dict(
        email="diego@example.com",
        full_name="Diego Ventas Demo",
        cargo=Cargo.ASESOR,
        actividades=[A.VENTAS, A.ARRIENDOS],
    ),
    dict(
        email="preventas@example.com",
        full_name="Pre-ventas Demo",
        cargo=Cargo.ASESOR,
        funcion=FuncionIndependiente.PRE_VENTAS,
    ),
    dict(
        email="auxiliar@example.com",
        full_name="Auxiliar Demo",
        cargo=Cargo.AUXILIAR_ADMINISTRATIVA,
    ),
    dict(email="atencion@example.com", full_name="Atención Demo", cargo=Cargo.ATENCION_CLIENTE),
]


def main() -> None:
    if not settings.is_dev:
        sys.exit(f"Refusing to seed demo users in environment '{settings.environment}'.")

    password = os.environ.get("SEED_PASSWORD", DEFAULT_PASSWORD)
    with SessionLocal() as db:
        for spec in DEMO_USERS:
            if get_user_by_email(db, spec["email"]):
                print(f"  exists   {spec['email']}")
                continue
            create_user(db, password=password, **spec)
            print(f"  created  {spec['email']}")
        db.flush()
        n = seed_leads(db)
        print(f"  leads    {n} created" if n else "  leads    already present, skipped")
        n = seed_captaciones(db)
        print(f"  captac.  {n} created" if n else "  captac.  already present, skipped")
        n = seed_preoperacional(db)
        print(f"  preop.   {n} created" if n else "  preop.   already present, skipped")
        n = seed_pedidos(db)
        print(f"  pedidos  {n} created" if n else "  pedidos  already present, skipped")
        n = seed_rendimiento(db)
        print(f"  rendim.  {n} leads created" if n else "  rendim.  already present, skipped")
        n = seed_compensacion(db)
        print(f"  compens. {n} closed deals" if n else "  compens. already present, skipped")
        n = seed_novedades(db)
        print(f"  noveda.  {n} absences" if n else "  noveda.  already present, skipped")
        n = seed_inmuebles(db)
        print(f"  inmueb.  {n} in the catalog" if n else "  inmueb.  already present, skipped")
        n = seed_administracion(db)
        print(f"  admin.   {n} records" if n else "  admin.   already present, skipped")
        db.commit()


if __name__ == "__main__":
    main()
