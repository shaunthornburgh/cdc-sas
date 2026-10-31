import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.security import verify_password
from app.models.enums import ActividadComercial as A
from app.models.enums import Cargo, FuncionIndependiente
from app.services.users import DomainError, set_actividades


def test_password_is_hashed_with_argon2(make_user):
    user = make_user(password="s3cret-pass")
    assert user.hashed_password.startswith("$argon2id$")
    assert verify_password("s3cret-pass", user.hashed_password)
    assert not verify_password("wrong", user.hashed_password)


def test_duplicate_email_rejected(make_user):
    make_user(email="dup@example.com")
    with pytest.raises(DomainError):
        make_user(email="DUP@example.com")


def test_atencion_cliente_gets_its_funcion_and_no_activities(make_user):
    user = make_user(Cargo.ATENCION_CLIENTE)
    assert user.funcion == FuncionIndependiente.ATENCION_CLIENTE
    with pytest.raises(DomainError):
        set_actividades(None, user, [A.VENTAS])  # type: ignore[arg-type]


def test_funcion_and_activities_cannot_mix(make_user):
    with pytest.raises(DomainError):
        make_user(funcion=FuncionIndependiente.PRE_VENTAS, actividades=[A.CAPTACION])


def test_set_actividades_toggles_and_tracks_who(db, make_user):
    coord = make_user(Cargo.COORDINACION)
    asesor = make_user(actividades=[A.CAPTACION])
    assert asesor.gps_checkin_enabled

    set_actividades(db, asesor, [A.VENTAS, A.ARRIENDOS], actor=coord)
    db.expire_all()

    assert asesor.actividades == [A.VENTAS, A.ARRIENDOS]
    assert not asesor.gps_checkin_enabled
    assert {link.granted_by_id for link in asesor.actividad_links} == {coord.id}


def test_db_trigger_blocks_activity_for_user_with_funcion(db, make_user):
    user = make_user(funcion=FuncionIndependiente.PRE_VENTAS)
    with pytest.raises(IntegrityError, match="independent function"):
        db.execute(
            text("INSERT INTO user_actividades (user_id, actividad) VALUES (:id, 'ventas')"),
            {"id": user.id},
        )


def test_db_trigger_blocks_funcion_for_user_with_activities(db, make_user):
    user = make_user(actividades=[A.VENTAS])
    with pytest.raises(IntegrityError, match="commercial activities"):
        db.execute(text("UPDATE users SET funcion = 'pre_ventas' WHERE id = :id"), {"id": user.id})


def test_db_check_atencion_cliente_requires_funcion(db, make_user):
    user = make_user(Cargo.ATENCION_CLIENTE)
    with pytest.raises(IntegrityError, match="ck_users_atencion_cliente_funcion"):
        db.execute(text("UPDATE users SET funcion = NULL WHERE id = :id"), {"id": user.id})
