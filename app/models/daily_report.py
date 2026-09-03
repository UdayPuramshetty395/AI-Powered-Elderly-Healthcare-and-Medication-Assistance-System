"""daily_reports — stores generated daily reports persistently."""
from datetime import datetime, date
from app import db


class DailyReport(db.Model):
    __tablename__ = 'daily_reports'

    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    report_date   = db.Column(db.Date, nullable=False, index=True)
    caretaker_id  = db.Column(db.Integer, db.ForeignKey('users.id'),
                               nullable=False, index=True)
    elder_id      = db.Column(db.Integer, db.ForeignKey('elders.id'),
                               nullable=True)

    total_scheduled   = db.Column(db.Integer, default=0)
    total_taken       = db.Column(db.Integer, default=0)
    total_taken_late  = db.Column(db.Integer, default=0)
    total_missed      = db.Column(db.Integer, default=0)
    total_reminders   = db.Column(db.Integer, default=0)
    adherence_percent = db.Column(db.Float, default=0.0)

    email_sent    = db.Column(db.Boolean, default=False)
    email_sent_at = db.Column(db.DateTime, nullable=True)
    notes         = db.Column(db.Text, nullable=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id':                self.id,
            'report_date':       self.report_date.isoformat() if self.report_date else None,
            'caretaker_id':      self.caretaker_id,
            'elder_id':          self.elder_id,
            'total_scheduled':   self.total_scheduled,
            'total_taken':       self.total_taken,
            'total_taken_late':  self.total_taken_late,
            'total_missed':      self.total_missed,
            'total_reminders':   self.total_reminders,
            'adherence_percent': self.adherence_percent,
            'email_sent':        self.email_sent,
        }
