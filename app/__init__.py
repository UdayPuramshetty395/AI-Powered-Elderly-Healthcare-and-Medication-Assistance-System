import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_cors import CORS
from flask_mail import Mail
from flask_socketio import SocketIO

from app.config import config

db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()
mail = Mail()
socketio = SocketIO()


def create_app(config_name=None):
    """Application factory."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    app.config.from_object(config.get(config_name, config['default']))

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": app.config['CORS_ORIGINS']}})

    # SocketIO — threading mode (compatible with Python 3.14)
    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode='threading',
        logger=False,
        engineio_logger=False
    )

    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        from flask import jsonify
        return jsonify({'error': 'Token has expired', 'code': 'token_expired'}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        from flask import jsonify
        return jsonify({'error': 'Invalid token', 'code': 'invalid_token'}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        from flask import jsonify
        return jsonify({'error': 'Authorization token required',
                        'code': 'authorization_required'}), 401

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.elder import elder_bp
    from app.routes.medicine import medicine_bp
    from app.routes.schedule import schedule_bp
    from app.routes.adherence import adherence_bp
    from app.routes.alerts import alerts_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.chatbot import chatbot_bp
    from app.routes.views import views_bp
    from app.routes.health import health_bp
    from app.routes.wellness import wellness_bp
    from app.routes.analytics import analytics_bp
    from app.routes.reminders_api import reminders_api_bp
    from app.routes.push_notifications import push_bp
    from app.routes.settings import settings_bp
    from app.routes.voice_api import voice_api_bp
    from app.routes.reports import reports_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(elder_bp, url_prefix='/api/elders')
    app.register_blueprint(medicine_bp, url_prefix='/api/medicines')
    app.register_blueprint(schedule_bp, url_prefix='/api/schedules')
    app.register_blueprint(adherence_bp, url_prefix='/api/adherence')
    app.register_blueprint(alerts_bp, url_prefix='/api/alerts')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    app.register_blueprint(chatbot_bp, url_prefix='/api/chatbot')
    app.register_blueprint(wellness_bp, url_prefix='/api/wellness')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    app.register_blueprint(reminders_api_bp, url_prefix='/api/reminders')
    app.register_blueprint(push_bp, url_prefix='/api/push')
    app.register_blueprint(settings_bp, url_prefix='/api/settings')
    app.register_blueprint(voice_api_bp, url_prefix='/api/voice')
    app.register_blueprint(reports_bp, url_prefix='/api/reports')
    # Health check endpoint (no prefix)
    app.register_blueprint(health_bp)
    app.register_blueprint(views_bp)
    from app.routes.debug_reminder import debug_bp
    app.register_blueprint(debug_bp, url_prefix='/api/debug')

    # Register SocketIO events
    from app.sockets import events  # noqa

    # Ensure audio directory exists
    audio_dir = app.config.get('AUDIO_DIR', 'app/static/audio')
    os.makedirs(audio_dir, exist_ok=True)

    # Initialize tables + scheduler
    with app.app_context():
        db.create_all()

        # Prevent Flask debug reloader from creating duplicate scheduler jobs.
        # Start scheduler in:
        # - non-debug mode,
        # - Werkzeug reloader child process,
        # - or when the app is not launched through flask run CLI.
        is_reloader_child = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
        is_flask_cli = os.environ.get('FLASK_RUN_FROM_CLI') == 'true'

        if not app.debug or is_reloader_child or not is_flask_cli:
            from app.services.reminder_service import init_scheduler
            init_scheduler(app)
            # Pre-generate Telugu MP3s in background
            from app.services.voice_preloader import preload_all
            preload_all(app)
        else:
            app.logger.info('Skipping scheduler and preloader initialization in Flask reloader parent process')

    return app
