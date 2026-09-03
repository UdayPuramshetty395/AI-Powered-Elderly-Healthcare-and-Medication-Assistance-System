import logging
from datetime import datetime
from app import db
from app.models.alert import Alert
from app.models.elder import Elder
from app.models.medicine import Medicine

logger = logging.getLogger(__name__)


class AlertService:
    """Handles creation and management of healthcare alerts."""

    @staticmethod
    def create_missed_dose_alert(elder_id: int, schedule_id: int,
                                  medicine_id: int, scheduled_time: str) -> Alert:
        """Create a missed dose alert for a caretaker."""
        elder = Elder.query.get(elder_id)
        if not elder:
            logger.error(f"Elder {elder_id} not found")
            return None

        medicine = Medicine.query.get(medicine_id)
        medicine_name = medicine.name if medicine else 'Unknown medication'
        dosage = medicine.dosage if medicine else ''

        alert = Alert(
            elder_id=elder_id,
            caretaker_id=elder.caretaker_id,
            alert_type='missed_dose',
            message=(
                f"⚠️ MISSED DOSE: {elder.name} has missed their "
                f"{medicine_name} {dosage} scheduled at {scheduled_time}. "
                f"Please follow up immediately."
            ),
            severity='high',
            related_medicine_id=medicine_id,
            related_schedule_id=schedule_id
        )

        db.session.add(alert)
        db.session.commit()
        logger.info(f"Missed dose alert created for elder {elder.name}")
        return alert

    @staticmethod
    def create_low_adherence_alert(elder_id: int, adherence_rate: float) -> Alert:
        """Create a low adherence alert."""
        elder = Elder.query.get(elder_id)
        if not elder:
            return None

        severity = 'critical' if adherence_rate < 40 else 'high'

        alert = Alert(
            elder_id=elder_id,
            caretaker_id=elder.caretaker_id,
            alert_type='low_adherence',
            message=(
                f"📉 LOW ADHERENCE: {elder.name}'s medication adherence rate is "
                f"{adherence_rate:.1f}% for the past 7 days. "
                f"Immediate attention required."
            ),
            severity=severity
        )

        db.session.add(alert)
        db.session.commit()
        logger.info(f"Low adherence alert created for {elder.name}: {adherence_rate:.1f}%")
        return alert

    @staticmethod
    def create_emergency_alert(elder_id: int, message: str) -> Alert:
        """Create an emergency alert."""
        elder = Elder.query.get(elder_id)
        if not elder:
            return None

        alert = Alert(
            elder_id=elder_id,
            caretaker_id=elder.caretaker_id,
            alert_type='emergency',
            message=f"🚨 EMERGENCY: {message}",
            severity='critical'
        )

        db.session.add(alert)
        db.session.commit()
        return alert

    @staticmethod
    def create_refill_alert(elder_id: int, medicine_id: int, medicine_name: str) -> Alert:
        """Create a medication refill needed alert."""
        elder = Elder.query.get(elder_id)
        if not elder:
            return None

        alert = Alert(
            elder_id=elder_id,
            caretaker_id=elder.caretaker_id,
            alert_type='refill_needed',
            message=f"💊 REFILL NEEDED: {medicine_name} prescription for {elder.name} needs to be refilled soon.",
            severity='medium',
            related_medicine_id=medicine_id
        )

        db.session.add(alert)
        db.session.commit()
        return alert

    @staticmethod
    def get_unread_count(caretaker_id: int) -> int:
        """Get count of unread alerts for a caretaker."""
        return Alert.query.filter_by(caretaker_id=caretaker_id, is_read=False).count()

    @staticmethod
    def dismiss_schedule_alerts(elder_id: int, schedule_id: int) -> int:
        """Dismiss all open alerts for a specific schedule (when dose is taken)."""
        updated = Alert.query.filter_by(
            elder_id=elder_id,
            related_schedule_id=schedule_id,
            is_read=False
        ).update({
            'is_read': True,
            'read_at': datetime.utcnow()
        })
        db.session.commit()
        return updated

    @staticmethod
    def send_email_alert(alert: Alert, recipient_email: str) -> bool:
        """Send email notification for critical alerts."""
        try:
            from flask import current_app
            from flask_mail import Message
            from app import mail

            if not recipient_email:
                return False

            msg = Message(
                subject=f"[Healthcare Alert] {alert.alert_type.replace('_', ' ').title()} - {alert.elder.name if alert.elder else 'Patient'}",
                recipients=[recipient_email],
                body=alert.message
            )
            mail.send(msg)
            logger.info(f"Email alert sent to {recipient_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
