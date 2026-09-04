from datetime import datetime
from app import db


class AdherenceRecord(db.Model):
    """Medication adherence tracking model."""
    __tablename__ = 'adherence_records'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('medicine_schedules.id'), nullable=False, index=True)
    elder_id = db.Column(db.Integer, db.ForeignKey('elders.id'), nullable=False, index=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id'), nullable=False, index=True)
    scheduled_datetime = db.Column(db.DateTime, nullable=False, index=True)
    taken_datetime = db.Column(db.DateTime, nullable=True)
    status = db.Column(
        db.Enum(
            'taken',
            'taken_late',
            'missed',
            'skipped',
            'pending',
            name='adherence_status_enum'
        ),
        nullable=False,
        default='pending'
    )
    notes = db.Column(db.Text, nullable=True)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'schedule_id': self.schedule_id,
            'elder_id': self.elder_id,
            'elder_name': self.elder.name if self.elder else None,
            'medicine_id': self.medicine_id,
            'medicine_name': self.medicine.name if self.medicine else None,
            'medicine_dosage': self.medicine.dosage if self.medicine else None,
            'scheduled_datetime': self.scheduled_datetime.isoformat() if self.scheduled_datetime else None,
            'taken_datetime': self.taken_datetime.isoformat() if self.taken_datetime else None,
            'status': self.status,
            'notes': self.notes,
            'recorded_by': self.recorded_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<AdherenceRecord {self.id} - {self.status}>'

    def to_dict(self):
        return {
            'id': self.id,
            'schedule_id': self.schedule_id,
            'elder_id': self.elder_id,
            'elder_name': self.elder.name if self.elder else None,
            'medicine_id': self.medicine_id,
            'medicine_name': self.medicine.name if self.medicine else None,
            'medicine_dosage': self.medicine.dosage if self.medicine else None,
            'scheduled_datetime': self.scheduled_datetime.isoformat() if self.scheduled_datetime else None,
            'taken_datetime': self.taken_datetime.isoformat() if self.taken_datetime else None,
            'status': self.status,
            'notes': self.notes,
            'recorded_by': self.recorded_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<AdherenceRecord {self.id} - {self.status}>'
