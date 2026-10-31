"""Who can do what, as plain predicates (used by services and by API dependencies)."""

from app.models import User
from app.models.enums import ActividadComercial, Cargo, FuncionIndependiente

# Manage users, toggle activities, see and manage every lead and cita.
USER_MANAGERS = (Cargo.GERENCIA, Cargo.COORDINACION)

# Independent functions that work the Atención al Cliente / Pre-ventas module.
LEAD_FUNCIONES = (FuncionIndependiente.ATENCION_CLIENTE, FuncionIndependiente.PRE_VENTAS)


def is_manager(user: User) -> bool:
    return user.cargo in USER_MANAGERS


def can_use_leads(user: User) -> bool:
    """Atención al Cliente / Pre-ventas, plus Coordinación and Gerencia."""
    return is_manager(user) or user.funcion in LEAD_FUNCIONES


def can_capture(user: User) -> bool:
    """Has the Captación activity (and so registers captaciones and uses GPS)."""
    return user.is_active and user.has_actividad(ActividadComercial.CAPTACION)


def can_use_captaciones(user: User) -> bool:
    """Captadores see their own captaciones; Coordinación and Gerencia verify all of them."""
    return is_manager(user) or can_capture(user)


def has_commercial_activity(user: User) -> bool:
    """Asesores: at least one of Captación, Ventas, Arriendos (and no independent function)."""
    return user.is_active and user.funcion is None and bool(user.actividades)


def can_use_asesor_home(user: User) -> bool:
    return has_commercial_activity(user) or is_manager(user)


def can_use_pedidos(user: User) -> bool:
    """Asesores, Atención / Pre-ventas, Coordinación and Gerencia (prototypes M06, C10, K06)."""
    return has_commercial_activity(user) or user.funcion in LEAD_FUNCIONES or is_manager(user)


def can_own_pedidos(user: User) -> bool:
    """People who can be «responsable» of a pedido."""
    return user.is_active and (has_commercial_activity(user) or user.funcion in LEAD_FUNCIONES)
