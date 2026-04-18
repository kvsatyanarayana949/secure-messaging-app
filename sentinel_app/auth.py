from functools import wraps

from flask import current_app, g, jsonify, request, session

from .data import get_cursor


_MISSING = object()


def get_session_value(key, default=None):
    if getattr(g, "_session_invalidated", False):
        return default

    if key in session:
        return session.get(key, default)

    restored_session = getattr(g, "_restored_session", _MISSING)
    if restored_session is _MISSING:
        try:
            restored_session = current_app.session_interface.open_session(current_app, request)
        except Exception:
            restored_session = None
        g._restored_session = restored_session

    if restored_session is None or getattr(g, "_session_invalidated", False):
        return default

    return restored_session.get(key, default)


def invalidate_session(preserve_csrf=True):
    csrf_token = session.get("csrf_token") if preserve_csrf else None
    session.clear()
    if csrf_token:
        session["csrf_token"] = csrf_token

    g._session_invalidated = True
    g._current_user_loaded = True
    g._current_user_record = None


def get_current_user_record():
    if getattr(g, "_current_user_loaded", False):
        return getattr(g, "_current_user_record", None)

    g._current_user_lookup_failed = False
    user_id = get_session_value("user_id")
    g._requested_user_id = user_id
    if not user_id:
        g._current_user_loaded = True
        g._current_user_record = None
        return None

    cur = None
    try:
        cur = get_cursor()
        cur.execute(
            "SELECT id, username, role, is_banned, is_deleted FROM users WHERE id=%s",
            (user_id,),
        )
        user = cur.fetchone()
    except Exception:
        current_app.logger.error("Failed to load session user", exc_info=True)
        g._current_user_lookup_failed = True
        user = None
    finally:
        if cur:
            cur.close()

    g._current_user_loaded = True
    g._current_user_record = user
    return user


def get_active_user_record():
    user = get_current_user_record()
    if getattr(g, "_current_user_lookup_failed", False):
        return None

    if not user:
        if getattr(g, "_requested_user_id", None):
            invalidate_session()
        return None

    if user["is_deleted"] or user["is_banned"]:
        invalidate_session()
        return None

    return user


def is_authenticated():
    return bool(get_session_value("user_id"))


def is_admin_session():
    user = get_active_user_record()
    return bool(user and user["role"] == "admin")


def is_member_session():
    user = get_active_user_record()
    return bool(user and user["role"] == "user")


def login_required_json(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_authenticated():
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        return fn(*args, **kwargs)

    return wrapper


def admin_required_json(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user_record()
        if getattr(g, "_current_user_lookup_failed", False):
            return jsonify({"status": "error", "message": "Authorization unavailable"}), 503
        if not user or user["is_deleted"]:
            if getattr(g, "_requested_user_id", None):
                invalidate_session()
            return jsonify({"status": "error", "message": "Forbidden"}), 403
        if user["is_banned"]:
            invalidate_session()
            return jsonify({"status": "error", "message": "Forbidden"}), 403
        if user["role"] != "admin":
            return jsonify({"status": "error", "message": "Forbidden"}), 403
        return fn(*args, **kwargs)

    return wrapper


def member_required_json(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_authenticated():
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        user = get_current_user_record()
        if getattr(g, "_current_user_lookup_failed", False):
            return jsonify({"status": "error", "message": "Authorization unavailable"}), 503
        if not user or user["is_deleted"]:
            invalidate_session()
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        if user["is_banned"]:
            invalidate_session()
            return jsonify({"status": "error", "message": "You are banned"}), 403
        if user["role"] != "user":
            return jsonify({"status": "error", "message": "Admins cannot access messages"}), 403
        return fn(*args, **kwargs)

    return wrapper
