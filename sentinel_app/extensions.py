from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mysqldb import MySQL
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect


mysql = MySQL()
csrf = CSRFProtect()
socketio = SocketIO()
limiter = Limiter(key_func=get_remote_address, default_limits=["200/hour", "50/minute"])

