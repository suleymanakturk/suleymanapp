import threading
import paramiko
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# Store active SSH sessions
sessions = {}

@app.route('/')
def index():
    return render_template('index.html')

def handle_ssh_output(sid, channel):
    """Reads output from the SSH channel and emits it to the client."""
    while True:
        if channel.recv_ready():
            data = channel.recv(1024).decode('utf-8', errors='ignore')
            socketio.emit('output', {'data': data}, room=sid)
        
        if channel.exit_status_ready():
            break
        
        socketio.sleep(0.01)

@socketio.on('connect_ssh')
def connect_ssh(data):
    sid = request.sid
    hostname = data.get('hostname')
    port = int(data.get('port', 22))
    username = data.get('username')
    password = data.get('password')

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname, port=port, username=username, password=password)
        
        channel = client.invoke_shell()
        sessions[sid] = {'client': client, 'channel': channel}
        
        # Start a background task to read output
        socketio.start_background_task(target=handle_ssh_output, sid=sid, channel=channel)
        
        emit('status', {'msg': f'Connected to {hostname}'})
        
    except Exception as e:
        emit('status', {'msg': f'Connection failed: {str(e)}'})

@socketio.on('input')
def handle_input(data):
    sid = request.sid
    if sid in sessions:
        channel = sessions[sid]['channel']
        channel.send(data['data'])

@socketio.on('disconnect')
def disconnect():
    sid = request.sid
    if sid in sessions:
        sessions[sid]['client'].close()
        del sessions[sid]
        print(f"Client {sid} disconnected")

if __name__ == '__main__':
    socketio.run('0.0.0.0', debug=True, port=5000)
