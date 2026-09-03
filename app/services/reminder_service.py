"""
Reminder Service — APScheduler integration
Runs background jobs:
  - schedule_todays_reminders: fires at midnight to schedule Level 1 reminders
  - check_missed_doses: fallback interval check for any missed escalation
  - check_low_adherence: weekly low-adherence alerts
  - check_wellness: daily wellness reminder
"""
import atexit
import logging
from datetime import datetime, timedelta, date, time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler = None


# ── Public: get_adaptive_message ─────────────────────────────────────────────

def get_adaptive_reminder_message(elder_name, medicine_name, dosage,
                                   missed_count, lang='en'):
    """Adaptive message used by UI and background jobs."""
    if lang == 'te':
        if missed_count == 0:
            return (f"నమస్కారం. {elder_name} గారూ, మీ {medicine_name} {dosage} "
                    f"తీసుకోవలసిన సమయం అయింది. దయచేసి మందు తీసుకోండి.")
        elif missed_count <= 2:
            return (f"గమనిక. {elder_name} గారూ, మీరు {missed_count} సార్లు "
                    f"{medicine_name} తీసుకోవడం మరచిపోయారు. "
                    f"దయచేసి ఇప్పుడే తీసుకోండి. మీ ఆరోగ్యం ముఖ్యం.")
        elif missed_count <= 4:
            return (f"ముఖ్యమైన హెచ్చరిక! {elder_name} గారూ, మీరు {missed_count} సార్లు "
                    f"{medicine_name} తీసుకోలేదు. వెంటనే తీసుకోండి.")
        else:
            return (f"అత్యవసరం! {elder_name} గారికి {missed_count} రోజులుగా "
                    f"{medicine_name} తీసుకోలేదు. వెంటనే వైద్యసహాయం తీసుకోండి.")
    else:
        if missed_count == 0:
            return (f"Hello. {elder_name}, it is time to take your {medicine_name} "
                    f"{dosage}. Please take it now.")
        elif missed_count <= 2:
            return (f"{elder_name}, you have missed {medicine_name} {missed_count} "
                    f"time(s). Please take it now. Your health is important.")
        elif missed_count <= 4:
            return (f"Warning! {elder_name} has missed {medicine_name} {missed_count} "
                    f"times. Please take it immediately or contact your doctor.")
        else:
            return (f"URGENT! {elder_name} has not taken {medicine_name} for "
                    f"{missed_count} doses. Please seek medical assistance immediately.")


def get_adaptive_severity(missed_count):
    if missed_count == 0:
        return 'low'
    elif missed_count <= 2:
        return 'medium'
    elif missed_count <= 4:
        return 'high'
    else:
        return 'critical'


def get_consecutive_missed_count(elder_id, medicine_id):
    from app.models.adherence import AdherenceRecord
    records = AdherenceRecord.query.filter_by(
        elder_id=elder_id, medicine_id=medicine_id
    ).order_by(AdherenceRecord.scheduled_datetime.desc()).limit(10).all()
    count = 0
    for r in records:
        if r.status == 'missed':
            count += 1
        elif r.status == 'taken':
            break
    return count


# ── Scheduled jobs ────────────────────────────────────────────────────────────

def schedule_todays_reminders(app):
    """
    Midnight job: schedule Level 1 reminders for all active schedules today.
    Also integrates ML early reminders for high-risk doses.
    """
    with app.app_context():
        try:
            from app.models.schedule import MedicineSchedule
            from app.models.elder import Elder
            from app.services.adaptive_reminder_engine import schedule_day_reminders
            from app.services.ml_service import get_risk_score

            today = date.today()
            today_str = today.isoformat()
            day_name = today.strftime('%A').lower()

            schedules = MedicineSchedule.query.filter(
                MedicineSchedule.is_active == True
            ).all()

            eligible = [s for s in schedules
                        if not s.day_of_week or
                        s.day_of_week == 'all' or
                        s.day_of_week == day_name]

            # Schedule standard Level 1 reminders
            schedule_day_reminders(app, eligible, today_str)

            # ML early reminders: risk_score > 70 → fire 30 min early
            for s in eligible:
                try:
                    risk = get_risk_score(s.elder_id)
                    if risk.get('risk_score', 0) > 70:
                        early_dt = datetime.combine(today, s.scheduled_time) - timedelta(minutes=30)
                        if early_dt > datetime.now():
                            from app.services.reminder_service import _scheduler
                            job_id = f"early_{s.id}_{s.elder_id}_{today_str}"
                            _scheduler.add_job(
                                func=_fire_early_reminder,
                                args=[app, s.id, s.elder_id, s.medicine_id],
                                trigger='date', run_date=early_dt,
                                id=job_id, replace_existing=True
                            )
                            logger.info(f"Early ML reminder for elder={s.elder_id} risk={risk['risk_score']}")
                except Exception:
                    pass

            logger.info(f"Scheduled {len(eligible)} reminders for {today_str}")
        except Exception as e:
            logger.error(f"schedule_todays_reminders error: {e}")


