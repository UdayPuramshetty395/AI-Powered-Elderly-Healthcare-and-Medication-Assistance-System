"""
Settings API
POST /api/settings/email  — save Gmail credentials + send test email
GET  /api/settings/status — check current notification config status
POST /api/voice/generate  — generate gTTS MP3 for Telugu/English voice
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User

settings_bp = Blueprint('settings', __name__)


# ── Email Settings ────────────────────────────────────────────────────────────

@settings_bp.route('/email', methods=['POST'])
@jwt_required()
def save_email():
    """Save Gmail credentials and send a test email using raw SMTP (bypasses Flask-Mail init issues)."""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'error': 'Email and password required'}), 400

    recipient_email = user.email or username

    # Test with raw SMTP first (most reliable way to validate credentials)
    test_result = _send_smtp_email(
        smtp_user=username,
        smtp_pass=password,
        to_email=recipient_email,
        subject='✅ ElderCare — Email Notifications Active',
        body=(
            f'Hello {user.full_name or user.username},\n\n'
            'Email notifications are now configured and working!\n\n'
            'You will receive:\n'
            '  ✅ Confirmation email every time a dose is taken\n'
            '  ⚠️  Alert email when a dose is missed\n'
            '  🚨 Urgent email for repeated missed doses\n'
            '  📊 Daily summary email at 9 PM\n\n'
            '--- AI-Powered Elderly Healthcare System'
        )
    )

    if not test_result['success']:
        error_msg = test_result.get('error', 'Unknown error')
        
        # Provide specific guidance for common issues
        if 'timeout' in error_msg.lower() or 'port' in error_msg.lower():
            friendly_error = (
                "⚠️ Network is blocking port 587 (SMTP). Possible causes:\n"
                "  • You are on a corporate/school network with firewall restrictions\n"
                "  • Your ISP is blocking port 587\n"
                "\n✅ Solutions:\n"
                "  1. Try from a different network (mobile hotspot, home WiFi)\n"
                "  2. Set up Gmail API for corporate networks (works on port 443)\n"
                "  3. Check with your IT department if you're on corporate WiFi\n"
                "\n💡 For now, emails will be logged and visible in the app (demo mode)"
            )
        elif 'authentication' in error_msg.lower() or 'auth' in error_msg.lower():
            friendly_error = (
                "❌ Authentication failed. Check your credentials:\n"
                "  • Make sure you're using an Email App Password, NOT your account password\n"
                "  • Go to: https://myaccount.google.com/apppasswords\n"
                "  • Select 'Mail' and 'Windows Computer'\n"
                "  • Generate a new 16-character password\n"
                "  • Remove any spaces and paste the full password here"
            )
        elif 'invalid_grant' in error_msg.lower() or 'bad request' in error_msg.lower() or 'oauth' in error_msg.lower():
            friendly_error = (
                "⚠️ Your Gmail OAuth token is invalid or expired.\n"
                "  • Delete the stale gmail_token.json file in the project root\n"
                "  • Run: python setup_gmail.py\n"
                "  • Sign in with your Gmail account again to re-authorize access\n"
                "\nIf you want to use SMTP instead, generate a fresh Gmail App Password and save it in Settings."
            )
        else:
            friendly_error = f"⚠️ {error_msg}\n\nTry using a Gmail App Password from: https://myaccount.google.com/apppasswords"
        
        return jsonify({
            'error': friendly_error,
            'technical_error': error_msg,
            'suggestion': 'Try demo mode or use a different network'
        }), 400

    # Save credentials to runtime config
    current_app.config['MAIL_USERNAME']       = username
    current_app.config['MAIL_PASSWORD']       = password
    current_app.config['MAIL_DEFAULT_SENDER'] = username
    current_app.config['MAIL_SERVER']         = 'smtp.gmail.com'
    current_app.config['MAIL_PORT']           = 587
    current_app.config['MAIL_USE_TLS']        = True
    current_app.config['MAIL_USE_SMTP']       = True

    # Also re-init Flask-Mail so other services can use it
    try:
        from app import mail
        mail.init_app(current_app)
    except Exception:
        pass

    # Persist to .env
    _update_env('MAIL_USERNAME', username)
    _update_env('MAIL_PASSWORD', password)
    _update_env('MAIL_DEFAULT_SENDER', username)

    return jsonify({
        'message': f'✅ Test email sent to {recipient_email}. Email notifications are active!',
        'email': recipient_email
    }), 200


def _send_smtp_email(smtp_user: str, smtp_pass: str,
                      to_email: str, subject: str, body: str) -> dict:
    """Send email using raw Python smtplib — works independently of Flask-Mail state."""
    try:
        msg = MIMEMultipart()
        msg['From']    = smtp_user
        msg['To']      = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to_email, msg.as_string())

        return {'success': True}
    
    except smtplib.SMTPAuthenticationError as e:
        return {'success': False, 'error': 'Authentication failed. Use Gmail App Password (not account password). Get one at: https://myaccount.google.com/apppasswords'}
    
    except TimeoutError as e:
        return {'success': False, 'error': 'Connection timeout on port 587. Network may be blocking SMTP.'}
    
    except smtplib.SMTPException as e:
        return {'success': False, 'error': f'SMTP error: {str(e)}'}
    
    except OSError as e:
        if 'connection' in str(e).lower() or 'refused' in str(e).lower():
            return {'success': False, 'error': 'Connection refused on port 587. Port may be blocked by firewall.'}
        return {'success': False, 'error': f'Network error: {str(e)}'}
    
    except Exception as e:
        return {'success': False, 'error': f'{type(e).__name__}: {str(e)}'}


def send_email_smtp(to_email: str, subject: str, body: str) -> bool:
    """
    Utility used by email_service.py — sends via raw SMTP using saved credentials.
    Falls back to Flask-Mail if SMTP creds not available.
    """
    smtp_user = current_app.config.get('MAIL_USERNAME', '')
    smtp_pass = current_app.config.get('MAIL_PASSWORD', '')
    if not smtp_user or not smtp_pass:
        return False
    result = _send_smtp_email(smtp_user, smtp_pass, to_email, subject, body)
    return result['success']


@settings_bp.route('/email-demo-mode', methods=['POST'])
@jwt_required()
def enable_email_demo_mode():
    """
    Save email credentials WITHOUT testing (for blocked networks).
    Emails will be logged and visible in the app (demo mode).
    User can switch to different network or Gmail API later to actually send emails.
    """
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'error': 'Email and password required'}), 400

    # Save credentials to runtime config WITHOUT testing
    current_app.config['MAIL_USERNAME']       = username
    current_app.config['MAIL_PASSWORD']       = password
    current_app.config['MAIL_DEFAULT_SENDER'] = username
    current_app.config['MAIL_SERVER']         = 'smtp.gmail.com'
    current_app.config['MAIL_PORT']           = 587
    current_app.config['MAIL_USE_TLS']        = True

    # Persist to .env
    _update_env('MAIL_USERNAME', username)
    _update_env('MAIL_PASSWORD', password)
    _update_env('MAIL_DEFAULT_SENDER', username)

    return jsonify({
        'message': (
            f'✅ Email configured in DEMO MODE\n\n'
            f'Email: {username}\n\n'
            f'Your network is blocking port 587 (SMTP). In this mode:\n'
            f'  • Emails will be logged and visible in "Email Log"\n'
            f'  • When you switch to a different network (mobile hotspot, home WiFi),\n'
            f'    emails will start sending automatically\n'
            f'  • All functionality continues to work\n\n'
            f'💡 Alternatives:\n'
            f'  1. Setup Gmail API (works on corporate networks)\n'
            f'  2. Try from a different network\n'
            f'  3. Ask IT to unblock port 587'
        ),
        'email': username,
        'mode': 'demo',
        'warning': 'Emails will be logged but not sent until SMTP connection is available'
    }), 200


@settings_bp.route('/email-log', methods=['GET'])
@jwt_required()
def get_email_log():
    """Return logged emails (for demo when SMTP is blocked by network)."""
    from app.services.email_service import get_email_log
    return jsonify({'emails': get_email_log()}), 200


@settings_bp.route('/status', methods=['GET'])
@jwt_required()
def get_status():
    mail_configured = bool(
        current_app.config.get('MAIL_USERNAME') and
        current_app.config.get('MAIL_PASSWORD')
    )
    
    # Check if Gmail API is configured
    gmail_api_token_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'gmail_token.json'
    )
    gmail_api_configured = os.path.exists(gmail_api_token_path)
    
    return jsonify({
        'email_configured':  mail_configured,
        'email_address':     current_app.config.get('MAIL_USERNAME', ''),
        'gmail_api_configured': gmail_api_configured,
        'push_configured':   bool(os.environ.get('VAPID_PUBLIC_KEY')),
        'websocket_enabled': True,
        'voice_engine':      'gTTS (Telugu + English)',
        'scheduler_running': _scheduler_running(),
    }), 200


@settings_bp.route('/email-diagnostic', methods=['GET'])
@jwt_required()
def email_diagnostic():
    """Run diagnostic tests on email configuration and return results."""
    from app.services.email_service import test_email_config
    
    try:
        results = test_email_config()
        return jsonify({
            'status': 'ok',
            'diagnostic_results': results,
            'message': 'Email configuration diagnosed. Check results for any issues.'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


def _scheduler_running():
    try:
        from app.services.reminder_service import _scheduler
        return _scheduler is not None and _scheduler.running
    except Exception:
        return False


def _update_env(key: str, value: str):
    try:
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            '.env'
        )
        if not os.path.exists(env_path):
            return
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        new_lines, updated = [], False
        for line in lines:
            if line.startswith(f'{key}=') or line.startswith(f'# {key}') and '=' in line:
                new_lines.append(f'{key}={value}\n')
                updated = True
            else:
                new_lines.append(line)
        if not updated:
            new_lines.append(f'{key}={value}\n')
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
    except Exception:
        pass
