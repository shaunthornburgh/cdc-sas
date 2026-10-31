"""Demo absences and permits (K13), called from app.scripts.seed after compensación.

Mirrors K13's example rows in the current month (incapacidades, permisos no remunerados and a
paid permit), plus one annulled by mistake. Registered through the service, so the unconfirmed
pay periods get their discounts. Preoperacional novedades come from seed_preoperacional.
"""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Novedad
from app.models.enums import TipoNovedad as T
from app.services import novedades as svc
from app.services.users import get_user_by_email

# email prefix, tipo, day offset in this month, days, observación, soportes, registered by
FILAS = [
    ("diego", T.INCAPACIDAD, 0, 2, "Certificado EPS adjunto", 1, "coordinacion"),
    ("bruno", T.INCAPACIDAD, 0, 2, "Certificado EPS adjunto", 1, "auxiliar"),
    ("carla", T.PERMISO_NO_REMUNERADO, 0, 2, "Diligencia personal", 0, "coordinacion"),
    ("asesor", T.PERMISO_NO_REMUNERADO, 1, 1, "Asunto familiar", 0, "coordinacion"),
    ("atencion", T.PERMISO_REMUNERADO, 1, 1, "Cita médica", 0, "auxiliar"),
    ("preventas", T.PERMISO_REMUNERADO, 15, 1, "Calamidad doméstica", 0, "auxiliar"),
    # 2nd pay period, still unconfirmed in the demo: «Salarios del mes» shows the discount.
    ("preventas", T.PERMISO_NO_REMUNERADO, 19, 2, "Trámite personal", 0, "coordinacion"),
]


def seed_novedades(db: Session) -> int:
    if db.scalar(select(Novedad.id).limit(1)):
        return 0
    u = {
        k: get_user_by_email(db, f"{k}@example.com")
        for k in (
            "coordinacion",
            "auxiliar",
            "asesor",
            "bruno",
            "carla",
            "diego",
            "preventas",
            "atencion",
        )  # noqa: E501
    }
    if None in u.values():
        raise RuntimeError("Seed the demo users first.")
    inicio, _ = svc.mes_actual()
    for emp, tipo, n, dias, obs, sop, por in FILAS:
        d1 = inicio + timedelta(days=n)
        svc.crear(
            db,
            {
                "empleado_id": u[emp].id,
                "tipo": tipo,
                "desde": d1,
                "hasta": d1 + timedelta(days=dias - 1),
                "observacion": obs,
                "soportes": sop,
            },
            actor=u[por],
        )
    # A mistake, annulled: it stays on record but doesn't count.
    mal, _ = svc.crear(
        db,
        {
            "empleado_id": u["asesor"].id,
            "tipo": T.INCAPACIDAD,
            "desde": inicio + timedelta(days=8),
            "hasta": inicio + timedelta(days=9),
            "observacion": "Registrada al empleado equivocado",
        },
        actor=u["auxiliar"],
    )
    svc.anular(db, mal, "Era de otra persona", actor=u["coordinacion"])
    db.flush()
    return db.scalar(select(func.count()).select_from(Novedad)) or 0
