import os


bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"

worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "eventlet")
workers = int(os.environ.get("GUNICORN_WORKERS", "1"))
worker_connections = int(os.environ.get("GUNICORN_WORKER_CONNECTIONS", "1000"))

timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", "5"))

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
capture_output = True

reload = False

