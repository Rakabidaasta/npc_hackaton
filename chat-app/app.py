from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from models import User
import json
from bson.objectid import ObjectId
import os
from flask_swagger_ui import get_swaggerui_blueprint
from dotenv import load_dotenv
from flask_socketio import SocketIO, emit

# После создания Flask-приложения
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24).hex()
socketio = SocketIO(app, cors_allowed_origins="*")  # или конкретные домены

SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.json'

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "Chat for everyone"
    }
)

app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

client = MongoClient(os.getenv('MONGO_URI'))
db = client.chat_db

login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    user_data = db.users.find_one({'_id': ObjectId(user_id)})
    return User(user_data) if user_data else None


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/healthcheck')
def healthcheck():
    return json.dumps({'status': "ok", "message": "server is running"}), 200, {'ContentType':'application/json'} 


@app.route('/auth/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')
        
        existing_user = db.users.find_one({'email': email})
        if existing_user:
            flash('Пользователь с таким email уже существует.')
            return redirect(url_for('signup'))
        
        hashed_password = generate_password_hash(password)
        new_user = {
            'email': email,
            'name': name,
            'password': hashed_password
        }
        db.users.insert_one(new_user)
        
        flash('Вы успешно зарегистрированы')
        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/auth/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user_data = db.users.find_one({'email': email})
        if user_data and check_password_hash(user_data['password'], password):
            user = User(user_data)
            login_user(user)
            return redirect(url_for('profile'))
        
        flash('Неверный email или пароль')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@app.route('/chat')
@login_required
def chat():
    messages = list(db.messages.find().sort('timestamp', -1).limit(50))
    return render_template('chat.html', messages=[
        {
            'user': User(db.users.find_one({'_id': ObjectId(msg['user_id'])})).name,
            'text': msg['text'],
            'time': msg['timestamp'].strftime('%H:%M')
        } for msg in reversed(messages)
    ])

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8000, debug=True)