def _fire_early_reminder(app, schedule_id, elder_id, medicine_id):
    """Fire an early warning reminder when ML risk_score > 70."""
    with app.app_context():
        try:
            from app import db
            from app.models.elder import Elder
            from app.models.medicine import Medicine
            from app.models.alert import Alert

            elder = Elder.query.get(elder_id)
            med = Medicine.query.get(medicine_id)
            if not elder or not med:
                return

            alert = Alert(
                elder_id=elder_id,
                caretaker_id=elder.caretaker_id,
                alert_type='general',
                message=(f"AI Prediction: {elder.name} has a high risk of missing "
                         f"{med.name} today. Consider an early check-in."),
                severity='medium'
            )
            db.session.add(alert)
            db.session.commit()
        except Exception as e:
            logger.error(f"_fire_early_reminder error: {e}")


def check_missed_doses(app):
    """
    Interval fallback: catch any doses missed without escalation.
    Runs every 15 minutes.
    Also sends email alerts for newly missed doses.
    """
    with app.app_context():
        try:
            from app import db
            from app.models.schedule import MedicineSchedule
            from app.models.adherence import AdherenceRecord
            from app.models.alert import Alert
            from app.models.elder import Elder
            from app.models.user import User
            from app.services.email_service import send_missed_dose_email
            import threading

            now = datetime.now()
            today = date.today()
            alert_delay = app.config.get('ALERT_DELAY_MINUTES', 30)
            cutoff_time = now - timedelta(minutes=alert_delay)
            day_name = today.strftime('%A').lower()

            schedules = MedicineSchedule.query.filter(
                MedicineSchedule.is_active == True
            ).all()

            for schedule in schedules:
                if (schedule.day_of_week and schedule.day_of_week != 'all'
                        and schedule.day_of_week != day_name):
                    continue

                scheduled_dt = datetime.combine(today, schedule.scheduled_time)
                if scheduled_dt > cutoff_time:
                    continue

                existing = AdherenceRecord.query.filter_by(
                    schedule_id=schedule.id, elder_id=schedule.elder_id
                ).filter(
                    AdherenceRecord.scheduled_datetime >= datetime.combine(today, time.min),
                    AdherenceRecord.scheduled_datetime <= datetime.combine(today, time.max)
                ).first()

                if existing and existing.status in ['taken', 'skipped']:
                    continue

                newly_missed = False
                if not existing:
                    db.session.add(AdherenceRecord(
                        schedule_id=schedule.id, elder_id=schedule.elder_id,
                        medicine_id=schedule.medicine_id,
                        scheduled_datetime=scheduled_dt, status='missed'
                    ))
                    newly_missed = True
                elif existing.status == 'pending':
                    existing.status = 'missed'
                    newly_missed = True

                # Adaptive alert
                alert_exists = Alert.query.filter_by(
                    elder_id=schedule.elder_id,
                    related_schedule_id=schedule.id,
                    alert_type='missed_dose',
                    is_read=False
                ).filter(
                    Alert.sent_at >= datetime.combine(today, time.min)
                ).first()

                if not alert_exists:
                    elder = Elder.query.get(schedule.elder_id)
                    if elder and schedule.medicine:
                        missed_count = get_consecutive_missed_count(
                            schedule.elder_id, schedule.medicine_id)
                        severity = get_adaptive_severity(missed_count)
                        msg = (
                            f"{elder.name} missed {schedule.medicine.name} "
                            f"({schedule.medicine.dosage}) at "
                            f"{schedule.scheduled_time.strftime('%I:%M %p')}."
                        )
                        if missed_count >= 3:
                            msg = (f"⚠️ REPEATED MISS ({missed_count}x): "
                                   f"{elder.name} — {schedule.medicine.name}. "
                                   f"Immediate attention required.")
                        db.session.add(Alert(
                            elder_id=schedule.elder_id,
                            caretaker_id=elder.caretaker_id,
                            alert_type='missed_dose', message=msg,
                            severity=severity,
                            related_medicine_id=schedule.medicine_id,
                            related_schedule_id=schedule.id
                        ))
                        
                        # Send email for newly missed doses
                        if newly_missed:
                            caretaker = User.query.get(elder.caretaker_id)
                            if caretaker and caretaker.email:
                                sched_time = schedule.scheduled_time.strftime('%I:%M %p')
                                missed_count_val = get_consecutive_missed_count(
                                    schedule.elder_id, schedule.medicine_id)
                                
                                def _send_missed_email(ct_email=caretaker.email,
                                                      ct_name=caretaker.full_name or caretaker.username,
                                                      ed_name=elder.name,
                                                      med_name=schedule.medicine.name,
                                                      med_dose=schedule.medicine.dosage,
                                                      sched_t=sched_time,
                                                      m_count=missed_count_val):
                                    with app.app_context():
                                        send_missed_dose_email(
                                            caretaker_email=ct_email,
                                            caretaker_name=ct_name,
                                            elder_name=ed_name,
                                            medicine_name=med_name,
                                            dosage=med_dose,
                                            scheduled_time=sched_t,
                                            missed_count=m_count
                                        )
                                threading.Thread(target=_send_missed_email, daemon=True).start()
            
            db.session.commit()
        except Exception as e:
            logger.error(f"check_missed_doses error: {e}")


