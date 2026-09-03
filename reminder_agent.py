"""
ElderCare Voice Reminder Agent
================================
Runs from Windows Task Scheduler or as a long-lived local agent.

This version reads the local SQLite database directly and speaks
medicine reminders through the PC speakers using pyttsx3.
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime, date, time as dt_time, timedelta
from pathlib import Path

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

logging.basicConfig(
    format='%(asctime)s %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)

MESSAGES = [
    "మీరు మందులు తీసుకునే సమయం అయింది. దయచేసి వెంటనే తీసుకోండి.",
    "మీ మందులు ఇంకా తీసుకోలేదు. ఇది గుర్తుచేసే సందేశం.",
    "మందు సమయం గడిచిపోయింది. ఇది మీ ఆరోగ్యానికి హానికరం కావచ్చు. వెంటనే తీసుకోండి.",
    "ఇది అత్యవసర గుర్తుచేయింపు. వెంటనే మందులు తీసుకోండి.",
    "సీరియస్ రిమైండర్: మీరు మందులు ఇంకా తీసుకోలేదు. ఇప్పుడే తీసుకోండి.",
    "హెచ్చరిక: మీ మందు సమయం చాలా ఎక్కువగా దాటింది. మీ ఆరోగ్యానికి ఇది ప్రమాదకరం." 
]

DEFAULT_REPEAT_MINUTES = 2
DEFAULT_POLL_SECONDS = 60
DEFAULT_DB_URL = os.environ.get(
    'DATABASE_URL',
    f"sqlite:///{Path(__file__).resolve().parent / 'elderly_healthcare.db'}"
)
DEFAULT_STATE_FILE = Path(__file__).resolve().parent / 'reminder_agent_state.json'
VOICE_RATE = 130
VOICE_VOLUME = 1.0
VOICE_STYLES = [
    {'rate': 130, 'volume': 0.95},
    {'rate': 140, 'volume': 1.0},
    {'rate': 150, 'volume': 1.0},
    {'rate': 160, 'volume': 1.0},
    {'rate': 170, 'volume': 1.0},
    {'rate': 180, 'volume': 1.0},
]


def normalize_db_path(db_url: str) -> str:
    if db_url.startswith('sqlite:///'):
        path = db_url[10:]
        if os.name == 'nt' and path.startswith('/') and len(path) > 2 and path[2] == ':':
            path = path[1:]
        return os.path.abspath(os.path.expanduser(path))
    if db_url.startswith('sqlite://'):
        path = db_url[9:]
        return os.path.abspath(os.path.expanduser(path))
    return os.path.abspath(os.path.expanduser(db_url))


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open('r', encoding='utf-8') as handle:
            return json.load(handle)
    except Exception as exc:
        log.warning('Failed to load state file %s: %s', path, exc)
        return {}


def save_state(path: Path, state: dict):
    try:
        with path.open('w', encoding='utf-8') as handle:
            json.dump(state, handle, indent=2)
    except Exception as exc:
        log.warning('Failed to save state file %s: %s', path, exc)


def parse_time(value):
    if value is None:
        return None
    if isinstance(value, dt_time):
        return value
    if isinstance(value, bytes):
        value = value.decode('utf-8', errors='ignore')
    if isinstance(value, str):
        value = value.strip()
        if '.' in value:
            value = value.split('.')[0]
        for fmt in ('%H:%M:%S', '%H:%M'):
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                continue
    return None


def create_engine():
    if pyttsx3 is None:
        log.warning('pyttsx3 is not installed')
        return None
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', VOICE_RATE)
        engine.setProperty('volume', VOICE_VOLUME)
        voices = engine.getProperty('voices') or []
        selected = None
        for voice in voices:
            name = getattr(voice, 'name', '') or ''
            vid = getattr(voice, 'id', '') or ''
            langs = getattr(voice, 'languages', None)
            lang_str = ''
            if langs:
                if isinstance(langs, (list, tuple)):
                    lang_str = ' '.join(str(x) for x in langs)
                else:
                    lang_str = str(langs)
            if any(token in name.lower() for token in ('telugu', 'shruti', 'te-')) or \
               any(token in vid.lower() for token in ('telugu', 'shruti', 'te-')) or \
               'te' in lang_str.lower():
                engine.setProperty('voice', voice.id)
                selected = voice
                break
        if selected is None:
            log.warning('No Telugu pyttsx3 voice found. Available voices:')
            for voice in voices:
                name = getattr(voice, 'name', '') or ''
                vid = getattr(voice, 'id', '') or ''
                langs = getattr(voice, 'languages', None)
                log.warning('  voice=%s id=%s langs=%s', name, vid, langs)
            return None
        log.info('Selected Telugu pyttsx3 voice: %s (%s)', selected.name, selected.id)
        return engine
    except Exception as exc:
        log.warning('pyttsx3 engine init failed: %s', exc)
        return None


def apply_voice_style(engine, count: int):
    if engine is None:
        return None
    style = VOICE_STYLES[min(count, len(VOICE_STYLES) - 1)]
    original = {
        'rate': engine.getProperty('rate'),
        'volume': engine.getProperty('volume')
    }
    try:
        engine.setProperty('rate', style['rate'])
        engine.setProperty('volume', style['volume'])
    except Exception as exc:
        log.warning('Failed to apply voice style: %s', exc)
    return original


def restore_voice_style(engine, original):
    if engine is None or original is None:
        return
    try:
        engine.setProperty('rate', original.get('rate', VOICE_RATE))
        engine.setProperty('volume', original.get('volume', VOICE_VOLUME))
    except Exception as exc:
        log.warning('Failed to restore voice style: %s', exc)


def speak_with_pyttsx3(engine, text: str) -> bool:
    if engine is None:
        return False
    try:
        engine.say(text)
        engine.runAndWait()
        return True
    except Exception as exc:
        log.warning('pyttsx3 playback failed: %s', exc)
        return False


def speak_with_edge_tts(text: str) -> bool:
    tmp = None
    try:
        import asyncio
        import edge_tts
        import tempfile
        import winsound
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            tmp = f.name
        async def _speak():
            await edge_tts.Communicate(text, 'te-IN-ShrutiNeural').save(tmp)
        asyncio.run(_speak())
        log.info('edge_tts audio file created: %s', tmp)
        try:
            winsound.PlaySound(tmp, winsound.SND_FILENAME | winsound.SND_SYNC)
            log.info('edge_tts playback succeeded')
            return True
        except Exception as exc:
            log.error('winsound playback failed: %s', exc)
            return False
    except ModuleNotFoundError:
        log.error('edge_tts is not installed and pyttsx3 is unavailable')
    except Exception as exc:
        log.error('edge_tts playback failed: %s', exc)
    finally:
        try:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass
    return False


def speak(text: str, engine, count: int = 0):
    log.info('Speaking: %s', text[:80])
    used_edge = False
    if engine:
        log.info('Attempting pyttsx3 Telugu playback')
        original = apply_voice_style(engine, count)
        try:
            if speak_with_pyttsx3(engine, text):
                log.info('pyttsx3 playback succeeded')
                log.info('Audio playback completed via pyttsx3')
                return
            else:
                log.info('pyttsx3 playback failed or returned False')
        finally:
            restore_voice_style(engine, original)
    log.info('Using edge_tts fallback playback')
    used_edge = True
    if speak_with_edge_tts(text):
        log.info('Audio playback completed via edge_tts')
    else:
        log.error('Audio playback failed on both pyttsx3 and edge_tts')


def get_adherence_status(conn, schedule_id: int, elder_id: int, today: date):
    cursor = conn.cursor()
    start = datetime.combine(today, dt_time.min)
    end = datetime.combine(today, dt_time.max)
    cursor.execute(
        'SELECT status FROM adherence_records '
        'WHERE schedule_id = ? AND elder_id = ? '
        'AND scheduled_datetime BETWEEN ? AND ? '
        'ORDER BY id DESC LIMIT 1',
        (schedule_id, elder_id, start, end)
    )
    row = cursor.fetchone()
    return row[0] if row else None


def get_due_schedules(conn, now: datetime):
    cursor = conn.cursor()
    cursor.execute(
        'SELECT ms.id AS schedule_id, ms.elder_id, ms.medicine_id, '
        'ms.scheduled_time, ms.recurrence, ms.day_of_week, '
        'e.name AS elder_name, m.name AS medicine_name, m.dosage '
        'FROM medicine_schedules ms '
        'JOIN elders e ON e.id = ms.elder_id '
        'JOIN medicines m ON m.id = ms.medicine_id '
        'WHERE ms.is_active = 1 AND e.is_active = 1 AND m.is_active = 1 '
        'ORDER BY ms.scheduled_time ASC'
    )
    rows = cursor.fetchall()
    today = now.date()
    due = []
    for row in rows:
        scheduled_time = parse_time(row['scheduled_time'])
        if scheduled_time is None:
            continue
        scheduled_dt = datetime.combine(today, scheduled_time)
        if scheduled_dt > now:
            continue

        recurrence = (row['recurrence'] or 'daily').lower()
        day_of_week = (row['day_of_week'] or '').strip().lower()
        if recurrence == 'weekly' and day_of_week:
            weekday = now.strftime('%A').lower()
            if day_of_week not in ('all', weekday):
                continue

        status = get_adherence_status(conn, row['schedule_id'], row['elder_id'], today)
        if status in ('taken', 'taken_late', 'skipped'):
            continue

        due.append({
            'schedule_id': row['schedule_id'],
            'elder_id': row['elder_id'],
            'medicine_id': row['medicine_id'],
            'elder_name': row['elder_name'] or '',
            'medicine_name': row['medicine_name'] or 'medicine',
            'dosage': row['dosage'] or '',
            'scheduled_time': scheduled_time.strftime('%H:%M')
        })
    return due


def build_message(elder_name: str, medicine_name: str, count: int) -> str:
    idx = min(count, len(MESSAGES) - 1)
    prefix = f"{elder_name} గారూ. " if elder_name else ''
    return f"{prefix}{MESSAGES[idx]} మందు: {medicine_name}."


def mark_reminders(conn, due_list, state: dict, repeat_minutes: int, engine):
    now = datetime.now()
    active_ids = set()
    for item in due_list:
        schedule_id = str(item['schedule_id'])
        active_ids.add(schedule_id)
        entry = state.get(schedule_id, {})
        last_str = entry.get('last_reminded_at')
        last_time = datetime.fromisoformat(last_str) if last_str else None
        if last_time and now - last_time < timedelta(minutes=repeat_minutes):
            continue

        count = entry.get('count', 0)
        message = build_message(item['elder_name'], item['medicine_name'], count)
        speak(message, engine, count)

        state[schedule_id] = {
            'count': min(count + 1, len(MESSAGES) - 1),
            'last_reminded_at': now.isoformat()
        }

    for schedule_id in list(state.keys()):
        if schedule_id not in active_ids:
            del state[schedule_id]

    return state


def run_once(db_path: Path, state_path: Path, repeat_minutes: int):
    if not db_path.exists():
        log.error('SQLite database not found: %s', db_path)
        return 1

    state = load_state(state_path)
    engine = create_engine()

    conn = sqlite3.connect(str(db_path), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    try:
        now = datetime.now()
        due = get_due_schedules(conn, now)
        log.info('Found %s due schedule(s)', len(due))
        state = mark_reminders(conn, due, state, repeat_minutes, engine)
    except Exception as exc:
        log.error('Reminder check failed: %s', exc)
        return 1
    finally:
        conn.close()

    save_state(state_path, state)
    return 0


def run_polling(db_path: Path, state_path: Path, repeat_minutes: int, poll_seconds: int):
    log.info('Starting continuous reminder agent: poll=%ss repeat=%smin', poll_seconds, repeat_minutes)
    try:
        while True:
            run_once(db_path, state_path, repeat_minutes)
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        log.info('Stopped by user')


def test_voice(engine):
    text = 'నమస్కారం. ఇది ఒక పరీక్ష. మీరు మందులు తీసుకునే సమయం అయింది.'
    speak(text, engine)
    time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description='ElderCare Windows Task reminder agent')
    parser.add_argument('--once', action='store_true', help='Run one reminder check and exit')
    parser.add_argument('--poll', action='store_true', help='Run continuously in a loop')
    parser.add_argument('--db', default=DEFAULT_DB_URL, help='SQLite database URL or path')
    parser.add_argument('--state-file', default=str(DEFAULT_STATE_FILE), help='Local JSON reminder state file')
    parser.add_argument('--repeat-minutes', type=int, default=DEFAULT_REPEAT_MINUTES, help='Repeat interval in minutes')
    parser.add_argument('--poll-seconds', type=int, default=DEFAULT_POLL_SECONDS, help='Polling interval in seconds')
    parser.add_argument('--test', action='store_true', help='Run a voice test and exit')
    args = parser.parse_args()

    db_path = Path(normalize_db_path(args.db))
    state_path = Path(args.state_file)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine()

    if args.test:
        test_voice(engine)
        return

    if args.once or not args.poll:
        ret = run_once(db_path, state_path, args.repeat_minutes)
        sys.exit(ret)

    run_polling(db_path, state_path, args.repeat_minutes, args.poll_seconds)


if __name__ == '__main__':
    main()
