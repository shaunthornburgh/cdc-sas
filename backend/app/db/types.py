from enum import Enum

from sqlalchemy import Enum as SAEnum


def pg_enum(enum_cls: type[Enum], name: str, *, create_type: bool = True) -> SAEnum:
    """Native Postgres enum that stores the enum *values* (e.g. 'gerencia'), not member names.

    `create_type=False` reuses a type another table already created.
    """
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        create_type=create_type,
    )
