"""
Adaptive Reminder Engine
========================
6-reminder cycle repeating every 10 minutes.
After 6 unanswered reminders → auto-mark missed + email caretaker.

Time-of-day voice modulation:
  Morning   (6–11 AM)  → energetic, cheerful  (rate=0.80, pitch=1.1)
  Afternoon (12–5 PM)  → calm, friendly        (rate=0.75, pitch=1.0)
  Night     (6–10 PM)  → soft, caring          (rate=0.65, pitch=0.9)

Reminder texts escalate every 2 reminders:
  1-2: Gentle       → "నమస్కారం. మీ మందు సమయం వచ్చింది."
  3-4: Moderate     → "మీరు ఇంకా మందు తీసుకోలేదు."
  5-6: Critical     → "ముఖ్యమైన హెచ్చరిక. వెంటనే తీసుకోండి."
"""
import logging
from datetime import datetime, timedelta, date, time as time_obj

logger = logging.getLogger(__name__)

MAX_REMINDERS = 6
REMINDER_INTERVAL_MINUTES = 2


# ── Time-of-day modulation ────────────────────────────────────────────────────

def get_time_of_day(hour: int) -> str:
    """Return time period: morning / afternoon / night."""
    if 6 <= hour < 12:
        return 'morning'
    if 12 <= hour < 18:
        return 'afternoon'
    if 18 <= hour < 23:
        return 'night'
    return 'morning'  # default for late night / early morning


# Voice modulation per time-of-day
VOICE_MODULATION = {
    'morning':   {'rate': 0.90, 'pitch': 1.05, 'volume': 0.92, 'label': 'Energetic & Cheerful'},
    'afternoon': {'rate': 0.88, 'pitch': 1.00, 'volume': 0.88, 'label': 'Calm & Friendly'},
    'night':     {'rate': 0.85, 'pitch': 0.96, 'volume': 0.85, 'label': 'Soft & Caring'},
}

# Additional modulation for repeated reminders (escalation layer)
REPEAT_MODULATION = {
    1: {'rate_delta': 0,    'pitch_delta': 0},    # reminder 1 — baseline
    2: {'rate_delta': 0,    'pitch_delta': 0},    # reminder 2 — same
    3: {'rate_delta': 0.05, 'pitch_delta': 0.05}, # reminder 3 — slightly firmer
    4: {'rate_delta': 0.05, 'pitch_delta': 0.05}, # reminder 4
    5: {'rate_delta': 0.10, 'pitch_delta': 0.15}, # reminder 5 — urgent
    6: {'rate_delta': 0.15, 'pitch_delta': 0.20}, # reminder 6 — critical
}


# ── Telugu/English reminder texts per escalation level ───────────────────────

