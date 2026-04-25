import app as app_module
from sentinel_app.socket_events import disconnect_member_sessions


def _member_client(app, dummy_cursor):
    dummy_cursor.current_user_record = {
        "id": 2,
        "username": "normaluser",
        "role": "user",
        "is_banned": False,
        "is_deleted": False,
    }
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = 2
        sess["username"] = "normaluser"
        sess["role"] = "user"
    return client


def _admin_client(app, dummy_cursor):
    dummy_cursor.current_user_record = {
        "id": 1,
        "username": "adminuser",
        "role": "admin",
        "is_banned": False,
        "is_deleted": False,
    }
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = "adminuser"
        sess["role"] = "admin"
    return client


def test_socketio_client_connects(app, socketio_client):
    assert socketio_client.is_connected()


def test_socketio_connect_emits_system_message(app, socketio_client):
    received = socketio_client.get_received()

    assert any(event["name"] == "system" for event in received)

    system_events = [event for event in received if event["name"] == "system"]
    assert len(system_events) >= 1
    assert system_events[0]["args"][0]["message"] == "Connected to real-time server"


def test_socketio_multiple_member_clients_can_connect(app, socketio, dummy_cursor):
    member_one = _member_client(app, dummy_cursor)
    member_two = _member_client(app, dummy_cursor)

    client_one = socketio.test_client(app, flask_test_client=member_one)
    client_two = socketio.test_client(app, flask_test_client=member_two)

    try:
        assert client_one.is_connected()
        assert client_two.is_connected()
    finally:
        if client_one.is_connected():
            client_one.disconnect()
        if client_two.is_connected():
            client_two.disconnect()


def test_socketio_emit_new_message_broadcasts_to_connected_member_clients(app, socketio, dummy_cursor):
    member_one = _member_client(app, dummy_cursor)
    member_two = _member_client(app, dummy_cursor)

    client_one = socketio.test_client(app, flask_test_client=member_one)
    client_two = socketio.test_client(app, flask_test_client=member_two)

    try:
        client_one.get_received()
        client_two.get_received()

        socketio.emit(
            "new_message",
            {
                "username": "normaluser",
                "message": "hello from test",
                "created_at": "just now",
            },
        )

        received_one = client_one.get_received()
        received_two = client_two.get_received()

        assert any(event["name"] == "new_message" for event in received_one)
        assert any(event["name"] == "new_message" for event in received_two)

        payload_one = [event["args"][0] for event in received_one if event["name"] == "new_message"][0]
        payload_two = [event["args"][0] for event in received_two if event["name"] == "new_message"][0]

        assert payload_one["username"] == "normaluser"
        assert payload_one["message"] == "hello from test"
        assert payload_one["created_at"] == "just now"

        assert payload_two["username"] == "normaluser"
        assert payload_two["message"] == "hello from test"
        assert payload_two["created_at"] == "just now"
    finally:
        if client_one.is_connected():
            client_one.disconnect()
        if client_two.is_connected():
            client_two.disconnect()


def test_socketio_typing_broadcasts_to_other_members(app, socketio, dummy_cursor):
    member_one = _member_client(app, dummy_cursor)
    member_two = _member_client(app, dummy_cursor)

    sender = socketio.test_client(app, flask_test_client=member_one)
    receiver = socketio.test_client(app, flask_test_client=member_two)

    try:
        sender.get_received()
        receiver.get_received()

        sender.emit("typing", {"active": True})
        received = receiver.get_received()

        assert any(event["name"] == "typing" for event in received)
        payload = [event["args"][0] for event in received if event["name"] == "typing"][0]
        assert payload["username"] == "normaluser"
        assert payload["active"] is True
    finally:
        if sender.is_connected():
            sender.disconnect()
        if receiver.is_connected():
            receiver.disconnect()


def test_socketio_allows_admin_presence_connections(app, socketio, dummy_cursor):
    admin_client = _admin_client(app, dummy_cursor)
    socket_client = socketio.test_client(app, flask_test_client=admin_client)

    try:
        assert socket_client.is_connected() is True
        received = socket_client.get_received()
        assert any(event["name"] == "system" for event in received)
        system_events = [event for event in received if event["name"] == "system"]
        assert system_events[0]["args"][0]["message"] == "Connected to admin presence channel"
    finally:
        if socket_client.is_connected():
            socket_client.disconnect()


def test_socketio_rejects_banned_member_connections(app, socketio, dummy_cursor):
    dummy_cursor.current_user_record = {
        "id": 2,
        "username": "normaluser",
        "role": "user",
        "is_banned": True,
        "is_deleted": False,
    }
    banned_client = app.test_client()
    with banned_client.session_transaction() as sess:
        sess["user_id"] = 2
        sess["username"] = "normaluser"
        sess["role"] = "user"

    socket_client = socketio.test_client(app, flask_test_client=banned_client)

    assert socket_client.is_connected() is False


def test_disconnect_member_sessions_disconnects_connected_members(app, socketio, dummy_cursor):
    member_client = _member_client(app, dummy_cursor)
    socket_client = socketio.test_client(app, flask_test_client=member_client)

    try:
        assert socket_client.is_connected()
        disconnect_member_sessions(2)
        assert socket_client.is_connected() is False
    finally:
        if socket_client.is_connected():
            socket_client.disconnect()


def test_socketio_client_disconnects_cleanly(socketio_client):
    assert socketio_client.is_connected()
    socketio_client.disconnect()
    assert not socketio_client.is_connected()
