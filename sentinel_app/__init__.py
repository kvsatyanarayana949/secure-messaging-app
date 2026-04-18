import logging
from datetime import timedelta

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import PROJECT_ROOT, apply_config
from .extensions import csrf, limiter, mysql, socketio
from .routes import register_context_processors, register_error_handlers, register_routes
from .socket_events import register_socketio_events


def configure_logging(app):
    logging.basicConfig(level=logging.INFO)
    app.logger.setLevel(logging.INFO)


def create_app(test_config=None):
    app = Flask(__name__, template_folder=str(PROJECT_ROOT / "templates"))
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    apply_config(app, test_config=test_config)

    if not app.config["SECRET_KEY"]:
        raise RuntimeError("SECRET_KEY must be set in environment.")

    app.permanent_session_lifetime = timedelta(minutes=30)

    mysql.init_app(app)
    csrf.init_app(app)
    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode=app.config["SOCKETIO_ASYNC_MODE"],
        manage_session=False,
    )
    limiter.init_app(app)

    configure_logging(app)
    if app.config["REQUESTED_SOCKETIO_ASYNC_MODE"] != app.config["SOCKETIO_ASYNC_MODE"]:
        app.logger.warning(
            "Socket.IO async mode '%s' is not available here, using '%s' instead.",
            app.config["REQUESTED_SOCKETIO_ASYNC_MODE"],
            app.config["SOCKETIO_ASYNC_MODE"],
        )

    register_context_processors(app)
    register_error_handlers(app)
    register_routes(app)
    register_socketio_events()

    return app

