"""Demo pólizas (X11 · G-087 · G-072), called from app.scripts.seed after compensación.

The prototype's three example insurers with their plazos (70 / 45 / 60 days, warn 10 before) and
five policies (prices, study costs, response days and coverages from X11's comparator). The nine
closed rental deals get a policy in every state of the flow (one expired and one about to expire
for the alerts, a denied one that can be retaken, a second study…), and older contracts give the
indicators history. Dates are relative to today. All are DATOS DE EJEMPLO.
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Aseguradora, Cierre, Inmueble, Poliza, PolizaTipo
from app.models.enums import EstadoInmueble, TipoNegocio
from app.services import fechas
from app.services.users import get_user_by_email

ASEGURADORAS = [
    (
        "Entidad 1 (ejemplo)",
        70,
        [
            ("Tipo de póliza 1 (ejemplo)", "2.0", 0, 1, ["can", "adm"]),
            ("Tipo de póliza 2 (ejemplo)", "2.8", 0, 1, ["can", "adm", "ser", "dan"]),
        ],
    ),
    (
        "Entidad 2 (ejemplo)",
        45,
        [
            ("Tipo de póliza 1 (ejemplo)", "1.9", 45_000, 2, ["can", "adm"]),
            ("Tipo de póliza 2 (ejemplo)", "3.1", 45_000, 2, ["can", "adm", "ser", "dan", "jur"]),
        ],
    ),
    (
        "Entidad 3 (ejemplo)",
        60,
        [
            ("Tipo de póliza 3 (ejemplo)", "2.4", 30_000, 3, ["can", "adm", "ser"]),
        ],
    ),
]
# Older contracts: (insurer, type, canon, activated, description, with property insurance)
HISTORICOS = [
    (0, 0, 1_200_000, date(2024, 3, 5), "Apto Belén", True),
    (0, 0, 1_650_000, date(2025, 5, 20), "Apto Laureles", True),
    (0, 1, 2_400_000, date(2025, 6, 8), "Casa Envigado", True),
    (0, 0, 1_500_000, date(2026, 7, 15), "Apto Sabaneta", False),
    (0, 0, 1_700_000, date(2026, 9, 18), "Apto Laureles", True),
    (0, 1, 2_300_000, date(2026, 2, 3), "Apto El Poblado", True),
    (1, 0, 1_350_000, date(2024, 8, 12), "Apto Belén", True),
    (1, 0, 1_450_000, date(2026, 8, 4), "Apto Belén", False),
    (1, 1, 2_600_000, date(2026, 7, 1), "Apto El Poblado", True),
    (1, 0, 1_800_000, date(2025, 11, 14), "Apto Laureles", True),
    (2, 0, 2_100_000, date(2025, 2, 3), "Apto Sabaneta", True),
    (2, 0, 1_900_000, date(2026, 9, 2), "Apto Envigado", False),
]


def seed_polizas(db: Session) -> int:
    if db.scalar(select(Aseguradora.id).limit(1)) is not None:
        return 0
    aux = get_user_by_email(db, "auxiliar@example.com")
    hoy = fechas.local_date(fechas.now())
    tipos: list[list[PolizaTipo]] = []
    for nombre, dias, ts in ASEGURADORAS:
        a = Aseguradora(nombre=nombre, dias_max=dias, aviso_dias=10, ejemplo=True)
        db.add(a)
        db.flush()
        fila = []
        for tn, pct, est, resp, cob in ts:
            t = PolizaTipo(
                aseguradora_id=a.id,
                nombre=tn,
                precio_pct=Decimal(pct),
                costo_estudio=est,
                dias_respuesta=resp,
                coberturas=cob,
            )
            db.add(t)
            fila.append(t)
        tipos.append(fila)
    db.flush()

    def pol(t: PolizaTipo, canon: int, **kw) -> Poliza:
        p = Poliza(
            tipo_id=t.id,
            aseguradora_id=t.aseguradora_id,
            canon=canon,
            created_by_id=aux.id if aux else None,
            **kw,
        )
        db.add(p)
        return p

    n = 0
    for ia, it, canon, act, desc, seg in HISTORICOS:
        if act > hoy:
            continue
        pol(
            tipos[ia][it],
            canon,
            descripcion=desc,
            estado="activa",
            estudio_fecha=act - timedelta(days=20),
            decision_fecha=act - timedelta(days=18),
            firma_fecha=act - timedelta(days=12),
            activada_fecha=act,
            numero_poliza=f"POL-{100000 + n * 7919 % 900000}",
            seguro_inmueble=seg,
        )
        n += 1

    cierres = list(
        db.scalars(
            select(Cierre).where(Cierre.negocio == TipoNegocio.ARRIENDO).order_by(Cierre.numero)
        ).unique()
    )
    inms = list(
        db.scalars(
            select(Inmueble)
            .where(
                Inmueble.negocio == TipoNegocio.ARRIENDO, Inmueble.estado != EstadoInmueble.RETIRADO
            )
            .order_by(Inmueble.estado.desc(), Inmueble.codigo)
        ).unique()
    )
    d = lambda k: hoy - timedelta(days=k)  # noqa: E731
    # (insurer, type, state fields) for each closed rental deal, in order
    plan = [
        (1, 0, dict(estado="en_estudio", estudio_fecha=d(3), radicado="RAD-55120")),
        (
            1,
            0,
            dict(
                estado="aprobada",
                estudio_fecha=d(62),
                decision_fecha=d(60),
                firma_fecha=d(53),
                radicado="RAD-54011",
            ),
        ),  # vencida: Entidad 2 gives 45 days
        (
            0,
            0,
            dict(
                estado="aprobada",
                estudio_fecha=d(70),
                decision_fecha=d(68),
                firma_fecha=d(62),
                radicado="RAD-10442",
            ),
        ),  # por vencer: 8 days left of 70
        (
            2,
            0,
            dict(
                estado="aprobada",
                estudio_fecha=d(12),
                decision_fecha=d(9),
                firma_fecha=d(5),
                radicado="RAD-30871",
            ),
        ),
        (
            1,
            1,
            dict(
                estado="negada",
                estudio_fecha=d(10),
                decision_fecha=d(8),
                radicado="RAD-54390",
                motivo_negada="El codeudor no demostró ingresos suficientes",
            ),
        ),
        (
            0,
            0,
            dict(
                estado="activa",
                estudio_fecha=d(55),
                decision_fecha=d(53),
                firma_fecha=d(45),
                activada_fecha=d(40),
                numero_poliza="POL-204551",
                radicado="RAD-10390",
                seguro_inmueble=True,
            ),
        ),
        (
            1,
            1,
            dict(
                estado="activa",
                estudio_fecha=d(45),
                decision_fecha=d(43),
                firma_fecha=d(36),
                activada_fecha=d(30),
                numero_poliza="POL-338120",
                radicado="RAD-53977",
                seguro_inmueble=True,
            ),
        ),
        (
            0,
            1,
            dict(estado="aprobada", estudio_fecha=d(6), decision_fecha=d(2), radicado="RAD-10501"),
        ),
        (
            2,
            0,
            dict(
                estado="en_estudio",
                estudio_fecha=d(2),
                radicado="RAD-30902",
                estudios=2,
                retomada_motivo="Cambió el codeudor: ahora es la hermana del cliente",
            ),
        ),
    ]
    for k, (c, (ia, it, kw)) in enumerate(zip(cierres, plan, strict=False)):
        inm = inms[k] if k < len(inms) else None
        canon = c.valor or (inm.precio if inm and inm.precio else 1_800_000)
        pol(tipos[ia][it], canon, cierre_id=c.id, inmueble_id=inm.id if inm else None, **kw)
        n += 1
    db.flush()
    return n
