"""
ML Service — Non-Adherence Prediction
======================================
Uses scikit-learn RandomForestClassifier when available.
Falls back to rule-based scoring when sklearn is not installed.

Generates:
  - Risk Score (0-100): probability of missing next dose
  - Adherence Score (0-100): actual rolling 30-day adherence
  - Behavior patterns: most-missed time slots, medicines, trends
"""
import logging
from datetime import datetime, timedelta, date

logger = logging.getLogger(__name__)

# Try importing sklearn — graceful fallback if not installed
try:
    from sklearn.ensemble import RandomForestClassifier
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.info("scikit-learn not available — using rule-based ML fallback")

# In-memory model cache (elder_id → model)
_model_cache = {}
_last_trained = {}


# ── Public API ────────────────────────────────────────────────────────────────

def get_risk_score(elder_id: int) -> dict:
    """
    Returns Risk_Score (0-100) for the elder's next scheduled dose.
    Cold start: < 10 records → return 50.
    """
    records = _load_records(elder_id)
    adherence_score = _compute_adherence_score(records)

    if len(records) == 0:
        return {
            'risk_score': 50,
            'adherence_score': 0,
            'confidence': 'none',
            'reason': 'No historical data'
        }

    if len(records) < 10:
        return {
            'risk_score': 50,
            'adherence_score': adherence_score,
            'confidence': 'low',
            'reason': f'Only {len(records)} records — need 10+ for prediction'
        }

    if SKLEARN_AVAILABLE:
        score = _sklearn_predict(elder_id, records)
    else:
        score = _rule_based_predict(records)

    return {
        'risk_score': score,
        'adherence_score': adherence_score,
        'confidence': 'high' if len(records) >= 30 else 'medium',
        'reason': 'ML model' if SKLEARN_AVAILABLE else 'Rule-based prediction'
    }


def get_behavior_patterns(elder_id: int) -> dict:
    """Returns behavioral analysis for an elder."""
    records = _load_records(elder_id)
    if not records:
        return {'error': 'No data available'}

    # Most-missed time slots (top 3 hours)
    missed_by_hour = {}
    for r in records:
        if r['status'] == 'missed':
            h = r['hour']
            missed_by_hour[h] = missed_by_hour.get(h, 0) + 1

    top_missed_hours = sorted(missed_by_hour.items(),
                               key=lambda x: x[1], reverse=True)[:3]

    # Most-missed medicine
    missed_by_med = {}
    for r in records:
        if r['status'] == 'missed':
            m = r['medicine_name']
            missed_by_med[m] = missed_by_med.get(m, 0) + 1
    most_missed_medicine = max(missed_by_med, key=missed_by_med.get) if missed_by_med else None

    # Average delay for late taken records
    delays = []
    for r in records:
        if r['status'] == 'taken' and r.get('delay_minutes'):
            delays.append(r['delay_minutes'])
    avg_delay = round(sum(delays) / len(delays), 1) if delays else 0

    # 7-day trend
    trend = _compute_trend(records)

    return {
        'top_missed_time_slots': [
            {'hour': h, 'label': f"{h:02d}:00", 'miss_count': c}
            for h, c in top_missed_hours
        ],
        'most_missed_medicine': most_missed_medicine,
        'average_delay_minutes': avg_delay,
        'trend_7day': trend,  # 'improving', 'stable', 'declining'
        'total_records_analysed': len(records),
    }


