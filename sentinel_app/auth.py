from functools import wraps

from flask import current_app, jsonify, request, session


def get_session_value(key, default=None):
    value = session.get(key)
    if value is not None:
        return value

    try:
        restored_session = current_app.session_interface.open_session(current_app, request)
    except Exception:
        return default

    if restored_session is None:
        return default

    return restored_session.get(key, default)


def is_authenticated():
    return bool(get_session_value("user_id"))


def is_admin_session():
    return is_authenticated() and get_session_value("role") == "admin"


def is_member_session():
    return is_authenticated() and get_session_value("role") == "user"


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
        if not is_admin_session():
            return jsonify({"status": "error", "message": "Forbidden"}), 403
        return fn(*args, **kwargs)

    return wrapper


def member_required_json(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_authenticated():
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        if not is_member_session():
            return jsonify({"status": "error", "message": "Admins cannot access messages"}), 403
        return fn(*args, **kwargs)

    return wrapper