def _build_texts(elder_name: str, medicine_name: str, dosage: str,
                  scheduled_time: str, reminder_num: int,
                  time_of_day: str) -> dict:
    """
    Build exact Telugu + English reminder texts per reminder level and time of day.
    These are the EXACT specified messages.
    """
    # ── Telugu messages ────────────────────────────────────────────────────────
    TELUGU = {
        'morning': [
            '',  # index 0 unused
            'శుభోదయం. మీ మందు తీసుకునే సమయం వచ్చింది.',
            'దయచేసి మీ మందు తీసుకోవడం మర్చిపోవద్దు.',
            'మీ మందు ఇంకా తీసుకోలేదు. దయచేసి ఇప్పుడు తీసుకోండి.',
            'మీ ఆరోగ్యం కోసం మందు తీసుకోవడం చాలా ముఖ్యం.',
            'మీ మందు ఇంకా పెండింగ్‌లో ఉంది. వెంటనే తీసుకోండి.',
            'హెచ్చరిక. మీ మందు సమయం చాలా దాటింది. దయచేసి వెంటనే మందు తీసుకోండి.',
        ],
        'afternoon': [
            '',
            'నమస్కారం. మీ మందు సమయం వచ్చింది.',
            'దయచేసి మీ మందు తీసుకోవడం మర్చిపోవద్దు.',
            'మీ మందు ఇంకా తీసుకోలేదు. దయచేసి తీసుకోండి.',
            'మీ ఆరోగ్య సంరక్షణ కోసం మందు తీసుకోవడం అవసరం.',
            'మీ మందు ఇంకా పెండింగ్‌లో ఉంది.',
            'హెచ్చరిక. మందు సమయం చాలా దాటింది.',
        ],
        'night': [
            '',
            'శుభ సాయంత్రం. మీ మందు తీసుకునే సమయం వచ్చింది.',
            'దయచేసి మీ రాత్రి మందు తీసుకోండి.',
            'మీ మందు ఇంకా తీసుకోలేదు.',
            'మీ ఆరోగ్యం కోసం మందు తీసుకోవడం అవసరం.',
            'మీ మందు ఇంకా పెండింగ్‌లో ఉంది.',
            'హెచ్చరిక. మందు సమయం చాలా దాటింది. దయచేసి వెంటనే మందు తీసుకోండి.',
        ],
    }

    # ── English messages ────────────────────────────────────────────────────────
    ENGLISH = {
        'morning': [
            '',
            f'Good morning {elder_name}. It is time to take your {medicine_name} {dosage}.',
            f'Please do not forget to take your {medicine_name}.',
            f'You have not yet taken {medicine_name}. Please take it now.',
            f'Taking your medicine is very important for your health.',
            f'Your {medicine_name} is still pending. Please take it immediately.',
            f'Warning. Your medicine time has passed. Please take {medicine_name} immediately.',
        ],
        'afternoon': [
            '',
            f'Hello {elder_name}. It is time to take your {medicine_name} {dosage}.',
            f'Please do not forget to take your {medicine_name}.',
            f'You have not yet taken {medicine_name}. Please take it.',
            f'Taking your medicine is necessary for your health.',
            f'Your {medicine_name} is still pending.',
            f'Warning. Medicine time has passed significantly.',
        ],
        'night': [
            '',
            f'Good evening {elder_name}. It is time to take your {medicine_name} {dosage}.',
            f'Please take your night medicine {medicine_name}.',
            f'You have not yet taken {medicine_name}.',
            f'Taking your medicine is necessary for your health.',
            f'Your {medicine_name} is still pending.',
            f'Warning. Medicine time has passed. Please take {medicine_name} immediately.',
        ],
    }

    tod = time_of_day if time_of_day in TELUGU else 'afternoon'
    idx = min(reminder_num, 6)

    te_base = TELUGU[tod][idx]
    en_base = ENGLISH[tod][idx]

    # Use a more natural Telugu reminder style that matches the user's request.
    if elder_name:
        if reminder_num == 1:
            te_full = (
                f"{elder_name} గారూ. "
                f"మీ {medicine_name} {dosage} తీసుకునే సమయం వచ్చింది. "
                f"దయచేసి ఇప్పుడు తీసుకోండి."
            )
        else:
            te_full = (
                f"{elder_name} గారూ. "
                f"మీ మందులు ఇంకా తీసుకోలేదు. "
                f"ఇది గుర్తుచేసే సందేశం."
            )
    else:
        te_full = te_base

    return {'te': te_full.strip(), 'en': en_base}


# ── State helpers ─────────────────────────────────────────────────────────────

def _get_or_create_state(db, schedule, today):
    from app.models.reminder_state import ReminderState
    state = ReminderState.query.filter_by(
        schedule_id=schedule.id,
        elder_id=schedule.elder_id,
        dose_date=today
    ).first()
    if not state:
        state = ReminderState(
            schedule_id=schedule.id,
            elder_id=schedule.elder_id,
            dose_date=today,
            reminder_level=1,
            snooze_count=0,
            status='active'
        )
        db.session.add(state)
        db.session.flush()
    return state


# ── Core: fire_reminder ───────────────────────────────────────────────────────

