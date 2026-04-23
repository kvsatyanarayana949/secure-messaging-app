from datetime import UTC, datetime

from flask import request

from .extensions import mysql


MEMBER_ROLE = "member"
ADMIN_ROLE = "admin"
LEGACY_MEMBER_ROLE = "user"
ACTIVE_STATUS = "active"
BANNED_STATUS = "banned"


def get_connection():
    return mysql.connection


def get_cursor():
    return get_connection().cursor()


def normalize_role(role):
    normalized = (role or MEMBER_ROLE).strip().lower()
    if normalized == LEGACY_MEMBER_ROLE:
        return MEMBER_ROLE
    return normalized or MEMBER_ROLE


def normalize_status(status=None, is_banned=False):
    normalized = (status or "").strip().lower()
    if normalized == BANNED_STATUS or bool(is_banned):
        return BANNED_STATUS
    return ACTIVE_STATUS


def normalize_user_record(record):
    if not record:
        return None

    normalized = dict(record)
    normalized["role"] = normalize_role(normalized.get("role"))
    normalized["status"] = normalize_status(
        status=normalized.get("status"),
        is_banned=normalized.get("is_banned", False),
    )
    normalized["is_banned"] = normalized["status"] == BANNED_STATUS
    normalized["is_online"] = bool(normalized.get("is_online", False))
    return normalized


def fetch_recent_messages(limit=50, search_query=""):
    query = (search_query or "").strip()
    cur = get_cursor()
    try:
        if query:
            cur.execute(
                "SELECT m.message, m.created_at, u.username "
                "FROM messages m JOIN users u ON u.id = m.sender_id "
                "WHERE u.is_deleted = FALSE AND m.message LIKE %s "
                "ORDER BY m.id DESC LIMIT %s",
                (f"%{query}%", limit),
            )
        else:
            cur.execute(
                "SELECT m.message, m.created_at, u.username "
                "FROM messages m JOIN users u ON u.id = m.sender_id "
                "WHERE u.is_deleted = FALSE "
                "ORDER BY m.id DESC LIMIT %s",
                (limit,),
            )
        return cur.fetchall()
    finally:
        cur.close()


def fetch_users():
    cur = get_cursor()
    try:
        cur.execute(
            "SELECT username, email, role, status, is_banned, is_online, last_seen, created_at, last_login_at "
            "FROM users WHERE is_deleted = FALSE ORDER BY is_online DESC, created_at DESC"
        )
        return [normalize_user_record(record) for record in cur.fetchall()]
    finally:
        cur.close()


def build_member_stats(users):
    normalized_users = [normalize_user_record(user) for user in users]
    total_members = len(normalized_users)
    active_users = sum(1 for user in normalized_users if user["is_online"])
    banned_users = sum(1 for user in normalized_users if user["status"] == BANNED_STATUS)
    offline_users = sum(1 for user in normalized_users if not user["is_online"])
    return {
        "active_users": active_users,
        "total_members": total_members,
        "banned_users": banned_users,
        "offline_users": offline_users,
    }


def set_user_presence(user_id, is_online):
    if not user_id:
        return None

    cur = None
    timestamp = None
    try:
        cur = get_cursor()
        if is_online:
            cur.execute(
                "UPDATE users SET is_online = TRUE WHERE id = %s AND is_deleted = FALSE",
                (user_id,),
            )
        else:
            timestamp = datetime.now(UTC).replace(microsecond=0, tzinfo=None)
            cur.execute(
                "UPDATE users SET is_online = FALSE, last_seen = %s WHERE id = %s AND is_deleted = FALSE",
                (timestamp, user_id),
            )
        commit_or_rollback(success=True)
    except Exception:
        commit_or_rollback(success=False)
        raise
    finally:
        if cur:
            cur.close()

    return timestamp


def write_log(cur, event_type, username=None, status="info", user_id=None):
    cur.execute(
        "INSERT INTO logs (event_type, user_id, username, ip_address, status) VALUES (%s,%s,%s,%s,%s)",
        (event_type, user_id, username, request.remote_addr, status),
    )


def commit_or_rollback(success=True):
    if success:
        get_connection().commit()
    else:
        get_connection().rollback()
