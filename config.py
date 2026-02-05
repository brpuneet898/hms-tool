"""
Configuration for MediFriend Healthcare Platform
"""
import os
import yaml


# Load API keys
def load_keys():
    keys_path = os.path.join(os.path.dirname(__file__), 'keys.yaml')
    with open(keys_path, 'r') as f:
        return yaml.safe_load(f)


class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'mysupersecretkey-change-in-production'
    
    # Database
    DB_PATH = os.path.join(os.path.dirname(__file__), 'hms.db')
    
    # Upload folder
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
    
    # Gemini API
    keys = load_keys()
    GEMINI_API_KEY = keys.get('GEMINI_API_KEY')
    
    # Session configuration
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    
    # Email configuration (Gmail SMTP)
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = keys.get('MAIL_USERNAME')  # Add to keys.yaml
    MAIL_PASSWORD = keys.get('MAIL_PASSWORD')  # Add to keys.yaml (App Password for Gmail)
    MAIL_DEFAULT_SENDER = keys.get('MAIL_USERNAME')


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS
