import os

from werkzeug.security import check_password_hash, generate_password_hash

from sentinel_app import create_app
from sentinel_app.auth import (
    admin_required_json,
    get_session_value,
    is_admin_session,
    is_authenticated,
    is_member_session,
    login_required_json,
    member_required_json,
)
from sentinel_app.data import (
    build_member_stats,
    commit_or_rollback,
    fetch_recent_messages,
    fetch_users,
    get_connection,
    get_cursor,
    write_log,
)
from sentinel_app.extensions import csrf, limiter, mysql, socketio


app = create_app()
app.extensions["socketio"] = socketio


if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=(app.config["ENV"] == "development"),
    )

