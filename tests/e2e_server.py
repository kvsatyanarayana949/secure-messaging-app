import os
import sys
from copy import deepcopy
from pathlib import Path

from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "e2e-secret-key")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")
os.environ.setdefault("SOCKETIO_ASYNC_MODE", "threading")
os.environ.setdefault("RATELIMIT_ENABLED", "false")

import sentinel_app.routes as routes_module
import sentinel_app.auth as auth_module
import sentinel_app.data as data_module
from sentinel_app import create_app
from sentinel_app.extensions import socketio


USERS = [
    {
        "id": 1,
        "username": "admin",
        "email": "admin@sentinel.local",
        "password_hash": generate_password_hash("AdminPass123!"),
        "role": "admin",
        "is_banned": False,
        "is_deleted": False,
        "created_at": "2026-04-18 12:00:00",
        "last_login_at": None,
    },
    {
        "id": 2,
        "username": "normaluser",
        "email": "normal@example.com",
        "password_hash": generate_password_hash("Password123"),
        "role": "user",
        "is_banned": False,
        "is_deleted": False,
        "created_at": "2026-04-18 12:01:00",
        "last_login_at": None,
    },
]
MESSAGES = [
    {
        "username": "normaluser",
        "message": "welcome to the browser audit stream",
        "created_at": "2026-04-18 12:05:00",
    }
]
LOGS = []


def public_user(user):
    return {
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "is_banned": user["is_banned"],
        "created_at": user["created_at"],
        "last_login_at": user["last_login_at"],
    }


class MemoryCursor:
    rowcount = 1

    def __init__(self):
        self.one = None
        self.results = []
        self.last_query = ""
        self.last_params = ()

    def execute(self, query, params=None):
        self.last_query = " ".join(query.lower().split())
        self.last_params = params or ()
        self.rowcount = 1

        if self.last_query.startswith("select id, username, role, is_banned, is_deleted from users where id="):
            user_id = self.last_params[0]
            self.one = next(({
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "is_banned": user["is_banned"],
                "is_deleted": user["is_deleted"],
            } for user in USERS if user["id"] == user_id), None)
            return

        if self.last_query.startswith("select id, username"):
            username = self.last_params[0]
            self.one = next((deepcopy(user) for user in USERS if user["username"] == username), None)
            return

        if self.last_query.startswith("insert into users"):
            username, email, password_hash, role, is_banned, is_deleted = self.last_params
            if any(user["username"] == username or user["email"] == email for user in USERS):
                raise Exception("Duplicate entry")
            USERS.append({
                "id": max(user["id"] for user in USERS) + 1,
                "username": username,
                "email": email,
                "password_hash": password_hash,
                "role": role,
                "is_banned": is_banned,
                "is_deleted": is_deleted,
                "created_at": "2026-04-18 12:10:00",
                "last_login_at": None,
            })
            return

        if self.last_query.startswith("update users set last_login_at"):
            ip_address, user_id = self.last_params
            for user in USERS:
                if user["id"] == user_id:
                    user["last_login_at"] = "2026-04-18 12:15:00"
                    user["last_login_ip"] = ip_address
            return

        if self.last_query.startswith("insert into messages"):
            message, sender_id = self.last_params
            sender = next(user for user in USERS if user["id"] == sender_id)
            MESSAGES.insert(0, {
                "username": sender["username"],
                "message": message,
                "created_at": "just now",
            })
            return

        if self.last_query.startswith("select id, role from users"):
            username = self.last_params[0]
            user = next((user for user in USERS if user["username"] == username and not user["is_deleted"]), None)
            self.one = {"id": user["id"], "role": user["role"]} if user else None
            if not user:
                self.rowcount = 0
            return

        if self.last_query.startswith("select role from users"):
            username = self.last_params[0]
            user = next((user for user in USERS if user["username"] == username and not user["is_deleted"]), None)
            self.one = {"role": user["role"]} if user else None
            if not user:
                self.rowcount = 0
            return

        if self.last_query.startswith("update users set is_banned=true"):
            username = self.last_params[0]
            user = next((user for user in USERS if user["username"] == username and not user["is_deleted"]), None)
            if user:
                user["is_banned"] = True
            else:
                self.rowcount = 0
            return

        if self.last_query.startswith("update users set is_banned=false"):
            username = self.last_params[0]
            user = next((user for user in USERS if user["username"] == username and not user["is_deleted"]), None)
            if user:
                user["is_banned"] = False
            else:
                self.rowcount = 0
            return

        if self.last_query.startswith("insert into logs"):
            event_type, user_id, username, ip_address, status = self.last_params
            LOGS.append({
                "event_type": event_type,
                "user_id": user_id,
                "username": username,
                "ip_address": ip_address,
                "status": status,
                "created_at": "2026-04-18 12:20:00",
            })
            return

        if self.last_query.startswith("select event_type"):
            self.results = deepcopy(LOGS[-100:])
            return

        if self.last_query.startswith("select 1"):
            self.one = {"1": 1}

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.results

    def close(self):
        pass


class MemoryConnection:
    def cursor(self):
        return MemoryCursor()

    def commit(self):
        pass

    def rollback(self):
        pass


def get_connection():
    return MemoryConnection()


def get_cursor():
    return get_connection().cursor()


def fetch_recent_messages(limit=50, search_query=""):
    query = (search_query or "").lower()
    records = [deepcopy(message) for message in MESSAGES if not query or query in message["message"].lower()]
    return records[:limit]


def fetch_users():
    return [public_user(user) for user in USERS if not user["is_deleted"]]


def write_log(cur, event_type, username=None, status="info", user_id=None):
    LOGS.append({
        "event_type": event_type,
        "user_id": user_id,
        "username": username,
        "ip_address": "127.0.0.1",
        "status": status,
        "created_at": "2026-04-18 12:20:00",
    })


def commit_or_rollback(success=True):
    return None


routes_module.get_connection = get_connection
routes_module.get_cursor = get_cursor
routes_module.fetch_recent_messages = fetch_recent_messages
routes_module.fetch_users = fetch_users
routes_module.write_log = write_log
routes_module.commit_or_rollback = commit_or_rollback
auth_module.get_cursor = get_cursor
data_module.get_connection = get_connection
data_module.get_cursor = get_cursor

app = create_app({
    "TESTING": False,
    "WTF_CSRF_ENABLED": True,
    "SESSION_COOKIE_SECURE": False,
    "SOCKETIO_ASYNC_MODE": "threading",
    "RATELIMIT_ENABLED": False,
    "SECRET_KEY": "e2e-secret-key",
})


if __name__ == "__main__":
    socketio.run(app, host="127.0.0.1", port=5100, debug=False, allow_unsafe_werkzeug=True)
