def test_users_endpoint_requires_admin_when_logged_out(client):
    response = client.get("/users")
    assert response.status_code == 403
    assert response.get_json()["message"] == "Forbidden"


def test_logs_endpoint_requires_admin_when_logged_out(client):
    response = client.get("/logs")
    assert response.status_code == 403
    assert response.get_json()["message"] == "Forbidden"


def test_ban_user_requires_admin_when_logged_out(client):
    response = client.post("/ban_user", data={"username": "someone"})
    assert response.status_code == 403
    assert response.get_json()["message"] == "Forbidden"


def test_normal_user_cannot_access_users(client, auth_session):
    response = client.get("/users")
    assert response.status_code == 403
    assert response.get_json()["message"] == "Forbidden"


def test_normal_user_cannot_access_logs(client, auth_session):
    response = client.get("/logs")
    assert response.status_code == 403
    assert response.get_json()["message"] == "Forbidden"


def test_admin_cannot_access_messages(client, admin_session):
    response = client.get("/messages")
    assert response.status_code == 403
    assert response.get_json()["message"] == "Admins cannot access messages"


def test_admin_cannot_submit_messages(client, admin_session):
    response = client.post("/submit", data={"new_message": "admin should not send"})
    assert response.status_code == 403
    assert response.get_json()["message"] == "Admins cannot access messages"


def test_normal_user_cannot_ban_user(client, auth_session):
    response = client.post("/ban_user", data={"username": "targetuser"})
    assert response.status_code == 403
    assert response.get_json()["message"] == "Forbidden"


def test_admin_can_get_users(client, admin_session, mock_db, sample_users):
    mock_db.cursor().current_user_record = {
        "id": 1,
        "username": "adminuser",
        "role": "admin",
        "is_banned": False,
        "is_deleted": False,
    }
    mock_db.cursor().results = sample_users

    response = client.get("/users")

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert len(data["users"]) == 2
    assert data["users"][0]["username"] == "adminuser"
    assert data["users"][1]["username"] == "normaluser"
    assert data["users"][0]["created_at"] == "2026-04-13T09:00:00Z"
    assert data["users"][0]["last_login_at"] == "2026-04-13T10:00:00Z"


def test_admin_can_get_logs(client, admin_session, mock_db, sample_logs):
    mock_db.cursor().current_user_record = {
        "id": 1,
        "username": "adminuser",
        "role": "admin",
        "is_banned": False,
        "is_deleted": False,
    }
    mock_db.cursor().results = sample_logs

    response = client.get("/logs")

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert len(data["logs"]) == 2
    assert data["logs"][0]["event_type"] == "LOGIN_SUCCESS"
    assert data["logs"][1]["event_type"] == "MESSAGE_SENT"
    assert data["logs"][0]["created_at"] == "2026-04-13T10:00:00Z"


def test_admin_cannot_ban_self(client, admin_session):
    response = client.post("/ban_user", data={"username": "adminuser"})

    assert response.status_code == 400
    assert response.get_json()["message"] == "Admin cannot ban self"


def test_admin_ban_user_requires_username(client, admin_session):
    response = client.post("/ban_user", data={"username": ""})

    assert response.status_code == 400
    assert response.get_json()["message"] == "Username required"


def test_admin_can_ban_existing_user(client, admin_session, mock_db):
    mock_db.cursor().current_user_record = {
        "id": 1,
        "username": "adminuser",
        "role": "admin",
        "is_banned": False,
        "is_deleted": False,
    }
    mock_db.cursor().one = {"role": "user"}
    mock_db.cursor().rowcount = 1

    response = client.post("/ban_user", data={"username": "targetuser"})

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert mock_db.committed is True


def test_admin_can_unban_existing_user(client, admin_session, mock_db):
    mock_db.cursor().current_user_record = {
        "id": 1,
        "username": "adminuser",
        "role": "admin",
        "is_banned": False,
        "is_deleted": False,
    }
    mock_db.cursor().one = {"role": "user"}
    mock_db.cursor().rowcount = 1

    response = client.post("/unban_user", data={"username": "targetuser"})

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert mock_db.committed is True


def test_admin_ban_user_returns_404_when_user_missing(client, admin_session, mock_db):
    mock_db.cursor().current_user_record = {
        "id": 1,
        "username": "adminuser",
        "role": "admin",
        "is_banned": False,
        "is_deleted": False,
    }
    mock_db.cursor().rowcount = 0

    response = client.post("/ban_user", data={"username": "missinguser"})

    assert response.status_code == 404
    assert response.get_json()["message"] == "User not found"


def test_admin_cannot_ban_another_admin(client, admin_session, mock_db):
    mock_db.cursor().current_user_record = {
        "id": 1,
        "username": "adminuser",
        "role": "admin",
        "is_banned": False,
        "is_deleted": False,
    }
    mock_db.cursor().one = {"role": "admin"}

    response = client.post("/ban_user", data={"username": "anotheradmin"})

    assert response.status_code == 400
    assert response.get_json()["message"] == "Cannot ban another admin"
