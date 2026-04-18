def test_member_login_chat_logout_flow(client, mock_db, sample_user_record):
    mock_db.cursor().one = sample_user_record

    login_response = client.post("/login", data={
        "username": "normaluser",
        "password": "Password123",
    })
    assert login_response.status_code == 200
    assert login_response.get_json()["can_view_messages"] is True

    mock_db.cursor().results = []
    messages_response = client.get("/messages")
    assert messages_response.status_code == 200
    assert messages_response.get_json()["status"] == "success"

    submit_response = client.post("/submit", data={"new_message": "production smoke test"})
    assert submit_response.status_code == 201
    assert submit_response.get_json()["message"] == "production smoke test"

    logout_response = client.post("/logout")
    assert logout_response.status_code == 200
    assert logout_response.get_json()["status"] == "success"


def test_admin_dashboard_moderation_logout_flow(client, admin_session, mock_db, sample_users):
    mock_db.cursor().results = sample_users

    dashboard_response = client.get("/admin")
    assert dashboard_response.status_code == 200
    assert b"admin-app" in dashboard_response.data

    users_response = client.get("/users")
    assert users_response.status_code == 200
    assert users_response.get_json()["users"][1]["username"] == "normaluser"

    mock_db.cursor().one = {"role": "user"}
    ban_response = client.post("/ban_user", data={"username": "normaluser"})
    assert ban_response.status_code == 200

    unban_response = client.post("/unban_user", data={"username": "normaluser"})
    assert unban_response.status_code == 200

    logout_response = client.post("/logout")
    assert logout_response.status_code == 200

