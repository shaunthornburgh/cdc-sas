"""Reusable permission dependencies.

Examples:

    # Only Gerencia or Coordinación (as a route-level guard)
    solo_direccion = require_cargo(Cargo.GERENCIA, Cargo.COORDINACION)
    @router.get("/reportes", dependencies=[Depends(solo_direccion)])

    # Needs Captación active, and you want the user object
    @router.post("/checkin")
    Captador = Annotated[User, Depends(require_actividad(ActividadComercial.CAPTACION))]
    def checkin(user: Captador): ...

    # Needs Ventas AND Arriendos
    require_actividad(ActividadComercial.VENTAS, ActividadComercial.ARRIENDOS, require_all=True)

No implicit superuser: if Gerencia should pass a check, list it explicitly.
"""

from collections.abc import Callable

from fastapi import HTTPException, status

from app.api.deps import CurrentUser
from app.models import User
from app.models.enums import ActividadComercial, Cargo, FuncionIndependiente
from app.services.policies import LEAD_FUNCIONES, USER_MANAGERS, can_use_leads


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def require_cargo(*cargos: Cargo) -> Callable[[User], User]:
    """Allow users whose cargo is any of `cargos`."""
    allowed = frozenset(cargos)

    def dependency(user: CurrentUser) -> User:
        if user.cargo not in allowed:
            raise _forbidden("Tu cargo no tiene acceso a este recurso.")
        return user

    return dependency


def require_actividad(
    *actividades: ActividadComercial, require_all: bool = False
) -> Callable[[User], User]:
    """Allow users with any (default) or all of the given commercial activities active."""
    wanted = frozenset(actividades)

    def dependency(user: CurrentUser) -> User:
        active = set(user.actividades)
        ok = wanted <= active if require_all else bool(wanted & active)
        if not ok:
            raise _forbidden("No tienes activa la actividad requerida.")
        return user

    return dependency


def require_funcion(*funciones: FuncionIndependiente) -> Callable[[User], User]:
    """Allow users assigned to any of the given independent functions."""
    allowed = frozenset(funciones)

    def dependency(user: CurrentUser) -> User:
        if user.funcion not in allowed:
            raise _forbidden("Tu función no tiene acceso a este recurso.")
        return user

    return dependency


def require_leads_module(user: CurrentUser) -> User:
    """Atención al Cliente and Pre-ventas, plus Coordinación and Gerencia.

    Asesores with only commercial activities (and Auxiliar administrativa) are refused.
    """
    if not can_use_leads(user):
        raise _forbidden("Este módulo es de Atención al Cliente y Pre-ventas.")
    return user


__all__ = [
    "LEAD_FUNCIONES",
    "USER_MANAGERS",
    "require_actividad",
    "require_cargo",
    "require_funcion",
    "require_leads_module",
]
