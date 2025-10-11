from flask import Flask, request, jsonify, redirect, url_for, flash, session, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import uuid
from functools import wraps
import socket
import time
from datetime import timezone
from flask_migrate import Migrate



# Initialize Flask app
app = Flask(__name__)

# Fix database URL for Render
database_url = os.environ.get('DATABASE_URL', 'postgresql://user:password@host:port/database')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# Create upload directories
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'images'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'audios'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'files'), exist_ok=True)

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    verification_code = db.Column(db.String(6))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship('Message', backref='author', lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text)
    message_type = db.Column(db.String(20), default='text')
    file_path = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Utility Functions
def generate_verification_code():
    return ''.join(secrets.choice('0123456789') for _ in range(6))

def send_verification_email(email, code):
    try:
        smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))
        email_user = os.environ.get('EMAIL_USER')
        email_password = os.environ.get('EMAIL_PASSWORD')
        
        # If email credentials aren't set, use console logging
        if not all([email_user, email_password]):
            print(f"Credenciais de email não ajustadas. Código de verificação para {email}: {code}")
            return True
        
        # Set socket timeout to prevent hanging
        socket.setdefaulttimeout(10)
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = email_user
        msg['To'] = email
        msg['Subject'] = 'AlgoNET - Código de Verificação'
        
        # Simple text email (faster than HTML)
        body = f"Seu código de verificação da AlgoNET: {code}\n\nEsse código de verificação irá expirar em 10 minutos."
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email with timeout
        start_time = time.time()
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
        server.starttls()
        server.login(email_user, email_password)
        server.send_message(msg)
        server.quit()
        
        print(f"Verification email sent to {email} in {time.time() - start_time:.2f}s")
        return True
        
    except socket.timeout:
        print(f"Email timeout for {email}. Verification code: {code}")
        return False
    except Exception as e:
        print(f"Email error for {email}: {e}. Verification code: {code}")
        return False

def allowed_file(filename):
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp3', 'wav', 'ogg', 'm4a', 'pdf', 'txt', 'doc', 'docx'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def verification_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_verified:
            flash('Por favor verifique seu email primeiro.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated and current_user.is_verified:
        return redirect(url_for('chat_room'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            flash('Por favor entre seu endereço de email.', 'error')
            return render_template('login.html')
        
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email)
            db.session.add(user)
        
        verification_code = generate_verification_code()
        user.verification_code = verification_code
        user.is_verified = False
        db.session.commit()
        
        # Try to send email, but don't wait too long
        email_sent = send_verification_email(email, verification_code)
        
        if email_sent:
            flash('O código de verificação foi enviado ao seu email!', 'success')
        
        session['verify_email'] = email
        return redirect(url_for('verify'))
    
    return render_template('login.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    email = session.get('verify_email')
    
    if not email:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        code = request.form.get('code')
        user = User.query.filter_by(email=email).first()
        
        if user and user.verification_code == code:
            user.is_verified = True
            user.verification_code = None
            db.session.commit()
            login_user(user, remember=True)
            session.pop('verify_email', None)
            flash('Email verificado com sucesso!', 'success')
            return redirect(url_for('chat_room'))
        else:
            flash('Código de verificação inválido.', 'error')
    
    return render_template('verify.html', email=email)

@app.route('/chat')
@login_required
@verification_required
def chat_room():
    return render_template('chat.html')

@app.route('/api/messages')
@login_required
@verification_required
def get_messages():
    messages = Message.query.order_by(Message.timestamp.asc()).all()
    messages_data = []
    
    for message in messages:
        messages_data.append({
            'id': message.id,
            'user_email': message.author.email,
            'content': message.content,
            'type': message.message_type,
            'file_path': message.file_path,
            'timestamp': message.timestamp.isoformat(),
            'is_own': message.user_id == current_user.id
        })
    
    return jsonify(messages_data)

@app.route('/api/send_message', methods=['POST'])
@login_required
@verification_required
def send_message():
    try:
        content = request.form.get('content', '')
        file = request.files.get('file')
        
        message = Message(
            user_id=current_user.id,
            timestamp=datetime.now(timezone.utc)

        )
        
        if file and file.filename:
            filename = str(uuid.uuid4()) + '_' + file.filename
            file_extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            
            if file_extension in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                upload_folder = 'images'
                message_type = 'image'
            elif file_extension in ['mp3', 'wav', 'ogg', 'm4a']:
                upload_folder = 'audios'
                message_type = 'audio'
            else:
                upload_folder = 'files'
                message_type = 'file'
            
            if allowed_file(file.filename):
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], upload_folder, filename)
                file.save(file_path)
                
                message.message_type = message_type
                message.file_path = f'uploads/{upload_folder}/{filename}'
                message.content = file.filename
            else:
                return jsonify({'error': 'Tipo de arquivo não permitido'}), 400
        else:
            if not content.strip():
                return jsonify({'error': 'Sua mensagem não pode ser vazia'}), 400
            
            message.message_type = 'text'
            message.content = content.strip()
        
        db.session.add(message)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': {
                'id': message.id,
                'user_email': current_user.email,
                'content': message.content,
                'type': message.message_type,
                'file_path': message.file_path,
                'timestamp': message.timestamp.isoformat(),
                'is_own': True
            }
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users')
@login_required
@verification_required
def get_online_users():
    users = User.query.filter_by(is_verified=True).all()
    return jsonify([user.email for user in users])

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('login'))

@app.route('/health')
def health_check():
    return 'OK'

@app.route('/debug')
def debug():
    user_count = User.query.count()
    message_count = Message.query.count()
    return f"Users: {user_count}, Messages: {message_count}, Database URL: {app.config['SQLALCHEMY_DATABASE_URI'][:50]}..."

# Initialize database - safe table creation
with app.app_context():
    try:
        # This will create tables only if they don't exist
        db.create_all()
        
        # Test database connection and tables
        test_user = User.query.first()
        print(f"Database connected successfully. Found {User.query.count()} users and {Message.query.count()} messages.")
        
    except Exception as e:
        print(f"Database initialization note: {e}")
        # This is normal on first deploy or if there are connection issues


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
    return 'OK'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
