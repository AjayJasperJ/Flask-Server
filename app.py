from flask import Flask
from flask_socketio import SocketIO
from models import create_all_tables
from routes.auth import auth_bp
from routes.websocket import socket_io, ws_chat_bp

app = Flask(__name__)
app.register_blueprint(auth_bp)
app.register_blueprint(ws_chat_bp)

socket_io.init_app(app, cors_allowed_origins="*",async_mode='eventlet')

@app.route('/')
def root():
    return {'type': 'root', 'name': "ajayjasperj"}

if __name__ == '__main__':
    create_all_tables()
    socket_io.run(app, debug=True,host='127.0.0.1',port=5002)