def get_adherence_analytics(elder_id: int) -> dict:
    """Returns daily/weekly/monthly adherence percentages."""
    from app.models.adherence import AdherenceRecord

    today = date.today()

    def _rate(days):
        since = datetime.combine(today - timedelta(days=days), __import__('datetime').time.min)
        rows = AdherenceRecord.query.filter(
            AdherenceRecord.elder_id == elder_id,
            AdherenceRecord.scheduled_datetime >= since
        ).all()
        total = len(rows)
        taken = sum(1 for r in rows if r.status == 'taken')
        missed = sum(1 for r in rows if r.status == 'missed')
        skipped = sum(1 for r in rows if r.status == 'skipped')
        late = sum(1 for r in rows
                   if r.status == 'taken' and r.taken_datetime and
                   (r.taken_datetime - r.scheduled_datetime).total_seconds() > 1800)
        return {
            'total': total,
            'taken': taken,
            'missed': missed,
            'skipped': skipped,
            'late': late,
            'rate': round(taken / total * 100, 1) if total > 0 else 0
        }

    # Daily chart data (last 30 days)
    daily_chart = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        since = datetime.combine(d, __import__('datetime').time.min)
        until = datetime.combine(d, __import__('datetime').time.max)
        rows = AdherenceRecord.query.filter(
            AdherenceRecord.elder_id == elder_id,
            AdherenceRecord.scheduled_datetime >= since,
            AdherenceRecord.scheduled_datetime <= until
        ).all()
        t = len(rows)
        tk = sum(1 for r in rows if r.status == 'taken')
        daily_chart.append({
            'date': d.isoformat(),
            'day': d.strftime('%d %b'),
            'taken': tk,
            'missed': sum(1 for r in rows if r.status == 'missed'),
            'total': t,
            'rate': round(tk / t * 100, 1) if t > 0 else 0
        })

    # Missed medicine analysis (last 30 days)
    since_30 = datetime.combine(today - timedelta(days=30), __import__('datetime').time.min)
    missed_rows = AdherenceRecord.query.filter(
        AdherenceRecord.elder_id == elder_id,
        AdherenceRecord.status == 'missed',
        AdherenceRecord.scheduled_datetime >= since_30
    ).all()

    missed_by_med = {}
    for r in missed_rows:
        name = r.medicine.name if r.medicine else 'Unknown'
        missed_by_med[name] = missed_by_med.get(name, 0) + 1

    missed_analysis = sorted(
        [{'medicine': k, 'count': v} for k, v in missed_by_med.items()],
        key=lambda x: x['count'], reverse=True
    )

    return {
        'daily': _rate(1),
        'weekly': _rate(7),
        'monthly': _rate(30),
        'daily_chart': daily_chart,
        'missed_analysis': missed_analysis,
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_records(elder_id: int) -> list:
    """Load AdherenceRecords for an elder as feature dicts."""
    from app.models.adherence import AdherenceRecord
    rows = AdherenceRecord.query.filter(
        AdherenceRecord.elder_id == elder_id,
        AdherenceRecord.scheduled_datetime >= datetime.now() - timedelta(days=90)
    ).order_by(AdherenceRecord.scheduled_datetime.asc()).all()

    result = []
    for r in rows:
        delay = None
        if r.status == 'taken' and r.taken_datetime:
            delay = (r.taken_datetime - r.scheduled_datetime).total_seconds() / 60
        result.append({
            'status': r.status,
            'hour': r.scheduled_datetime.hour,
            'dow': r.scheduled_datetime.weekday(),  # 0=Mon
            'medicine_name': r.medicine.name if r.medicine else 'unknown',
            'medicine_id': r.medicine_id,
            'date': r.scheduled_datetime.date(),
            'delay_minutes': delay,
            'missed': 1 if r.status == 'missed' else 0,
        })
    return result


def _compute_adherence_score(records: list) -> int:
    """30-day rolling adherence percentage as integer 0-100."""
    cutoff = date.today() - timedelta(days=30)
    recent = [r for r in records if r['date'] >= cutoff]
    if not recent:
        return 0
    taken = sum(1 for r in recent if r['status'] == 'taken')
    return round(taken / len(recent) * 100)


def _compute_trend(records: list) -> str:
    """Compare last-7-day adherence to prior-7-day adherence."""
    today = date.today()
    last7 = [r for r in records if today - timedelta(days=7) <= r['date'] <= today]
    prev7 = [r for r in records
              if today - timedelta(days=14) <= r['date'] < today - timedelta(days=7)]

    def rate(lst):
        if not lst:
            return 0
        return sum(1 for r in lst if r['status'] == 'taken') / len(lst)

    r1, r2 = rate(last7), rate(prev7)
    if r1 > r2 + 0.05:
        return 'improving'
    if r1 < r2 - 0.05:
        return 'declining'
    return 'stable'


def _rule_based_predict(records: list) -> int:
    """Simple rule-based risk score when sklearn not available."""
    if not records:
        return 50

    total = len(records)
    missed = sum(r['missed'] for r in records)
    miss_rate = missed / total

    # Weight recent records more heavily
    recent = records[-10:]
    recent_missed = sum(r['missed'] for r in recent)
    recent_rate = recent_missed / len(recent)

    # Combine: 40% historical + 60% recent
    score = (miss_rate * 40) + (recent_rate * 60)
    return min(100, max(0, round(score * 100)))


def _sklearn_predict(elder_id: int, records: list) -> int:
    """Train/use a RandomForest model for risk prediction."""
    global _model_cache, _last_trained

    # Re-train every 24h or if no model exists
    needs_train = (
        elder_id not in _model_cache or
        elder_id not in _last_trained or
        (datetime.now() - _last_trained[elder_id]).total_seconds() > 86400
    )

    if needs_train and len(records) >= 10:
        X = [[
    r['hour'],
    r['dow'],
    r['medicine_id'] or 0
] for r in records]
        y = [r['missed'] for r in records]
        try:
            clf = RandomForestClassifier(n_estimators=50, random_state=42)
            clf.fit(np.array(X), np.array(y))
            _model_cache[elder_id] = clf
            _last_trained[elder_id] = datetime.now()
        except Exception as e:
            logger.error(f"sklearn training failed: {e}")
            return _rule_based_predict(records)

    clf = _model_cache.get(elder_id)
    if clf is None:
        return _rule_based_predict(records)

    # Predict for the next upcoming scheduled hour
    now = datetime.now()
    X_pred = np.array([[now.hour, now.weekday(), 0]])
    try:
        proba = clf.predict_proba(X_pred)[0]
        # proba[1] = probability of missed
        miss_prob = proba[1] if len(proba) > 1 else proba[0]
        return min(100, max(0, round(miss_prob * 100)))
    except Exception as e:
        logger.error(f"sklearn predict failed: {e}")
        return _rule_based_predict(records)
