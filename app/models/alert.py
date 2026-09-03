from datetime import datetime
from app import db


class Alert(db.Model):
    """Alert/notification model."""
    __tablename__ = 'alerts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    elder_id = db.Column(db.Integer, db.ForeignKey('elders.id'), nullable=False, index=True)
    caretaker_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    alert_type = db.Column(db.Enum('missed_dose', 'low_adherence', 'emergency', 
                                   'appointment', 'refill_needed', 'general'),
                          nullable=False, default='general')
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    severity = db.Column(db.Enum('low', 'medium', 'high', 'critical'), 
                        nullable=False, default='medium')
    related_medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id'), nullable=True)
    related_schedule_id = db.Column(db.Integer, db.ForeignKey('medicine_schedules.id'), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'elder_id': self.elder_id,
            'elder_name': self.elder.name if self.elder else None,
            'caretaker_id': self.caretaker_id,
            'alert_type': self.alert_type,
            'message': self.message,
            'is_read': self.is_read,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'severity': self.severity,
            'related_medicine_id': self.related_medicine_id,
            'related_schedule_id': self.related_schedule_id,
        }

    def __repr__(self):
        return f'<Alert {self.id} - {self.alert_type}>'
