import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

# Base directory of the project
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database - SQLite by default (no installation needed)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{os.path.join(BASE_DIR, 'elderly_healthcare.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }
    
    # JWT
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 3600)))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=int(os.environ.get('JWT_REFRESH_TOKEN_EXPIRES', 2592000)))
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'
    
    # Mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', '')
    
    # OpenAI
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

    # Sarvam AI (Bulbul TTS)
    SARVAM_API_KEY = os.environ.get('SARVAM_API_KEY', '')
    SARVAM_TTS_MODEL = os.environ.get('SARVAM_TTS_MODEL', 'bulbul:v3')
    
    # Audio
    AUDIO_DIR = os.environ.get('AUDIO_DIR', 'app/static/audio')
    
    # Scheduler
    SCHEDULER_INTERVAL_MINUTES = int(os.environ.get('SCHEDULER_INTERVAL_MINUTES', 15))
    ALERT_DELAY_MINUTES = int(os.environ.get('ALERT_DELAY_MINUTES', 30))
    
    # CORS
    CORS_ORIGINS = ['http://localhost:5000', 'http://127.0.0.1:5000']


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SQLALCHEMY_ECHO = False
    
    # Stricter JWT in production
    JWT_COOKIE_SECURE = True


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=60)


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
