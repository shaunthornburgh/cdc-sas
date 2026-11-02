"""Demo integrations (G07), called from app.scripts.seed after plataformas.

Creates G07's catalog, sets the monthly costs of the ads and services (G07's quarter figures / 3)
and how their data arrives, and saves connection data for the three active portals and Facebook /
Instagram, which leaves them «Por confirmar conexión» (there are no real connectors). Done through
the service as Gerencia, so it shows in «Registro de cambios». No secret is stored.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Integracion
from app.services import integraciones as svc
from app.services.users import get_user_by_email

AJUSTES = {
    "ciencuadras": {"como": "correo"},
    "espacio_urbano": {"como": "correo"},
    "proppi": {"como": "correo"},
    "finca_raiz": {"como": "por_confirmar"},
    "metrocuadrado": {"como": "por_confirmar"},
    "facebook": {"como": "directa", "costo_mensual": 466_000},
    "instagram": {"como": "directa", "costo_mensual": 283_000},
    "tiktok": {"como": "directa", "costo_mensual": 83_000},
    "correo_avisos": {"como": "correo"},
    "whatsapp": {"como": "manual"},
    "maps": {"como": "directa", "costo_mensual": 32_000},
}
DATOS = {
    "ciencuadras": {"usuario": "CDC-CIEN-0418"},
    "espacio_urbano": {"usuario": "casadolcecasa"},
    "proppi": {"usuario": "CDC-PRP-77"},
    "facebook": {"cuenta": "act_000000", "formularios": "Todos los formularios activos"},
    "instagram": {"cuenta": "act_000000"},
}


def seed_integraciones(db: Session) -> int:
    ger = get_user_by_email(db, "gerencia@example.com")
    if ger is None:
        raise RuntimeError("Seed the demo users first.")
    svc.asegurar_catalogo(db)
    por_clave = {i.clave: i for i in db.scalars(select(Integracion)).unique()}
    if any(i.estado != "sin_conectar" or i.costo_mensual for i in por_clave.values()):
        return 0
    for clave, data in AJUSTES.items():
        svc.ajustes(db, por_clave[clave], data, actor=ger)
    for clave, valores in DATOS.items():
        svc.guardar_datos(db, por_clave[clave], valores, actor=ger)
    db.flush()
    return len(por_clave)
