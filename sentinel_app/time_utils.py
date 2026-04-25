from datetime import UTC, datetime


TIMESTAMP_FIELDS = frozenset({"created_at", "last_login_at", "last_seen"})


def utc_now():
    return datetime.now(UTC).replace(microsecond=0)


def utc_now_naive():
    return utc_now().replace(tzinfo=None)


def parse_utc_timestamp(value):
    if value in (None, ""):
        return None

    if isinstance(value, datetime):
        candidate = value
    else:
        text = str(value).strip()
        if not text:
            return None
        normalized = f"{text[:-1]}+00:00" if text.endswith("Z") else text
        try:
            candidate = datetime.fromisoformat(normalized)
        except ValueError:
            return None

    if candidate.tzinfo is None:
        return candidate.replace(tzinfo=UTC)
    return candidate.astimezone(UTC)


def serialize_utc_timestamp(value):
    parsed = parse_utc_timestamp(value)
    if parsed is None:
        return value
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")
