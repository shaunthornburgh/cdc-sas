"""Demo data for «Administración de inmuebles» (called from app.scripts.seed, after inmuebles).

Mirrors X14's example records, with dates relative to today so the KPIs have something to show:
an inventory with findings that became a repair, a clean one, two scheduled this week, repairs in
every stage, and requests open, late, answered and assigned to an asesor. Everything goes through
the service, as if the Auxiliar did it.
"""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Inmueble, Inventario, Reparacion, Solicitud
from app.models.enums import CanalSolicitud as C
from app.models.enums import CategoriaReparacion as K
from app.models.enums import EstadoAmbiente as E
from app.models.enums import EstadoReparacion as R
from app.models.enums import EstadoSolicitud as S
from app.models.enums import PagaReparacion as P
from app.models.enums import Prioridad
from app.models.enums import Solicitante as D
from app.models.enums import TipoInventario as T
from app.models.enums import TipoSolicitud as TS
from app.services import administracion as svc
from app.services.users import get_user_by_email


def seed_administracion(db: Session) -> int:
    if db.scalar(select(Inventario.id).limit(1)):
        return 0
    u = {
        k: get_user_by_email(db, f"{k}@example.com")
        for k in ("auxiliar", "gerencia", "asesor", "bruno", "carla", "diego")
    }
    if None in u.values():
        raise RuntimeError("Seed the demo users first.")
    inm = {i.codigo: i for i in db.scalars(select(Inmueble)).unique()}
    if "INM-0219" not in inm:
        raise RuntimeError("Seed the inmuebles first.")
    aux = u["auxiliar"]
    hoy = svc.hoy()
    d = lambda n: hoy + timedelta(days=n)  # noqa: E731

    def inventario(cod, tipo, dias, ref, resp, revisar=None, firmar=False):
        inv = svc.crear_inventario(
            db,
            {
                "inmueble_id": inm[cod].id,
                "tipo": tipo,
                "fecha": d(dias),
                "referencia": ref,
                "responsable_id": u[resp].id,
            },
            actor=aux,
        )
        if revisar is not None:
            for i, a in enumerate(inv.ambientes):
                estado, obs = revisar.get(a.nombre, (E.BUENO, None))
                svc.marcar_ambiente(
                    db,
                    inv,
                    a.id,
                    {"estado": estado, "observacion": obs, "fotos": 2 if obs else i % 2 + 1},
                    actor=u[resp],
                )
        if firmar:
            svc.firmar_inventario(db, inv, actor=aux)
        return inv

    inventario(
        "INM-0301",
        T.ENTREGA,
        -64,
        "CTO-0147 · Cliente Ejemplo 12",
        "asesor",
        revisar={},
        firmar=True,
    )
    con_nov = inventario(
        "INM-0219",
        T.RECEPCION,
        -31,
        "Contrato terminado · Cliente Ejemplo 38",
        "bruno",
        revisar={
            "Baños": (E.MALO, "grifo del baño principal dañado"),
            "Pisos y paredes": (E.REGULAR, "pintura con manchas en la habitación 2"),
        },
        firmar=True,
    )
    inventario("INM-0372", T.RECEPCION, 5, "CTO-0102 · Cliente Ejemplo 42", "carla")
    inventario("INM-0318", T.ENTREGA, 3, "NEG-0158 · Cliente Ejemplo 9", "asesor")

    # ---- repairs
    def reparacion(cod, titulo, cat, pri, sol, dias, avance=None, estados=(), fin=None):
        rep = svc.crear_reparacion(
            db,
            {
                "inmueble_id": inm[cod].id,
                "titulo": titulo,
                "categoria": cat,
                "prioridad": pri,
                "solicitante": sol,
                "fecha": d(dias),
                "responsable_id": aux.id,
            },
            actor=aux,
        )
        return _avanzar(db, rep, aux, avance, estados, fin)

    reparacion(
        "INM-0245",
        "Cerradura de la puerta principal",
        K.CERRAJERIA,
        Prioridad.URGENTE,
        "Inquilino · Cliente Ejemplo 40",
        -41,
        {"proveedor": "Proveedor Ejemplo 2", "valor": 95_000, "paga": P.PROPIETARIO},
        (R.COTIZADA, R.APROBADA, R.EN_EJECUCION, R.TERMINADA),
        fin=d(-39),
    )
    rep = svc.reparacion_desde_inventario(db, con_nov, actor=aux)
    rep.categoria = K.PLOMERIA
    _avanzar(
        db, rep, aux, {"proveedor": "Proveedor Ejemplo 1", "valor": 180_000}, (R.COTIZADA,), None
    )
    reparacion(
        "INM-0301",
        "Humedad en la habitación principal",
        K.HUMEDAD,
        Prioridad.URGENTE,
        "Inquilino · Cliente Ejemplo 12",
        -2,
    )
    reparacion(
        "INM-0255",
        "Tomacorrientes de la cocina sin energía",
        K.ELECTRICO,
        Prioridad.NORMAL,
        "Propietario · Fernando Zapata",
        -10,
        {"proveedor": "Proveedor Ejemplo 4", "valor": 320_000, "paga": P.PROPIETARIO},
        (R.COTIZADA, R.APROBADA, R.EN_EJECUCION),
    )

    # ---- requests
    def solicitud(cod, tipo, de, nombre, canal, texto, dias, resp, respuesta=None, estado=None):
        sol = svc.crear_solicitud(
            db,
            {
                "inmueble_id": inm[cod].id,
                "tipo": tipo,
                "de": de,
                "nombre": nombre,
                "canal": canal,
                "descripcion": texto,
                "fecha": d(dias),
                "responsable_id": u[resp].id,
            },
            actor=aux,
        )
        if estado:
            svc.estado_solicitud(
                db, sol, estado, nota="Se pidió cotización al proveedor", actor=aux
            )
        if respuesta:
            svc.responder_solicitud(db, sol, respuesta[0], actor=u[resp])
            sol.fecha_respuesta = d(dias + respuesta[1])
        return sol

    solicitud(
        "INM-0372",
        TS.RECLAMO,
        D.PROPIETARIO,
        "Propietario Ejemplo 5",
        C.LLAMADA,
        "Valor de la liquidación del mes pasado",
        -56,
        "gerencia",
        respuesta=("Se revisó y se explicó el descuento de la reparación con su soporte.", 7),
    )
    solicitud(
        "INM-0280",
        TS.QUEJA,
        D.INQUILINO,
        "Cliente Ejemplo 44",
        C.WHATSAPP,
        "Demora en la reparación del calentador",
        -36,
        "auxiliar",
        estado=S.EN_TRAMITE,
    )
    solicitud(
        "INM-0245",
        TS.PETICION,
        D.PROPIETARIO,
        "Propietario Ejemplo 2",
        C.CORREO,
        "Copia del estado de cuenta del mes pasado",
        -3,
        "auxiliar",
    )
    solicitud(
        "INM-0318",
        TS.PETICION,
        D.INQUILINO,
        "Cliente Ejemplo 9",
        C.OFICINA,
        "Copia del contrato antes de la entrega",
        -1,
        "asesor",
    )
    db.flush()
    return sum(
        db.scalar(select(func.count()).select_from(m)) or 0
        for m in (Inventario, Reparacion, Solicitud)
    )


def _avanzar(db, rep: Reparacion, actor, avance, estados, fin):
    if avance:
        svc.avance_reparacion(db, rep, avance, actor=actor)
    for e in estados:
        svc.estado_reparacion(db, rep, e, nota=None, actor=actor)
    if fin:  # it was finished back then
        rep.fecha_fin = fin
    return rep


__all__ = ["seed_administracion"]
