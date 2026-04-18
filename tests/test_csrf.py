import re

import pytest

import app as app_module
import sentinel_app.data as data_module


@pytest.fixture
def csrf_app():
    test_config = {
        "TESTING": True,
        "WTF_CSRF_ENABLED": True,
        "SESSION_COOKIE_SECURE": False,
        "SOCKETIO_ASYNC_MODE": "threading",
        "RATELIMIT_ENABLED": False,
        "SECRET_KEY": "test-secret-key",
    }
    app = app_module.create_app(test_config=test_config)
    yield app


@pytest.fixture
def csrf_client(csrf_app):
    return csrf_app.test_client()


def _get_csrf_token(client, path="/"):
    response = client.get(path)
    html = response.get_data(as_text=True)
    match = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def test_register_without_csrf_token_fails(csrf_client):
    response = csrf_client.post("/register", data={
        "username": "newuser",
        "email": "new@example.com",
        "password": "Password123",
    })

    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
    assert data["message"] == "CSRF validation failed"


def test_login_without_csrf_token_fails(csrf_client):
    response = csrf_client.post("/login", data={
        "username": "normaluser",
        "password": "Password123",
    })

    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
    assert data["message"] == "CSRF validation failed"
    assert data["csrf_refresh_required"] is True


def test_submit_without_csrf_token_fails(csrf_client):
    with csrf_client.session_transaction() as sess:
        sess["user_id"] = 2
        sess["username"] = "normaluser"
        sess["role"] = "user"

    response = csrf_client.post("/submit", data={"new_message": "hello"})

    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
    assert data["message"] == "CSRF validation failed"


def test_register_with_csrf_token_passes_validation_layer(csrf_client, monkeypatch):
    class DummyCursor:
        def __init__(self):
            self.executed = []

        def execute(self, query, params=None):
            self.executed.append((query, params))

        def close(self):
            pass

    class DummyConnection:
        def __init__(self):
            self._cursor = DummyCursor()
            self.committed = False
            self.rolled_back = False

        def cursor(self):
            return self._cursor

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

    dummy_connection = DummyConnection()
    monkeypatch.setattr(data_module, "get_connection", lambda: dummy_connection)

    token = _get_csrf_token(csrf_client)

    response = csrf_client.post(
        "/register",
        data={
            "username": "newuser",
            "email": "new@example.com",
            "password": "Password123",
            "csrf_token": token,
        },
        headers={"X-CSRFToken": token},
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["status"] == "success"
    assert data["message"] == "Registered successfully"


def test_csrf_token_endpoint_returns_fresh_token(csrf_client):
    response = csrf_client.get("/csrf-token")

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["csrf_token"]


def test_login_with_csrf_token_passes_validation_layer(csrf_client, monkeypatch, sample_user_record):
    class DummyCursor:
        def __init__(self):
            self.one = sample_user_record
            self.executed = []

        def execute(self, query, params=None):
            self.executed.append((query, params))

        def fetchone(self):
            return self.one

        def close(self):
            pass

    class DummyConnection:
        def __init__(self):
            self._cursor = DummyCursor()
            self.committed = False
            self.rolled_back = False

        def cursor(self):
            return self._cursor

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

    dummy_connection = DummyConnection()
    monkeypatch.setattr(data_module, "get_connection", lambda: dummy_connection)
    token = _get_csrf_token(csrf_client)

    response = csrf_client.post(
        "/login",
        data={
            "username": "normaluser",
            "password": "Password123",
            "csrf_token": token,
        },
        headers={"X-CSRFToken": token},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "success"
    assert dummy_connection.committed is True
    with csrf_client.session_transaction() as sess:
        assert sess["username"] == "normaluser"
        assert "csrf_token" in sess


def test_csrf_error_handler_returns_json(csrf_client):
    response = csrf_client.post("/register", data={
        "username": "newuser",
        "email": "new@example.com",
        "password": "Password123",
    })

    assert response.is_json is True
    assert response.get_json()["message"] == "CSRF validation failed"