def check_low_adherence(app):
    with app.app_context():
        try:
            from app import db
            from app.models.adherence import AdherenceRecord
            from app.models.alert import Alert
            from app.models.elder import Elder

            since = datetime.utcnow() - timedelta(days=7)
            for elder in Elder.query.filter_by(is_active=True).all():
                records = AdherenceRecord.query.filter(
                    AdherenceRecord.elder_id == elder.id,
                    AdherenceRecord.scheduled_datetime >= since
                ).all()
                total = len(records)
                if total < 5:
                    continue
                taken = sum(1 for r in records if r.status == 'taken')
                rate = (taken / total) * 100
                if rate < 60:
                    week_start = datetime.utcnow() - timedelta(days=7)
                    existing = Alert.query.filter(
                        Alert.elder_id == elder.id,
                        Alert.alert_type == 'low_adherence',
                        Alert.sent_at >= week_start
                    ).first()
                    if not existing:
                        db.session.add(Alert(
                            elder_id=elder.id,
                            caretaker_id=elder.caretaker_id,
                            alert_type='low_adherence',
                            message=(f"{elder.name}'s adherence is {rate:.1f}% "
                                     f"this week — critically low. Follow up immediately."),
                            severity='critical' if rate < 40 else 'high'
                        ))
            db.session.commit()
        except Exception as e:
            logger.error(f"check_low_adherence error: {e}")


def send_daily_summary(app):
    """Send daily medication summary email to all caretakers at 9 PM, store in DB."""
    with app.app_context():
        try:
            from app import db
            from app.models.user import User
            from app.models.elder import Elder
            from app.models.adherence import AdherenceRecord
            from app.models.reminder_log import ReminderLog
            from app.models.daily_report import DailyReport
            from app.services.email_service import send_daily_summary_email
            from datetime import date as date_cls
            from datetime import time as time_obj
            import threading

            today = date_cls.today()
            caretakers = User.query.filter(
                User.is_active == True,
                User.email != None,
                User.email != ''
            ).all()

            for caretaker in caretakers:
                elders = Elder.query.filter_by(
                    caretaker_id=caretaker.id, is_active=True
                ).all()
                if not elders:
                    continue

                summary = []
                for elder in elders:
                    records = AdherenceRecord.query.filter(
                        AdherenceRecord.elder_id == elder.id,
                        AdherenceRecord.scheduled_datetime >= datetime.combine(today, time_obj.min),
                        AdherenceRecord.scheduled_datetime <= datetime.combine(today, time_obj.max)
                    ).all()

                    total      = len(records)
                    taken      = sum(1 for r in records if r.status == 'taken')
                    taken_late = sum(1 for r in records if r.status == 'taken_late')
                    missed     = sum(1 for r in records if r.status == 'missed')

                    # Count reminders fired today for this elder
                    reminders_today = ReminderLog.query.filter(
                        ReminderLog.elder_id == elder.id,
                        ReminderLog.fired_at >= datetime.combine(today, time_obj.min),
                        ReminderLog.fired_at <= datetime.combine(today, time_obj.max)
                    ).count()

                    rate = round((taken + taken_late) / total * 100, 1) if total > 0 else 0

                    # Collect medicine details
                    medicines_detail = {}
                    for record in records:
                        med_id = record.medicine_id
                        if med_id not in medicines_detail:
                            medicines_detail[med_id] = {
                                'name': record.medicine.name if record.medicine else 'Unknown',
                                'dosage': record.medicine.dosage if record.medicine else 'N/A',
                                'taken': 0,
                                'missed': 0,
                            }
                        if record.status == 'taken' or record.status == 'taken_late':
                            medicines_detail[med_id]['taken'] += 1
                        elif record.status == 'missed':
                            medicines_detail[med_id]['missed'] += 1

                    # Persist to daily_reports table
                    existing_report = DailyReport.query.filter_by(
                        report_date=today,
                        caretaker_id=caretaker.id,
                        elder_id=elder.id
                    ).first()

                    if existing_report:
                        existing_report.total_scheduled   = total
                        existing_report.total_taken        = taken
                        existing_report.total_taken_late   = taken_late
                        existing_report.total_missed       = missed
                        existing_report.total_reminders    = reminders_today
                        existing_report.adherence_percent  = rate
                    else:
                        db.session.add(DailyReport(
                            report_date        = today,
                            caretaker_id       = caretaker.id,
                            elder_id           = elder.id,
                            total_scheduled    = total,
                            total_taken        = taken,
                            total_taken_late   = taken_late,
                            total_missed       = missed,
                            total_reminders    = reminders_today,
                            adherence_percent  = rate
                        ))

                    summary.append({
                        'elder':       elder.name,
                        'taken':       taken,
                        'taken_late':  taken_late,
                        'missed':      missed,
                        'total':       total,
                        'rate':        rate,
                        'reminders':   reminders_today,
                        'medicines':   list(medicines_detail.values()) if medicines_detail else []
                    })

                db.session.commit()

                if summary:
                    def _send(ct=caretaker, s=summary):
                        with app.app_context():
                            sent = send_daily_summary_email(
                                caretaker_email=ct.email,
                                caretaker_name=ct.full_name or ct.username,
                                summary=s
                            )
                            if sent:
                                # Mark email_sent on all today's reports for this caretaker
                                from app.models.daily_report import DailyReport as DR
                                DR.query.filter_by(
                                    report_date=today, caretaker_id=ct.id
                                ).update({'email_sent': True, 'email_sent_at': datetime.now()})
                                db.session.commit()
                    threading.Thread(target=_send, daemon=True).start()

        except Exception as e:
            logger.error(f"send_daily_summary error: {e}")


