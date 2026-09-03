"""
AI-Powered Elderly Healthcare and Medication Assistance System
Entry point — uses Flask-SocketIO for WebSocket support.
"""
import os
from app import create_app, socketio

app = create_app(os.environ.get('FLASK_ENV', 'development'))

if __name__ == '__main__':
    print("=" * 60)
    print("  AI-Powered Elderly Healthcare System")
    print("=" * 60)
    print(f"  URL:         http://localhost:5000")
    print(f"  Elder View:  http://localhost:5000/elder-view")
    print(f"  Dashboard:   http://localhost:5000/dashboard")
    print(f"  Environment: {os.environ.get('FLASK_ENV', 'development')}")
    print("=" * 60)
    print("  WebSockets: enabled")
    print("  Push Notifications: enabled (Web Push + VAPID)")
    print("  PWA: enabled (install via browser)")
    print("=" * 60)

    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=os.environ.get('FLASK_ENV', 'development') == 'development',
        use_reloader=False,   # APScheduler conflicts with reloader
        log_output=False
    )
