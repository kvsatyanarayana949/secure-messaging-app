def test_logout_requires_login(client):
    response = client.post("/logout")
    assert response.status_code == 401
    assert response.get_json()["message"] == "Unauthorized"


def test_submit_requires_login(client):
    response = client.post("/submit", data={"new_message": "hello"})
    assert response.status_code == 401
    assert response.get_json()["message"] == "Unauthorized"


def test_messages_requires_login(client):
    response = client.get("/messages")
    assert response.status_code == 401
    assert response.get_json()["message"] == "Unauthorized"


def test_register_requires_all_fields(client):
    response = client.post("/register", data={
        "username": "",
        "email": "",
        "password": ""
    })
    assert response.status_code == 400
    assert "required" in response.get_json()["message"]


def test_register_rejects_invalid_username(client):
    response = client.post("/register", data={
        "username": "!!",
        "email": "test@example.com",
        "password": "Password123"
    })
    assert response.status_code == 400
    assert response.get_json()["message"] == "Invalid username"


def test_register_rejects_short_password(client):
    response = client.post("/register", data={
        "username": "testuser",
        "email": "test@example.com",
        "password": "123"
    })
    assert response.status_code == 400
    assert "at least 8 characters" in response.get_json()["message"]


def test_register_rejects_invalid_email(client):
    response = client.post("/register", data={
        "username": "testuser",
        "email": "invalid-email",
        "password": "Password123"
    })
    assert response.status_code == 400
    assert response.get_json()["message"] == "Invalid email"


def test_register_success(client, mock_db):
    response = client.post("/register", data={
        "username": "newuser",
        "email": "new@example.com",
        "password": "Password123"
    })

    assert response.status_code == 201
    data = response.get_json()
    assert data["status"] == "success"
    assert data["message"] == "Registered successfully"
    assert mock_db.committed is True


def test_login_requires_username_and_password(client):
    response = client.post("/login", data={
        "username": "",
        "password": ""
    })
    assert response.status_code == 400
    assert "required" in response.get_json()["message"]


def test_login_user_not_found(client, mock_db):
    mock_db.cursor().one = None

    response = client.post("/login", data={
        "username": "ghost",
        "password": "Password123"
    })

    assert response.status_code == 401
    assert response.get_json()["message"] == "Invalid username or password"


def test_login_banned_user(client, mock_db, sample_user_record):
    sample_user_record["is_banned"] = True
    mock_db.cursor().one = sample_user_record

    response = client.post("/login", data={
        "username": "normaluser",
        "password": "Password123"
    })

    assert response.status_code == 403
    assert response.get_json()["message"] == "You are banned"
    assert mock_db.committed is True


def test_login_wrong_password(client, mock_db, sample_user_record):
    mock_db.cursor().one = sample_user_record

    response = client.post("/login", data={
        "username": "normaluser",
        "password": "WrongPassword999"
    })

    assert response.status_code == 401
    assert response.get_json()["message"] == "Invalid username or password"
    assert mock_db.committed is True


def test_login_success(client, mock_db, sample_user_record):
    mock_db.cursor().one = sample_user_record

    response = client.post("/login", data={
        "username": "normaluser",
        "password": "Password123"
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["username"] == "normaluser"
    assert data["role"] == "member"
    assert mock_db.committed is True

    with client.session_transaction() as sess:
        assert sess["user_id"] == sample_user_record["id"]
        assert sess["username"] == sample_user_record["username"]
        assert sess["role"] == "member"


def test_submit_rejects_empty_message(client, auth_session):
    response = client.post("/submit", data={"new_message": ""})
    assert response.status_code == 400
    assert response.get_json()["message"] == "Invalid message"


def test_messages_success(client, auth_session, mock_db):
    mock_db.cursor().current_user_record = {
        "id": 2,
        "username": "normaluser",
        "role": "user",
        "is_banned": False,
        "is_deleted": False,
    }
    mock_db.cursor().results = [
        {"username": "normaluser", "message": "hello world", "created_at": "2026-04-13 10:00:00"}
    ]

    response = client.get("/messages")

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["messages"][0]["message"] == "hello world"


def test_submit_rejects_too_long_message(client, auth_session):
    response = client.post("/submit", data={"new_message": "a" * 501})
    assert response.status_code == 400
    assert response.get_json()["message"] == "Invalid message"


def test_submit_success(client, auth_session, mock_db):
    mock_db.cursor().current_user_record = {
        "id": 2,
        "username": "normaluser",
        "role": "user",
        "is_banned": False,
        "is_deleted": False,
    }
    response = client.post("/submit", data={"new_message": "hello world"})

    assert response.status_code == 201
    data = response.get_json()
    assert data["status"] == "success"
    assert data["message"] == "hello world"
    assert mock_db.committed is True


def test_logout_success(client, auth_session):
    response = client.post("/logout")

    assert response.status_code == 200
    assert response.get_json()["status"] == "success"

    with client.session_transaction() as sess:
        assert "user_id" not in sess
        assert "username" not in sess
        assert "role" not in sess


def test_messages_reject_banned_member_session(client, auth_session, mock_db):
    mock_db.cursor().current_user_record = {
        "id": 2,
        "username": "normaluser",
        "role": "user",
        "is_banned": True,
        "is_deleted": False,
    }

    response = client.get("/messages")

    assert response.status_code == 403
    assert response.get_json()["message"] == "You are banned"
    with client.session_transaction() as sess:
        assert "user_id" not in sess
        assert "username" not in sess
        assert "role" not in sess


def test_submit_rejects_banned_member_session(client, auth_session, mock_db):
    mock_db.cursor().current_user_record = {
        "id": 2,
        "username": "normaluser",
        "role": "user",
        "is_banned": True,
        "is_deleted": False,
    }

    response = client.post("/submit", data={"new_message": "still trying"})

    assert response.status_code == 403
    assert response.get_json()["message"] == "You are banned"
    with client.session_transaction() as sess:
        assert "user_id" not in sess
        assert "username" not in sess
        assert "role" not in sess
