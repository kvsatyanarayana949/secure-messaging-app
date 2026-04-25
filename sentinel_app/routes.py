import html
import traceback

from flask import jsonify, redirect, render_template, request, session, url_for
from flask_wtf.csrf import CSRFError, generate_csrf
from werkzeug.security import check_password_hash, generate_password_hash

from .auth import (
    admin_required_json,
    get_active_user_record,
    get_session_value,
    is_admin_session,
    is_member_session,
    login_required_json,
    member_required_json,
)
from .data import (
    ACTIVE_STATUS,
    BANNED_STATUS,
    MEMBER_ROLE,
    build_member_stats,
    commit_or_rollback,
    fetch_recent_messages,
    fetch_users,
    get_cursor,
    normalize_user_record,
    write_log,
)
from .extensions import limiter, socketio
from .socket_events import disconnect_member_sessions


def serialize_records(records):
    serialized = []
    for record in records:
        next_record = {}
        for key, value in record.items():
            if hasattr(value, "isoformat"):
                next_record[key] = value.isoformat(sep=" ", timespec="seconds")
            else:
                next_record[key] = value
        serialized.append(next_record)
    return serialized


def build_restriction_content(user):
    normalized = normalize_user_record(user)
    if not normalized:
        return {
            "eyebrow": "Authentication required",
            "title": "Sign in to continue.",
            "message": "Use an active member account to open the member workspace.",
            "action_label": "",
            "action_href": "",
        }

    if normalized["status"] == BANNED_STATUS:
        return {
            "eyebrow": "Access revoked",
            "title": "This account is blocked.",
            "message": "A banned account cannot enter the member workspace until an administrator restores access.",
            "action_label": "",
            "action_href": "",
        }

    if normalized["role"] == "admin":
        return {
            "eyebrow": "Restricted route",
            "title": "Admins cannot open the member message stream.",
            "message": "This route is reserved for active member accounts. Use the admin console to manage access and monitor presence.",
            "action_label": "Open Admin Dashboard",
            "action_href": "/admin",
        }

    return {
        "eyebrow": "Restricted route",
        "title": "This session cannot enter the workspace.",
        "message": "Sign back in with an active member account to restore access.",
        "action_label": "",
        "action_href": "",
    }


def register_context_processors(app):
    @app.context_processor
    def inject_user():
        user = get_active_user_record()
        return {
            "current_user": user["username"] if user else None,
            "current_role": user["role"] if user else "guest",
            "current_status": user["status"] if user else None,
            "can_view_messages": is_member_session(),
        }


def register_error_handlers(app):
    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        app.logger.warning("CSRF error: %s", error.description)
        return jsonify({
            "status": "error",
            "message": "CSRF validation failed",
            "csrf_refresh_required": True,
        }), 400

    @app.errorhandler(404)
    def handle_404(_error):
        return jsonify({"status": "error", "message": "Not found"}), 404

    @app.errorhandler(Exception)
    def handle_error(_error):
        app.logger.error(traceback.format_exc())
        return jsonify({"status": "error", "message": "Internal Server Error"}), 500


