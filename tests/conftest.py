import os
import pytest
import sentinel_app.data as data_module

os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["MYSQL_HOST"] = "localhost"
os.environ["MYSQL_USER"] = "root"
os.environ["MYSQL_PASSWORD"] = "rootpassword"
os.environ["MYSQL_DB"] = "secure_panel"
os.environ["SESSION_COOKIE_SECURE"] = "false"
os.environ["SOCKETIO_ASYNC_MODE"] = "threading"

import app as app_module


class DummyCursor:
    def __init__(self):
        self.one = None
        self.results = []
        self.rowcount = 1
        self.executed = []
        self.current_user_record = None
        self.last_query = ""
        self.last_params = None

    def execute(self, query, params=None):
        self.executed.append((query, params))
        self.last_query = query
        self.last_params = params

    def fetchone(self):
        if "FROM users WHERE id=%s" in self.last_query:
            return self.current_user_record
        return self.one

    def fetchall(self):
        return self.results

    def close(self):
        pass


class DummyConnection:
    def __init__(self, cursor=None):
        self._cursor = cursor or DummyCursor()
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


@pytest.fixture
def app():
    test_config = {
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SESSION_COOKIE_SECURE": False,
        "SOCKETIO_ASYNC_MODE": "threading",
        "RATELIMIT_ENABLED": False,
        "SECRET_KEY": "test-secret-key",
    }
    flask_app = app_module.create_app(test_config=test_config)
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def socketio(app):
    return app_module.socketio


@pytest.fixture
def socketio_client(app, client, dummy_cursor):
    dummy_cursor.current_user_record = {
        "id": 2,
        "username": "normaluser",
        "role": "user",
        "is_banned": False,
        "is_deleted": False,
    }
    with client.session_transaction() as sess:
        sess["user_id"] = 2
        sess["username"] = "normaluser"
        sess["role"] = "user"
    test_client = app_module.socketio.test_client(app, flask_test_client=client)
    yield test_client
    if test_client.is_connected():
        test_client.disconnect()


@pytest.fixture
def dummy_cursor():
    return DummyCursor()


@pytest.fixture
def dummy_connection(dummy_cursor):
    return DummyConnection(dummy_cursor)


@pytest.fixture(autouse=True)
def mock_db(monkeypatch, dummy_connection):
    monkeypatch.setattr(data_module, "get_connection", lambda: dummy_connection)
    return dummy_connection


@pytest.fixture
def auth_session(client, dummy_cursor):
    dummy_cursor.current_user_record = {
        "id": 2,
        "username": "normaluser",
        "role": "user",
        "is_banned": False,
        "is_deleted": False,
    }
    with client.session_transaction() as sess:
        sess["user_id"] = 2
        sess["username"] = "normaluser"
        sess["role"] = "user"


@pytest.fixture
def admin_session(client, dummy_cursor):
    dummy_cursor.current_user_record = {
        "id": 1,
        "username": "adminuser",
        "role": "admin",
        "is_banned": False,
        "is_deleted": False,
    }
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = "adminuser"
        sess["role"] = "admin"


@pytest.fixture
def sample_user_record():
    return {
        "id": 2,
        "username": "normaluser",
        "email": "normal@example.com",
        "password_hash": app_module.generate_password_hash("Password123"),
        "role": "user",
        "is_banned": False,
        "is_deleted": False,
    }


@pytest.fixture
def sample_admin_record():
    return {
        "id": 1,
        "username": "adminuser",
        "email": "admin@example.com",
        "password_hash": app_module.generate_password_hash("AdminPass123"),
        "role": "admin",
        "is_banned": False,
        "is_deleted": False,
    }


@pytest.fixture
def sample_logs():
    return [
        {
            "event_type": "LOGIN_SUCCESS",
            "username": "adminuser",
            "ip_address": "127.0.0.1",
            "status": "success",
            "created_at": "2026-04-13 10:00:00",
        },
        {
            "event_type": "MESSAGE_SENT",
            "username": "normaluser",
            "ip_address": "127.0.0.1",
            "status": "success",
            "created_at": "2026-04-13 10:01:00",
        },
    ]


@pytest.fixture
def sample_users():
    return [
        {
            "username": "adminuser",
            "email": "admin@example.com",
            "role": "admin",
            "is_banned": False,
            "created_at": "2026-04-13 09:00:00",
            "last_login_at": "2026-04-13 10:00:00",
        },
        {
            "username": "normaluser",
            "email": "normal@example.com",
            "role": "user",
            "is_banned": False,
            "created_at": "2026-04-13 09:05:00",
            "last_login_at": "2026-04-13 10:05:00",
        },
    ]
