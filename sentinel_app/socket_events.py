from collections import defaultdict

from flask import request
from flask_socketio import emit, join_room

from .auth import get_current_user_record, get_session_value, is_member_session
from .extensions import socketio


_connected_member_sids = defaultdict(set)
_sid_to_user_id = {}


def _track_member_connection(user_id, sid):
    _connected_member_sids[user_id].add(sid)
    _sid_to_user_id[sid] = user_id


def _release_member_connection(sid):
    user_id = _sid_to_user_id.pop(sid, None)
    if user_id is None:
        return

    user_connections = _connected_member_sids.get(user_id)
    if not user_connections:
        return

    user_connections.discard(sid)
    if not user_connections:
        _connected_member_sids.pop(user_id, None)


def disconnect_member_sessions(user_id):
    if not user_id:
        return

    for sid in list(_connected_member_sids.get(user_id, ())):
        socketio.emit(
            "access_revoked",
            {"message": "Your account has been banned. You have been removed from the member workspace."},
            room=sid,
        )
        socketio.server.leave_room(sid, "members")
        socketio.server.leave_room(sid, f"user:{user_id}")
        socketio.server.disconnect(sid)
        _release_member_connection(sid)


def register_socketio_events():
    @socketio.on("connect")
    def handle_connect():
        if not is_member_session():
            return False
        user = get_current_user_record()
        _track_member_connection(user["id"], request.sid)
        join_room("members")
        join_room(f"user:{user['id']}")
        emit("system", {"message": "Connected to real-time server"})

    @socketio.on("typing")
    def handle_typing(data=None):
        if not is_member_session():
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
        _release_member_connection(request.sid)