def register_routes(app):
    @app.route("/")
    def home():
        user = get_active_user_record()
        messages = []
        view_state = "auth"
        restricted = build_restriction_content(None)
        if user and user["role"] == MEMBER_ROLE and user["status"] == ACTIVE_STATUS:
            view_state = "chat"
            try:
                messages = fetch_recent_messages()
            except Exception:
                app.logger.error(traceback.format_exc())
        elif user:
            view_state = "restricted"
            restricted = build_restriction_content(user)

        return render_template(
            "index.html",
            messages=serialize_records(messages),
            view_state=view_state,
            restricted_state=restricted,
        )

    @app.route("/admin", methods=["GET"])
    def admin_dashboard():
        if not is_admin_session():
            return redirect(url_for("home"))

        members = []
        stats = {
            "active_users": 0,
            "total_members": 0,
            "banned_users": 0,
            "offline_users": 0,
        }
        try:
            members = serialize_records(fetch_users())
            stats = build_member_stats(members)
        except Exception:
            app.logger.error(traceback.format_exc())

        return render_template("admin.html", members=members, stats=stats)

    @app.route("/csrf-token", methods=["GET"])
    @limiter.exempt
    def csrf_token():
        return jsonify({"status": "success", "csrf_token": generate_csrf()}), 200

    @app.route("/register", methods=["POST"])
    @limiter.limit("5/minute")
    def register():
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not username or not email or not password:
            return jsonify({"status": "error", "message": "Username, email, and password required"}), 400
        if len(username) < 3 or len(username) > 30 or not username.replace("_", "").isalnum():
            return jsonify({"status": "error", "message": "Invalid username"}), 400
        if "@" not in email or "." not in email.split("@")[-1]:
            return jsonify({"status": "error", "message": "Invalid email"}), 400
        if len(password) < 8:
            return jsonify({"status": "error", "message": "Password must be at least 8 characters"}), 400

        cur = None
        try:
            cur = get_cursor()
            hashed = generate_password_hash(password)
            cur.execute(
                "INSERT INTO users (username, email, password_hash, role, status, is_banned, is_deleted) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (username, email, hashed, MEMBER_ROLE, ACTIVE_STATUS, False, False),
            )
            write_log(cur, "REGISTER_SUCCESS", username=username, status="success")
            commit_or_rollback(success=True)
            return jsonify({"status": "success", "message": "Registered successfully"}), 201
        except Exception as error:
            commit_or_rollback(success=False)
            app.logger.error(str(error))
            if "Duplicate entry" in str(error):
                return jsonify({"status": "error", "message": "User already exists"}), 409
            return jsonify({"status": "error", "message": "Registration failed"}), 500
        finally:
            if cur:
                cur.close()

    @app.route("/login", methods=["POST"])
    @limiter.limit("5/minute")
    def login():
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not username or not password:
            return jsonify({"status": "error", "message": "Username and password required"}), 400

        cur = None
        try:
            cur = get_cursor()
            cur.execute(
                "SELECT id, username, email, password_hash, role, status, is_banned, is_deleted "
                "FROM users WHERE username=%s",
                (username,),
            )
            user = normalize_user_record(cur.fetchone())

            if not user or user["is_deleted"]:
                return jsonify({"status": "error", "message": "Invalid username or password"}), 401
            if user["status"] == BANNED_STATUS:
                write_log(cur, "BANNED_LOGIN", username=username, user_id=user["id"], status="blocked")
                commit_or_rollback(success=True)
                return jsonify({"status": "error", "message": "You are banned"}), 403
            if not check_password_hash(user["password_hash"], password):
                write_log(cur, "LOGIN_FAILED", username=username, user_id=user["id"], status="fail")
                commit_or_rollback(success=True)
                return jsonify({"status": "error", "message": "Invalid username or password"}), 401

            csrf_token_value = session.get("csrf_token")
            session.clear()
            if csrf_token_value:
                session["csrf_token"] = csrf_token_value
            session.permanent = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            cur.execute(
                "UPDATE users SET last_login_at=NOW(), last_login_ip=%s WHERE id=%s",
                (request.remote_addr, user["id"]),
            )
            write_log(cur, "LOGIN_SUCCESS", username=username, user_id=user["id"], status="success")
            commit_or_rollback(success=True)

            return jsonify(
                {
                    "status": "success",
                    "username": user["username"],
                    "role": user["role"],
                    "can_view_messages": user["role"] == MEMBER_ROLE,
                    "can_manage_members": user["role"] == "admin",
                    "redirect_to": "/admin" if user["role"] == "admin" else "/",
                }
            ), 200
        except Exception:
            commit_or_rollback(success=False)
            app.logger.error(traceback.format_exc())
            return jsonify({"status": "error", "message": "Login failed"}), 500
        finally:
            if cur:
                cur.close()

    @app.route("/logout", methods=["POST"])
    @login_required_json
    def logout():
        session.clear()
        return jsonify({"status": "success"}), 200

    @app.route("/messages", methods=["GET"])
    @member_required_json
    @limiter.limit("30/minute")
    def get_messages():
        try:
            query = (request.args.get("q") or "").strip()
            return jsonify({
                "status": "success",
                "messages": serialize_records(fetch_recent_messages(search_query=query)),
            }), 200
        except Exception:
            app.logger.error(traceback.format_exc())
            return jsonify({"status": "error", "message": "Messages unavailable"}), 500

    @app.route("/submit", methods=["POST"])
    @limiter.limit("20/minute")
    @member_required_json
    def submit():
        msg = (request.form.get("new_message") or "").strip()
        if not msg or len(msg) > 500:
            return jsonify({"status": "error", "message": "Invalid message"}), 400

        safe_msg = html.escape(msg)
        cur = None
        try:
            cur = get_cursor()
            cur.execute(
                "INSERT INTO messages (message, sender_id) VALUES (%s,%s)",
                (safe_msg, get_session_value("user_id")),
            )
            write_log(
                cur,
                "MESSAGE_SENT",
                username=get_session_value("username"),
                user_id=get_session_value("user_id"),
                status="success",
            )
            commit_or_rollback(success=True)

            socketio.emit(
                "new_message",
                {
                    "username": get_session_value("username"),
                    "message": safe_msg,
                    "created_at": "just now",
                },
                room="members",
            )
            return jsonify({"status": "success", "message": safe_msg}), 201
        except Exception:
            commit_or_rollback(success=False)
            app.logger.error(traceback.format_exc())
            return jsonify({"status": "error", "message": "Message save failed"}), 500
        finally:
            if cur:
                cur.close()

    @app.route("/users", methods=["GET"])
    @admin_required_json
    def get_users():
        try:
            users = serialize_records(fetch_users())
            return jsonify({"status": "success", "users": users}), 200
        except Exception:
            app.logger.error(traceback.format_exc())
            return jsonify({"status": "error", "message": "Users unavailable"}), 500

    @app.route("/logs", methods=["GET"])
    @admin_required_json
    def get_logs():
        cur = None
        try:
            cur = get_cursor()
            cur.execute(
                "SELECT event_type, username, ip_address, status, created_at "
                "FROM logs ORDER BY id DESC LIMIT 100"
            )
            logs = serialize_records(cur.fetchall())
            return jsonify({"status": "success", "logs": logs}), 200
        finally:
            if cur:
                cur.close()

    @app.route("/ban_user", methods=["POST"])
    @admin_required_json
    def ban_user():
        username = (request.form.get("username") or "").strip()
        if not username:
            return jsonify({"status": "error", "message": "Username required"}), 400
        if username == get_session_value("username"):
            return jsonify({"status": "error", "message": "Admin cannot ban self"}), 400

        cur = None
        try:
            cur = get_cursor()
            cur.execute(
                "SELECT id, role FROM users WHERE username=%s AND is_deleted=FALSE",
                (username,),
            )
            user = normalize_user_record(cur.fetchone())
            if not user:
                return jsonify({"status": "error", "message": "User not found"}), 404
            if user["role"] == "admin":
                return jsonify({"status": "error", "message": "Cannot ban another admin"}), 400

            cur.execute(
                "UPDATE users SET status=%s, is_banned=TRUE, is_online=FALSE, last_seen=NOW() "
                "WHERE username=%s AND is_deleted=FALSE",
                (BANNED_STATUS, username),
            )
            cur.execute(
                "SELECT username, email, role, status, is_banned, is_online, last_seen, created_at, last_login_at "
                "FROM users WHERE username=%s AND is_deleted=FALSE",
                (username,),
            )
            updated_user = normalize_user_record(cur.fetchone())
            write_log(cur, "USER_BANNED", username=username, status="success")
            commit_or_rollback(success=True)
            socketio.emit("roster_refresh", {"reason": "user_banned"}, room="admins")
            disconnect_member_sessions(user.get("id"))
            return jsonify({
                "status": "success",
                "user": serialize_records([updated_user])[0] if updated_user else None,
            }), 200
        except Exception:
            commit_or_rollback(success=False)
            app.logger.error(traceback.format_exc())
            return jsonify({"status": "error", "message": "Ban failed"}), 500
        finally:
            if cur:
                cur.close()

    @app.route("/unban_user", methods=["POST"])
    @admin_required_json
    def unban_user():
        username = (request.form.get("username") or "").strip()
        if not username:
            return jsonify({"status": "error", "message": "Username required"}), 400

        cur = None
        try:
            cur = get_cursor()
            cur.execute(
                "SELECT id, username, role, status, is_banned, is_deleted FROM users "
                "WHERE username=%s AND is_deleted=FALSE",
                (username,),
            )
            user = normalize_user_record(cur.fetchone())
            if not user:
                return jsonify({"status": "error", "message": "User not found"}), 404

            cur.execute(
                "UPDATE users SET status=%s, is_banned=FALSE WHERE username=%s AND is_deleted=FALSE",
                (ACTIVE_STATUS, username),
            )
            cur.execute(
                "SELECT username, email, role, status, is_banned, is_online, last_seen, created_at, last_login_at "
                "FROM users WHERE username=%s AND is_deleted=FALSE",
                (username,),
            )
            updated_user = normalize_user_record(cur.fetchone())
            write_log(cur, "USER_UNBANNED", username=username, status="success")
            commit_or_rollback(success=True)
            socketio.emit("roster_refresh", {"reason": "user_unbanned"}, room="admins")
            return jsonify({
                "status": "success",
                "user": serialize_records([updated_user])[0] if updated_user else None,
            }), 200
        except Exception:
            commit_or_rollback(success=False)
            app.logger.error(traceback.format_exc())
            return jsonify({"status": "error", "message": "Unban failed"}), 500
        finally:
            if cur:
                cur.close()

    @app.route("/health", methods=["GET"])
    @limiter.exempt
    def health():
        cur = None
        try:
            cur = get_cursor()
            cur.execute("SELECT 1")
            return jsonify({"status": "ok"}), 200
        except Exception:
            return jsonify({"status": "db-failed"}), 200
        finally:
            if cur:
                cur.close()
