"""
Escalation Service
==================
Level 1: 1 missed dose in 24h  → in-app alert (medium)
Level 2: 3+ missed in 24h      → in-app alert (high) + email
Level 3: 3+ consecutive days   → in-app alert (critical) + email + SMS log
"""
import logging
from datetime import datetime, timedelta, date

logger = logging.getLogger(__name__)


class EscalationService:

    @staticmethod
    def escalate(app, elder_id: int):
        """Evaluate missed dose counts and fire appropriate escalation."""
        with app.app_context():
            try:
                from app import db
                from app.models.adherence import AdherenceRecord
                from app.models.elder import Elder
                from app.models.alert import Alert
                from app.models.user import User

                elder = Elder.query.get(elder_id)
                if not elder:
                    return

                caretaker = User.query.get(elder.caretaker_id)
                if not caretaker:
                    return

                today = date.today()
                window_24h = datetime.now() - timedelta(hours=24)

                # Count missed doses in last 24h
                missed_24h = AdherenceRecord.query.filter(
                    AdherenceRecord.elder_id == elder_id,
                    AdherenceRecord.status == 'missed',
                    AdherenceRecord.scheduled_datetime >= window_24h
                ).count()

                # Count consecutive days with at least one missed dose
                consecutive_days = EscalationService._count_consecutive_missed_days(elder_id)

                # Determine escalation level
                if consecutive_days >= 3:
                    level = 3
                    severity = 'critical'
                elif missed_24h >= 3:
                    level = 2
                    severity = 'high'
                elif missed_24h >= 1:
                    level = 1
                    severity = 'medium'
                else:
                    return

                # Deduplicate: don't create same-level alert twice today
                existing = Alert.query.filter(
                    Alert.elder_id == elder_id,
                    Alert.alert_type == 'missed_dose',
                    Alert.severity == severity,
                    Alert.is_read == False,
                    Alert.sent_at >= datetime.combine(today, __import__('datetime').time.min)
                ).first()

                if not existing:
                    msg = EscalationService._build_message(elder.name, missed_24h,
                                                            consecutive_days, level)
                    alert = Alert(
                        elder_id=elder_id,
                        caretaker_id=elder.caretaker_id,
                        alert_type='missed_dose',
                        message=msg,
                        severity=severity,
                    )
                    db.session.add(alert)
                    db.session.commit()
                    logger.info(f"Escalation L{level} alert created for {elder.name}")

                # Email for Level 2+
                if level >= 2 and caretaker.email:
                    EscalationService._send_email(app, caretaker.email,
                                                   elder.name, missed_24h,
                                                   consecutive_days, level)

                # SMS log for Level 3
                if level == 3 and caretaker.phone:
                    EscalationService._log_sms(caretaker.phone, elder.name,
                                                missed_24h, consecutive_days)

            except Exception as e:
                logger.error(f"EscalationService.escalate error: {e}")

    @staticmethod
    def _count_consecutive_missed_days(elder_id: int) -> int:
        """Count how many consecutive calendar days had at least one missed dose."""
        from app.models.adherence import AdherenceRecord
        count = 0
        for i in range(30):
            day = date.today() - timedelta(days=i)
            missed = AdherenceRecord.query.filter(
                AdherenceRecord.elder_id == elder_id,
                AdherenceRecord.status == 'missed',
                AdherenceRecord.scheduled_datetime >= datetime.combine(day, __import__('datetime').time.min),
                AdherenceRecord.scheduled_datetime <= datetime.combine(day, __import__('datetime').time.max)
            ).count()
            if missed > 0:
                count += 1
            else:
                break
        return count

    @staticmethod
    def _build_message(elder_name, missed_24h, consecutive_days, level):
        prefix = {1: '', 2: '⚠️ ', 3: '🚨 CRITICAL: '}[level]
        msg = (
            f"{prefix}Medication Alert: {elder_name} has missed "
            f"{missed_24h} dose(s) in the last 24 hours."
        )
        if consecutive_days >= 3:
            msg += f" Non-adherence detected for {consecutive_days} consecutive days."
        msg += " Status: Not Confirmed. Please follow up immediately."
        return msg

    @staticmethod
    def _send_email(app, to_email, elder_name, missed_24h, consecutive_days, level):
        """Send email alert to caretaker using raw SMTP."""
        try:
            from app.services.email_service import _send as smtp_send

            subject_map = {
                2: f"⚠️ Medication Alert — {elder_name}",
                3: f"🚨 CRITICAL: Repeated Missed Doses — {elder_name}",
            }
            subject = subject_map.get(level, f"Medication Alert — {elder_name}")

            body = f"""Dear Caretaker,

This is an automated alert from the Elderly Healthcare System.

Patient                    : {elder_name}
Status                     : Medication NOT CONFIRMED ❌
Missed doses (last 24h)    : {missed_24h}
Consecutive non-adherent days: {consecutive_days}

{'🚨 CRITICAL: Patient has missed medication for multiple days. Please check immediately.' if level == 3 else 'Please contact the patient immediately to ensure their medication is taken.'}

Action Required:
  1. Call or visit the patient
  2. Ensure medication is taken
  3. Contact doctor if needed

---
AI-Powered Elderly Healthcare System (Automated Alert)
"""
            with app.app_context():
                result = smtp_send(to_email, subject, body)
                if result:
                    logger.info(f"Escalation email sent to {to_email} for {elder_name}")
                else:
                    logger.warning(f"Escalation email failed for {to_email} — SMTP not configured")
        except Exception as e:
            logger.warning(f"Escalation email error: {e}")

    @staticmethod
    def _log_sms(phone, elder_name, missed_24h, consecutive_days):
        """Log SMS alert (actual sending requires Twilio/MSG91 configuration)."""
        sms_text = (
            f"URGENT: {elder_name} has missed medication for {consecutive_days} "
            f"consecutive days ({missed_24h} doses in 24h). Immediate attention required."
        )
        logger.warning(f"SMS ALERT to {phone}: {sms_text}")
        # To enable real SMS: configure Twilio in .env and call Twilio API here
        # from twilio.rest import Client
        # client = Client(account_sid, auth_token)
        # client.messages.create(to=phone, from_=twilio_number, body=sms_text)