def check_wellness(app):
    with app.app_context():
        try:
            from app import db
            from app.models.elder import Elder
            from app.models.alert import Alert
            from app.models.wellness import WellnessCheck

            today = date.today()
            for elder in Elder.query.filter_by(is_active=True).all():
                check = WellnessCheck.query.filter(
                    WellnessCheck.elder_id == elder.id,
                    WellnessCheck.checked_at >= datetime.combine(today, time.min)
                ).first()
                if not check:
                    exists = Alert.query.filter(
                        Alert.elder_id == elder.id,
                        Alert.alert_type == 'general',
                        Alert.message.like('%wellness%'),
                        Alert.sent_at >= datetime.combine(today, time.min)
                    ).first()
                    if not exists:
                        db.session.add(Alert(
                            elder_id=elder.id,
                            caretaker_id=elder.caretaker_id,
                            alert_type='general',
                            message=f"Daily wellness check pending for {elder.name}.",
                            severity='low'
                        ))
            db.session.commit()
        except Exception as e:
            logger.error(f"check_wellness error: {e}")


# ── Scheduler init ────────────────────────────────────────────────────────────

def init_scheduler(app):
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        return

    interval_minutes = app.config.get('SCHEDULER_INTERVAL_MINUTES', 15)

    _scheduler = BackgroundScheduler(daemon=True)

    # Midnight job: schedule today's Level 1 reminders
    _scheduler.add_job(
        func=schedule_todays_reminders, args=[app],
        trigger=CronTrigger(hour=0, minute=0),
        id='schedule_daily_reminders', replace_existing=True
    )

    # Interval fallback: catch any missed escalations
    _scheduler.add_job(
        func=check_missed_doses, args=[app],
        trigger=IntervalTrigger(minutes=interval_minutes),
        id='check_missed_doses', replace_existing=True
    )

    # Daily low-adherence check
    _scheduler.add_job(
        func=check_low_adherence, args=[app],
        trigger=IntervalTrigger(hours=24),
        id='check_low_adherence', replace_existing=True
    )

    # Daily summary email at 9 PM
    _scheduler.add_job(
        func=send_daily_summary, args=[app],
        trigger=CronTrigger(hour=21, minute=0),
        id='send_daily_summary', replace_existing=True
    )

    # Twice-daily wellness reminder
    _scheduler.add_job(
        func=check_wellness, args=[app],
        trigger=IntervalTrigger(hours=12),
        id='check_wellness', replace_existing=True
    )

    # Voice reminders — fires at EXACT scheduled time via fire_reminder()
    # No polling needed — voice is triggered directly in adaptive_reminder_engine.py
    # Just reset state at midnight
    from app.services.voice_scheduler import reset_voice_state
    _scheduler.add_job(
        func=reset_voice_state,
        trigger=CronTrigger(hour=0, minute=1),
        id='reset_voice_state', replace_existing=True
    )

    try:
        _scheduler.start()
        # Immediately schedule today's reminders on startup
        schedule_todays_reminders(app)
        logger.info(f"Scheduler started — interval={interval_minutes}min")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
    atexit.register(stop_scheduler)


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
