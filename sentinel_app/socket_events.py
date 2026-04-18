from flask_socketio import emit, join_room

from .auth import get_session_value, is_member_session
from .extensions import socketio


def register_socketio_events():
    @socketio.on("connect")
    def handle_connect():
        if not is_member_session():
            return False
        join_room("members")
        emit("system", {"message": "Connected to real-time server"})

    @socketio.on("typing")
    def handle_typing(data=None):
        if not is_member_session():
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

