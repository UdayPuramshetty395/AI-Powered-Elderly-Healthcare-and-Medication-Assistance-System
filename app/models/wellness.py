from datetime import datetime
from app import db


class WellnessCheck(db.Model):
    """Daily wellness check-in for elders."""
    __tablename__ = 'wellness_checks'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    elder_id = db.Column(db.Integer, db.ForeignKey('elders.id'), nullable=False, index=True)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Mood: 1=Very Sad, 2=Sad, 3=Neutral, 4=Happy, 5=Very Happy
    mood_score = db.Column(db.Integer, nullable=True)
    mood_label = db.Column(db.String(50), nullable=True)

    # Pain level: 0-10
    pain_level = db.Column(db.Integer, nullable=True)

    # Sleep quality: good, fair, poor
    sleep_quality = db.Column(db.String(20), nullable=True)

    # Appetite: good, fair, poor
    appetite = db.Column(db.String(20), nullable=True)

    # Notes / complaints
    notes = db.Column(db.Text, nullable=True)

    # Companion chat message if any
    companion_message = db.Column(db.Text, nullable=True)

    checked_at = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    # Relationships
    elder = db.relationship('Elder', backref=db.backref('wellness_checks', lazy=True),
                            foreign_keys=[elder_id])

    def to_dict(self):
        return {
            'id': self.id,
            'elder_id': self.elder_id,
            'elder_name': self.elder.name if self.elder else None,
            'recorded_by': self.recorded_by,
            'mood_score': self.mood_score,
            'mood_label': self.mood_label,
            'pain_level': self.pain_level,
            'sleep_quality': self.sleep_quality,
            'appetite': self.appetite,
            'notes': self.notes,
            'companion_message': self.companion_message,
            'checked_at': self.checked_at.isoformat() if self.checked_at else None,
        }

    def __repr__(self):
        return f'<WellnessCheck {self.id} - Elder {self.elder_id}>'
