"""
Reminder state model — persists escalation level and snooze count
per dose occasion so page reloads don't reset state.
"""
from datetime import datetime
from app import db


class ReminderState(db.Model):
    """Tracks the current escalation state for each active dose occasion."""
    __tablename__ = 'reminder_states'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('medicine_schedules.id'),
                            nullable=False, index=True)
    elder_id = db.Column(db.Integer, db.ForeignKey('elders.id'),
                         nullable=False, index=True)
    dose_date = db.Column(db.Date, nullable=False, index=True)

    # 1 = gentle, 2 = stricter, 3 = critical
    reminder_level = db.Column(db.Integer, nullable=False, default=1)
    snooze_count = db.Column(db.Integer, nullable=False, default=0)

    # When the next reminder should fire (used for snooze scheduling)
    next_reminder_at = db.Column(db.DateTime, nullable=True)

    # resolved = taken/missed, active = awaiting confirmation
    status = db.Column(db.Enum('active', 'snoozed', 'resolved'),
                       nullable=False, default='active')

    last_reminded_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    schedule = db.relationship('MedicineSchedule', backref='reminder_states',
                               foreign_keys=[schedule_id], lazy=True)
    elder = db.relationship('Elder', backref='reminder_states',
                            foreign_keys=[elder_id], lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'schedule_id': self.schedule_id,
            'elder_id': self.elder_id,
            'dose_date': self.dose_date.isoformat() if self.dose_date else None,
            'reminder_level': self.reminder_level,
            'snooze_count': self.snooze_count,
            'next_reminder_at': self.next_reminder_at.isoformat() if self.next_reminder_at else None,
            'status': self.status,
            'last_reminded_at': self.last_reminded_at.isoformat() if self.last_reminded_at else None,
        }

    def __repr__(self):
        return f'<ReminderState schedule={self.schedule_id} level={self.reminder_level}>'
