"""reminder_logs — stores every individual reminder that was fired."""
from datetime import datetime
from app import db


class ReminderLog(db.Model):
    __tablename__ = 'reminder_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('medicine_schedules.id'),
                            nullable=False, index=True)
    elder_id    = db.Column(db.Integer, db.ForeignKey('elders.id'),
                            nullable=False, index=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id'),
                            nullable=True)
    reminder_num    = db.Column(db.Integer, nullable=False)   # 1-6
    time_of_day     = db.Column(db.String(20), nullable=True) # morning/afternoon/night
    lang            = db.Column(db.String(5), nullable=True, default='te')
    text_te         = db.Column(db.Text, nullable=True)
    text_en         = db.Column(db.Text, nullable=True)
    fired_at        = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    acknowledged_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(
        db.Enum(
            'fired',
            'acknowledged',
            'missed',
            name='reminder_log_status_enum'
        ),
        nullable=False,
        default='fired'
    )

    def to_dict(self):
        return {
            'id':            self.id,
            'schedule_id':   self.schedule_id,
            'elder_id':      self.elder_id,
            'reminder_num':  self.reminder_num,
            'time_of_day':   self.time_of_day,
            'lang':          self.lang,
            'fired_at':      self.fired_at.isoformat() if self.fired_at else None,
            'status':        self.status,
        }
