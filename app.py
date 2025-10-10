from flask import Flask, request, jsonify, redirect, url_for, flash, session
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

# Initialize Flask app
app = Flask(__name__)

# Fix database URL for Render
database_url = os.environ.get('DATABASE_URL', 'sqlite:///chat.db')
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
            print(f"Email credentials not set. Verification code for {email}: {code}")
            return True
        
        # Set socket timeout to prevent hanging
        socket.setdefaulttimeout(10)
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = email_user
        msg['To'] = email
        msg['Subject'] = 'Chat App - Verification Code'
        
        # Simple text email (faster than HTML)
        body = f"Your Chat App verification code is: {code}\n\nThis code will expire in 10 minutes."
        
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
            flash('Please verify your email first.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_flash_messages():
    messages_html = ""
    categories = {
        'error': 'danger',
        'success': 'success', 
        'warning': 'warning',
        'info': 'info'
    }
    
    # Get flashed messages from session
    if '_flashes' in session:
        flashes = session['_flashes'].copy()
        for category, message in flashes:
            alert_class = categories.get(category, 'info')
            messages_html += f'''
            <div class="alert alert-{alert_class} alert-dismissible fade show">
                {message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
            '''
        # Clear the flashes after displaying
        session['_flashes'] = []
    
    return messages_html

# HTML Templates with escaped CSS braces
login_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chat App - Login</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
        }}
        .card {{
            border: none;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}
        .card-body {{
            padding: 2rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-md-6 col-lg-4">
                <div class="card">
                    <div class="card-body">
                        <h2 class="card-title text-center mb-4">Welcome to Chat App</h2>
                        {flash_messages}
                        <form method="POST">
                            <div class="mb-3">
                                <label for="email" class="form-label">Email Address</label>
                                <input type="email" class="form-control" id="email" name="email" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Send Verification Code</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

verify_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chat App - Verify</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
        }}
        .card {{
            border: none;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}
        .card-body {{
            padding: 2rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-md-6 col-lg-4">
                <div class="card">
                    <div class="card-body">
                        <h2 class="card-title text-center mb-4">Verify Your Email</h2>
                        <p class="text-center">We sent a verification code to <strong>{email}</strong></p>
                        {flash_messages}
                        <form method="POST">
                            <div class="mb-3">
                                <label for="code" class="form-label">Verification Code</label>
                                <input type="text" class="form-control" id="code" name="code" maxlength="6" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Verify</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

chat_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chat Room</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="/static/css/style.css" rel="stylesheet">
</head>
<body>
    <div class="container-fluid vh-100">
        {flash_messages}
        
        <div class="row h-100">
            <div class="col-md-3 border-end bg-light">
                <div class="d-flex flex-column h-100">
                    <div class="p-3 border-bottom">
                        <h5 class="mb-0">Online Users</h5>
                    </div>
                    <div class="flex-grow-1 p-3">
                        <div id="users-list">
                            <!-- Users will be populated by JavaScript -->
                        </div>
                    </div>
                    <div class="p-3 border-top">
                        <a href="/logout" class="btn btn-outline-danger w-100">Logout</a>
                    </div>
                </div>
            </div>
            
            <div class="col-md-9 d-flex flex-column">
                <div class="p-3 border-bottom">
                    <h4 class="mb-0">Chat Room</h4>
                </div>
                
                <div id="chat-messages" class="flex-grow-1 p-3">
                    <!-- Messages will be populated by JavaScript -->
                </div>
                
                <div class="p-3 border-top">
                    <form id="message-form" enctype="multipart/form-data">
                        <div class="input-group">
                            <input type="text" id="message-input" class="form-control" placeholder="Type your message..." maxlength="1000">
                            <input type="file" id="file-input" class="form-control" style="display: none;" accept="image/*,audio/*,.pdf,.txt,.doc,.docx">
                            <button type="button" id="file-btn" class="btn btn-outline-secondary">📎</button>
                            <button type="submit" class="btn btn-primary">Send</button>
                        </div>
                        <div id="file-info" class="mt-2" style="display: none;"></div>
                    </form>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="/static/js/chat.js"></script>
</body>
</html>
'''

# Routes
@app.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated and current_user.is_verified:
        return redirect(url_for('chat_room'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            flash('Please enter your email address.', 'error')
            return login_html.format(flash_messages=get_flash_messages())
        
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
            flash('Verification code sent to your email!', 'success')
        else:
            flash(f'Email may not have been sent. Your code is: {verification_code}', 'warning')
            print(f"DEBUG - Verification code for {email}: {verification_code}")
        
        session['verify_email'] = email
        return redirect(url_for('verify'))
    
    return login_html.format(flash_messages=get_flash_messages())

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
            flash('Email verified successfully!', 'success')
            return redirect(url_for('chat_room'))
        else:
            flash('Invalid verification code.', 'error')
    
    return verify_html.format(email=email, flash_messages=get_flash_messages())

@app.route('/chat')
@login_required
@verification_required
def chat_room():
    return chat_html.format(flash_messages=get_flash_messages())

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
            timestamp=datetime.utcnow()
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
                return jsonify({'error': 'File type not allowed'}), 400
        else:
            if not content.strip():
                return jsonify({'error': 'Message cannot be empty'}), 400
            
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
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/health')
def health_check():
    return 'OK'

# Initialize database
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
