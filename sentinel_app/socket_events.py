from collections import defaultdict

from flask import request
from flask_socketio import emit, join_room

from .auth import get_active_user_record, get_session_value
from .data import set_user_presence
from .extensions import socketio
from .time_utils import serialize_utc_timestamp


_connected_user_sids = defaultdict(set)
_sid_context = {}


def _serialize_presence_timestamp(value):
    return serialize_utc_timestamp(value)


def _track_user_connection(user, sid):
    user_id = user["id"]
    was_offline = not _connected_user_sids[user_id]
    _connected_user_sids[user_id].add(sid)
    _sid_context[sid] = {
        "user_id": user_id,
        "username": user["username"],
        "role": user["role"],
        "status": user["status"],
    }
    return was_offline


def _release_user_connection(sid):
    context = _sid_context.pop(sid, None)
    if not context:
        return None, False

    user_id = context["user_id"]
    user_connections = _connected_user_sids.get(user_id, set())
    user_connections.discard(sid)
    if user_connections:
        return context, False

    _connected_user_sids.pop(user_id, None)
    return context, True


def _emit_presence_update(context, is_online, last_seen=None):
    socketio.emit(
        "presence_update",
        {
            "user_id": context.get("user_id", context.get("id")),
            "username": context["username"],
            "role": context["role"],
            "status": context["status"],
            "is_online": bool(is_online),
            "last_seen": _serialize_presence_timestamp(last_seen),
        },
        room="admins",
    )


def disconnect_member_sessions(user_id):
    if not user_id:
        return

    for sid in list(_connected_user_sids.get(user_id, ())):
        if sid in _sid_context:
            _sid_context[sid]["status"] = "banned"
        socketio.emit(
            "access_revoked",
            {"message": "Your account has been banned. You have been removed from the member workspace."},
            room=sid,
        )
        socketio.server.disconnect(sid)


def register_socketio_events():
    @socketio.on("connect")
    def handle_connect(_auth=None):
        user = get_active_user_record()
        if not user:
            return False

        first_connection = _track_user_connection(user, request.sid)
        join_room(f"user:{user['id']}")
        if user["role"] == "admin":
            join_room("admins")
            emit("system", {"message": "Connected to admin presence channel"})
        else:
            join_room("members")
            emit("system", {"message": "Connected to real-time server"})

        if first_connection:
            set_user_presence(user["id"], True)
            _emit_presence_update(user, is_online=True)

    @socketio.on("typing")
    def handle_typing(data=None):
        user = get_active_user_record()
        if not user or user["role"] != "member":
            socketio.server.disconnect(request.sid)
            return False

        payload = data or {}
        emit(
            "typing",
            {
                "username": get_session_value("username"),
                "active": bool(payload.get("active", True)),
            },
            room="members",
            include_self=False,
        )

    @socketio.on("disconnect")
    def handle_disconnect():
        context, should_mark_offline = _release_user_connection(request.sid)
        if not context or not should_mark_offline:
            return

        last_seen = set_user_presence(context["user_id"], False)
        _emit_presence_update(context, is_online=False, last_seen=last_seen)
