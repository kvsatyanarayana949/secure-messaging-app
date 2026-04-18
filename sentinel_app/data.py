from flask import request

from .extensions import mysql


def get_connection():
    return mysql.connection


def get_cursor():
    return get_connection().cursor()


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
            "SELECT username, email, role, is_banned, created_at, last_login_at "
            "FROM users WHERE is_deleted = FALSE ORDER BY created_at DESC"
        )
        return cur.fetchall()
    finally:
        cur.close()


def build_member_stats(users):
    total_members = len(users)
    banned_members = sum(1 for user in users if user["is_banned"])
    admin_count = sum(1 for user in users if user["role"] == "admin")
    active_members = total_members - banned_members
    return {
        "total_members": total_members,
        "active_members": active_members,
        "banned_members": banned_members,
        "admin_count": admin_count,
    }


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