def fire_reminder(app, schedule_id: int, elder_id: int,
                   dose_date_str: str, reminder_num: int):
    """
    Fire reminder number `reminder_num` (1-6).
    If not confirmed after MAX_REMINDERS → auto-mark missed.
    """
    with app.app_context():
        try:
            from app import db
            from app.models.schedule import MedicineSchedule
            from app.models.elder import Elder
            from app.models.adherence import AdherenceRecord
            from app.models.alert import Alert
            from app.models.reminder_state import ReminderState

            today = date.fromisoformat(dose_date_str)
            schedule = MedicineSchedule.query.get(schedule_id)
            if not schedule or not schedule.is_active:
                return

            elder = Elder.query.get(elder_id)
            if not elder:
                return

            # Already taken? Stop.
            taken = AdherenceRecord.query.filter_by(
                schedule_id=schedule_id, elder_id=elder_id, status='taken'
            ).filter(
                AdherenceRecord.scheduled_datetime >= datetime.combine(today, time_obj.min),
                AdherenceRecord.scheduled_datetime <= datetime.combine(today, time_obj.max)
            ).first()
            if taken:
                _resolve_state(db, schedule_id, elder_id, today)
                return

            state = _get_or_create_state(db, schedule, today)
            if state.status == 'resolved':
                return

            med_name  = schedule.medicine.name   if schedule.medicine else 'medicine'
            dosage    = schedule.medicine.dosage  if schedule.medicine else ''
            sched_time = schedule.scheduled_time.strftime('%I:%M %p')
            hour      = datetime.now().hour
            tod       = get_time_of_day(hour)

            texts = _build_texts(elder.name, med_name, dosage, sched_time,
                                  reminder_num, tod)

            # Calculate voice modulation = base (time-of-day) + delta (reminder escalation)
            base_mod  = VOICE_MODULATION[tod]
            delta_mod = REPEAT_MODULATION.get(reminder_num, REPEAT_MODULATION[6])
            voice_mod = {
                'rate':   min(1.1, round(base_mod['rate']   + delta_mod['rate_delta'],  2)),
                'pitch':  min(1.5, round(base_mod['pitch']  + delta_mod['pitch_delta'], 2)),
                'volume': base_mod['volume'],
                'time_of_day': tod,
                'reminder_num': reminder_num,
            }

            # Update state
            state.reminder_level = min(3, (reminder_num - 1) // 2 + 1)
            state.snooze_count   = state.snooze_count or 0
            state.last_reminded_at = datetime.now()
            next_time = datetime.now() + timedelta(minutes=REMINDER_INTERVAL_MINUTES)
            state.next_reminder_at = next_time

            # Alert severity
            if reminder_num <= 2:
                severity = 'low'
            elif reminder_num <= 4:
                severity = 'high'
            else:
                severity = 'critical'

            alert_msg = (
                f"Reminder {reminder_num}/{MAX_REMINDERS}: {elder.name} — "
                f"Take {med_name} ({dosage}) scheduled at {sched_time}."
            )
            if reminder_num >= 5:
                alert_msg += " CRITICAL — Multiple reminders unanswered."

            # Avoid duplicate unread alerts for same schedule today
            existing_alert = Alert.query.filter_by(
                elder_id=elder_id,
                related_schedule_id=schedule_id,
                alert_type='missed_dose',
                is_read=False
            ).filter(
                Alert.sent_at >= datetime.combine(today, time_obj.min)
            ).first()

            if not existing_alert or reminder_num >= 3:
                db.session.add(Alert(
                    elder_id=elder_id,
                    caretaker_id=elder.caretaker_id,
                    alert_type='missed_dose',
                    message=alert_msg,
                    severity=severity,
                    related_medicine_id=schedule.medicine_id,
                    related_schedule_id=schedule_id
                ))

            db.session.commit()

            # ── Log this reminder in reminder_logs ───────────────────────────
            try:
                from app.models.reminder_log import ReminderLog
                db.session.add(ReminderLog(
                    schedule_id=schedule_id,
                    elder_id=elder_id,
                    medicine_id=schedule.medicine_id,
                    reminder_num=reminder_num,
                    time_of_day=tod,
                    lang='te',
                    text_te=texts.get('te', ''),
                    text_en=texts.get('en', ''),
                    status='fired'
                ))
                db.session.commit()
            except Exception as log_err:
                logger.warning(f'reminder_log write failed: {log_err}')

            # ── Play Telugu voice directly from server (no browser needed) ───
            try:
                from app.services.voice_scheduler import play_voice_for_reminder
                play_voice_for_reminder(
                    elder_name=elder.name,
                    medicine_name=med_name,
                    reminder_num=reminder_num
                )
            except Exception as ve:
                logger.warning(f'Voice play failed: {ve}')

            # ── Emit WebSocket event → dashboard popup only (NO browser audio) ─
            # PC speaker already played via voice_scheduler above.
            # Set audio_url_te='' and mute=True so browser shows popup but doesn't play audio.
            try:
                from app.sockets.events import emit_reminder
                emit_reminder(
                    elder_id=elder_id,
                    schedule_id=schedule_id,
                    medicine_id=schedule.medicine_id,
                    medicine_name=med_name,
                    dosage=dosage,
                    scheduled_time=sched_time,
                    level=state.reminder_level,
                    texts=texts,
                    voice_mod=voice_mod,
                    reminder_num=reminder_num,
                    max_reminders=MAX_REMINDERS
                )
            except Exception as e:
                logger.warning(f"WebSocket emit failed: {e}")

            # ── Web Push notification ────────────────────────────────────────
            try:
                from app.routes.push_notifications import get_subscriptions_for_user
                from app.services.push_service import PushService
                for sub in get_subscriptions_for_user(elder.caretaker_id):
                    PushService.send_medicine_reminder(
                        subscription_info=sub,
                        elder_name=elder.name,
                        medicine_name=med_name,
                        dosage=dosage,
                        scheduled_time=sched_time,
                        level=state.reminder_level,
                        schedule_id=schedule_id,
                        elder_id=elder_id,
                        medicine_id=schedule.medicine_id,
                        reminder_num=reminder_num
                    )
            except Exception as e:
                logger.warning(f"Push failed: {e}")

            # ── Schedule next reminder or auto-miss ──────────────────────────
            if reminder_num < MAX_REMINDERS:
                _schedule_next_reminder(app, schedule_id, elder_id,
                                         dose_date_str, reminder_num + 1, next_time)
            else:
                # Final reminder exceeded → auto-miss after 10 more minutes
                _schedule_auto_miss(app, schedule_id, elder_id, dose_date_str, next_time)

            logger.info(f"Reminder {reminder_num}/{MAX_REMINDERS} fired "
                         f"for {elder.name} — {med_name} [{tod}]")

        except Exception as e:
            logger.error(f"fire_reminder error: {e}")


# ── Backward-compat alias used by reminder_service.py ────────────────────────
def fire_level_reminder(app, schedule_id: int, elder_id: int,
                         dose_date_str: str, level: int):
    """Maps old 3-level API to new 6-reminder cycle."""
    reminder_num = {1: 1, 2: 3, 3: 5}.get(level, 1)
    fire_reminder(app, schedule_id, elder_id, dose_date_str, reminder_num)


# ── Auto-miss ─────────────────────────────────────────────────────────────────

def auto_mark_missed(app, schedule_id: int, elder_id: int, dose_date_str: str):
    """Auto-mark dose as missed after all reminders exhausted."""
    with app.app_context():
        try:
            from app import db
            from app.models.schedule import MedicineSchedule
            from app.models.adherence import AdherenceRecord

            today = date.fromisoformat(dose_date_str)
            schedule = MedicineSchedule.query.get(schedule_id)
            if not schedule:
                return

            taken = AdherenceRecord.query.filter_by(
                schedule_id=schedule_id, elder_id=elder_id, status='taken'
            ).filter(
                AdherenceRecord.scheduled_datetime >= datetime.combine(today, time_obj.min),
                AdherenceRecord.scheduled_datetime <= datetime.combine(today, time_obj.max)
            ).first()
            if taken:
                return

            scheduled_dt = datetime.combine(today, schedule.scheduled_time)
            existing = AdherenceRecord.query.filter_by(
                schedule_id=schedule_id, elder_id=elder_id
            ).filter(
                AdherenceRecord.scheduled_datetime >= datetime.combine(today, time_obj.min),
                AdherenceRecord.scheduled_datetime <= datetime.combine(today, time_obj.max)
            ).first()

            if existing and existing.status not in ['taken', 'skipped']:
                existing.status = 'missed'
            elif not existing:
                db.session.add(AdherenceRecord(
                    schedule_id=schedule_id, elder_id=elder_id,
                    medicine_id=schedule.medicine_id,
                    scheduled_datetime=scheduled_dt, status='missed'
                ))

            _resolve_state(db, schedule_id, elder_id, today)
            db.session.commit()

            # Escalate to caretaker
            from app.services.escalation_service import EscalationService
            EscalationService.escalate(app, elder_id)

            # Email notification
            try:
                from app.models.elder import Elder
                from app.models.medicine import Medicine
                from app.models.user import User
                from app.services.email_service import send_missed_dose_email
                from app.services.reminder_service import get_consecutive_missed_count
                import threading
                elder = Elder.query.get(elder_id)
                med   = Medicine.query.get(schedule.medicine_id)
                ct    = User.query.get(elder.caretaker_id) if elder else None
                if elder and med and ct and ct.email:
                    missed_count = get_consecutive_missed_count(elder_id, schedule.medicine_id)
                    sched_time   = schedule.scheduled_time.strftime('%I:%M %p')
                    def _send(a=app, e=elder, m=med, c=ct,
                              mc=missed_count, st=sched_time):
                        with a.app_context():
                            send_missed_dose_email(
                                caretaker_email=c.email,
                                caretaker_name=c.full_name or c.username,
                                elder_name=e.name,
                                medicine_name=m.name,
                                dosage=m.dosage,
                                scheduled_time=st,
                                missed_count=mc,
                                reminders_sent=MAX_REMINDERS
                            )
                    threading.Thread(target=_send, daemon=True).start()
            except Exception as e:
                logger.warning(f"Auto-miss email error: {e}")

            logger.info(f"Auto-marked missed after {MAX_REMINDERS} reminders: "
                         f"schedule={schedule_id}, elder={elder_id}")
        except Exception as e:
            logger.error(f"auto_mark_missed error: {e}")


def _resolve_state(db, schedule_id, elder_id, today):
    from app.models.reminder_state import ReminderState
    state = ReminderState.query.filter_by(
        schedule_id=schedule_id, elder_id=elder_id, dose_date=today
    ).first()
    if state:
        state.status = 'resolved'


# ── Scheduling helpers ────────────────────────────────────────────────────────

def _schedule_next_reminder(app, schedule_id, elder_id, dose_date_str,
                              reminder_num, run_at):
    from app.services.reminder_service import _scheduler
    if not _scheduler or not _scheduler.running:
        return
    job_id = f"reminder_{schedule_id}_{elder_id}_{dose_date_str}_R{reminder_num}"
    _scheduler.add_job(
        func=fire_reminder,
        args=[app, schedule_id, elder_id, dose_date_str, reminder_num],
        trigger='date', run_date=run_at,
        id=job_id, replace_existing=True, misfire_grace_time=120
    )


def _schedule_auto_miss(app, schedule_id, elder_id, dose_date_str, run_at):
    from app.services.reminder_service import _scheduler
    if not _scheduler or not _scheduler.running:
        return
    job_id = f"automiss_{schedule_id}_{elder_id}_{dose_date_str}"
    _scheduler.add_job(
        func=auto_mark_missed,
        args=[app, schedule_id, elder_id, dose_date_str],
        trigger='date', run_date=run_at,
        id=job_id, replace_existing=True, misfire_grace_time=120
    )


# ── Day scheduling ────────────────────────────────────────────────────────────

def schedule_day_reminders(app, schedules, today_str: str):
    """Schedule Reminder 1 for all active schedules at their exact time."""
    from app.services.reminder_service import _scheduler
    if not _scheduler or not _scheduler.running:
        return

    today = date.fromisoformat(today_str)
    now   = datetime.now()

    for schedule in schedules:
        scheduled_dt = datetime.combine(today, schedule.scheduled_time)
        job_id = f"reminder_{schedule.id}_{schedule.elder_id}_{today_str}_R1"
        
        if scheduled_dt < now:
            # Past time on today — check if reminder already fired RECENTLY
            from app.models.reminder_state import ReminderState
            state = ReminderState.query.filter_by(
                schedule_id=schedule.id,
                elder_id=schedule.elder_id,
                dose_date=today
            ).first()
            
            # Check if reminder fired in the last 5 minutes
            already_fired = False
            if state and state.last_reminded_at:
                time_since_last_fire = now - state.last_reminded_at
                # If fired within last 5 minutes, don't fire again
                if time_since_last_fire.total_seconds() < 300:
                    already_fired = True
                    logger.debug(f"Schedule {schedule.id} fired {time_since_last_fire.total_seconds():.0f}s ago, skipping")
            
            if already_fired:
                continue
            
            # Not fired recently — fire immediately
            logger.info(f"Past time for schedule {schedule.id} at {scheduled_dt} — firing immediately (now={now})")
            _scheduler.add_job(
                func=fire_reminder,
                args=[app, schedule.id, schedule.elder_id, today_str, 1],
                trigger='date', run_date=now,
                id=job_id, replace_existing=True, misfire_grace_time=30
            )
        else:
            # Future time — schedule normally
            _scheduler.add_job(
                func=fire_reminder,
                args=[app, schedule.id, schedule.elder_id, today_str, 1],
                trigger='date', run_date=scheduled_dt,
                id=job_id, replace_existing=True, misfire_grace_time=120
            )
            logger.debug(f"Scheduled R1 for schedule={schedule.id} at {scheduled_dt}")


# ── Snooze ────────────────────────────────────────────────────────────────────

def snooze_reminder(schedule_id: int, elder_id: int, dose_date: date, app):
    """Snooze — postpone next reminder by 10 min. Cap at 3 snoozes."""
    from app import db
    from app.models.reminder_state import ReminderState

    today = dose_date or date.today()
    state = ReminderState.query.filter_by(
        schedule_id=schedule_id, elder_id=elder_id, dose_date=today
    ).first()
    if not state or state.status == 'resolved':
        return {'success': False, 'error': 'No active reminder'}

    state.snooze_count = (state.snooze_count or 0) + 1
    snooze_disabled = state.snooze_count >= 3

    # Advance to next reminder number
    current_reminder_num = state.reminder_level * 2  # rough mapping
    next_reminder_num = min(MAX_REMINDERS, current_reminder_num + 1)
    next_time = datetime.now() + timedelta(minutes=REMINDER_INTERVAL_MINUTES)
    state.next_reminder_at = next_time
    state.status = 'snoozed'
    db.session.commit()

    dose_date_str = today.isoformat()
    _schedule_next_reminder(app, schedule_id, elder_id, dose_date_str,
                             next_reminder_num, next_time)
    return {
        'success': True,
        'snooze_disabled': snooze_disabled,
        'next_reminder': next_reminder_num,
        'next_at': next_time.isoformat()
    }


def get_active_reminders_for_elder(elder_id: int):
    from app.models.reminder_state import ReminderState
    today = date.today()
    return ReminderState.query.filter_by(
        elder_id=elder_id, dose_date=today, status='active'
    ).all()
