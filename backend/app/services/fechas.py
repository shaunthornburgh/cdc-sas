"""Dates in Colombia time (UTC-5, no daylight saving) and short Spanish formatting."""

from datetime import UTC, date, datetime, time, timedelta, timezone

BOGOTA = timezone(timedelta(hours=-5), "America/Bogota")
_DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def now() -> datetime:
    return datetime.now(UTC)


def local_date(dt: datetime) -> date:
    return dt.astimezone(BOGOTA).date()


def start_of_day(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=BOGOTA)


def fmt(dt: datetime) -> str:
    """'lun 6 oct 11:00' (Bogotá time)."""
    d = dt.astimezone(BOGOTA)
    return f"{_DIAS[d.weekday()]} {d.day} {_MESES[d.month - 1]} {d:%H:%M}"
