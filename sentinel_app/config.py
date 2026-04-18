import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_local_env(path):
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def resolve_socketio_async_mode(requested_mode):
    mode = (requested_mode or "threading").strip().lower()
    if mode != "eventlet":
        return mode

    if os.name == "nt":
        return "threading"

    try:
        import eventlet  # noqa: F401
    except ImportError:
        return "threading"

    return mode


def apply_config(app, test_config=None):
    load_local_env(PROJECT_ROOT / ".env")

    flask_env = os.environ.get("FLASK_ENV", "production")
    requested_async_mode = os.environ.get("SOCKETIO_ASYNC_MODE", "threading")

    app.config.update(
        ENV=flask_env,
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=env_bool("SESSION_COOKIE_SECURE", default=False),
        SESSION_COOKIE_SAMESITE="Lax",
        WTF_CSRF_HEADERS=["X-CSRFToken", "X-CSRF-Token"],
        WTF_CSRF_TIME_LIMIT=int(os.environ.get("WTF_CSRF_TIME_LIMIT", "14400")),
        MYSQL_HOST=os.environ.get("MYSQL_HOST", "localhost"),
        MYSQL_USER=os.environ.get("MYSQL_USER", "root"),
        MYSQL_PASSWORD=os.environ.get("MYSQL_PASSWORD", ""),
        MYSQL_DB=os.environ.get("MYSQL_DB", "secure_panel"),
        MYSQL_CURSORCLASS="DictCursor",
        REQUESTED_SOCKETIO_ASYNC_MODE=requested_async_mode,
        SOCKETIO_ASYNC_MODE=resolve_socketio_async_mode(requested_async_mode),
        RATELIMIT_ENABLED=env_bool("RATELIMIT_ENABLED", default=True),
        TESTING=False,
    )

    if test_config:
        app.config.update(test_config)

