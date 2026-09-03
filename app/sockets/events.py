"""
WebSocket event handlers (Flask-SocketIO)
Real-time push to connected browsers — no page refresh needed.
"""
import logging
from app import socketio

logger = logging.getLogger(__name__)


@socketio.on('connect')
def on_connect():
    logger.debug('Client connected')


@socketio.on('disconnect')
def on_disconnect():
    logger.debug('Client disconnected')


@socketio.on('join_room')
def on_join_room(data):
    from flask_socketio import join_room
    room = data.get('room')
    if room:
        join_room(room)
        logger.debug(f'Joined room: {room}')


@socketio.on('leave_room')
def on_leave_room(data):
    from flask_socketio import leave_room
    room = data.get('room')
    if room:
        leave_room(room)


# ── Emitter helpers ───────────────────────────────────────────────────────────

def emit_reminder(elder_id: int, schedule_id: int, medicine_id: int,
                   medicine_name: str, dosage: str, scheduled_time: str,
                   level: int, texts: dict,
                   voice_mod: dict = None, reminder_num: int = 1,
                   max_reminders: int = 6, lang: str = 'te'):
    """
    Push medicine reminder to elder's browser room.
    Includes preloaded MP3 URL for instant Telugu playback.
    
    Args:
        elder_id: Elder ID
        schedule_id: Medicine schedule ID
        medicine_id: Medicine ID
        medicine_name: Medicine name
        dosage: Medicine dosage
        scheduled_time: Scheduled time string
        level: Reminder level (1-3)
        texts: Dict with 'te' and 'en' keys containing reminder text
        voice_mod: Voice modulation settings (rate, pitch, volume)
        reminder_num: Current reminder number (1-6)
        max_reminders: Max reminders before auto-mark (typically 6)
        lang: Language code ('te', 'en', etc.) - for browser preference
    """
    # Get preloaded MP3 URL for this reminder
    try:
        from app.services.voice_preloader import get_preloaded_url
        from app.services.adaptive_reminder_engine import get_time_of_day, REMINDER_INTERVAL_MINUTES
        from datetime import datetime
        tod = get_time_of_day(datetime.now().hour)
        audio_url_te = get_preloaded_url(tod, min(reminder_num, 6))
    except Exception:
        audio_url_te = ''

    socketio.emit('medicine_reminder', {
        'elder_id':       elder_id,
        'schedule_id':    schedule_id,
        'medicine_id':    medicine_id,
        'medicine_name':  medicine_name,
        'dosage':         dosage,
        'scheduled_time': scheduled_time,
        'level':          level,
        'text_en':        texts.get('en', '') if texts else '',
        'text_te':        texts.get('te', '') if texts else '',
        'lang':           lang,  # ✅ Include language preference
        'audio_url_te':   audio_url_te,   # Pre-generated MP3 — plays immediately
        'voice_mod':      voice_mod or {'rate': 0.75, 'pitch': 1.0, 'volume': 0.9},
        'reminder_num':   reminder_num,
        'max_reminders':  max_reminders,
        'snooze_disabled': reminder_num >= max_reminders,
        'fullscreen':     level >= 3 or reminder_num >= 5,
        'repeat_interval_minutes': REMINDER_INTERVAL_MINUTES,
    }, room=f'elder_{elder_id}')
    logger.info(f'✅ Emitted reminder R{reminder_num}/{max_reminders} '
                 f'to elder_{elder_id} — {medicine_name} '
                 f'(lang={lang}, audio={bool(audio_url_te)}, text={len(texts.get("te", "")) if texts else 0} chars)')


def emit_adherence_update(caretaker_id: int, elder_id: int,
                           elder_name: str, medicine_name: str, status: str):
    socketio.emit('adherence_update', {
        'elder_id':      elder_id,
        'elder_name':    elder_name,
        'medicine_name': medicine_name,
        'status':        status,
    }, room=f'caretaker_{caretaker_id}')


def emit_alert(caretaker_id: int, alert_data: dict):
    socketio.emit('alert_update', alert_data,
                  room=f'caretaker_{caretaker_id}')


def emit_dashboard_refresh(caretaker_id: int):
    socketio.emit('dashboard_refresh', {},
                  room=f'caretaker_{caretaker_id}')
