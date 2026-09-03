"""
Daily Reports API
=================
GET  /api/reports/latest          — latest report per elder for current caretaker
GET  /api/reports/history         — paginated report history
GET  /api/reports/<id>            — single report detail
POST /api/reports/generate-now    — generate + email report right now (demo button)
GET  /api/reports/elder/<elder_id> — all reports for one elder
"""
import threading
from html import escape
from datetime import datetime, date, timedelta, time as time_obj
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.user import User
from app.models.elder import Elder
from app.models.adherence import AdherenceRecord
from app.models.daily_report import DailyReport
from app.models.reminder_log import ReminderLog

reports_bp = Blueprint('reports', __name__)


def _get_user():
    return User.query.get(int(get_jwt_identity()))


def _get_elder_ids(user):
    if user.role == 'admin':
        return [e.id for e in Elder.query.filter_by(is_active=True).all()]
    return [e.id for e in Elder.query.filter_by(caretaker_id=user.id, is_active=True).all()]


def _build_report_for_elder(elder, caretaker_id, report_date):
    """
    Build/update a DailyReport record for one elder on one date.
    Returns (DailyReport object, medicine_details list).
    """
    dt_from = datetime.combine(report_date, time_obj.min)
    dt_to   = datetime.combine(report_date, time_obj.max)

    records = AdherenceRecord.query.filter(
        AdherenceRecord.elder_id == elder.id,
        AdherenceRecord.scheduled_datetime >= dt_from,
        AdherenceRecord.scheduled_datetime <= dt_to
    ).all()

    total      = len(records)
    taken      = sum(1 for r in records if r.status == 'taken')
    taken_late = sum(1 for r in records if r.status == 'taken_late')
    missed     = sum(1 for r in records if r.status == 'missed')
    adherence  = round((taken + taken_late) / total * 100, 1) if total > 0 else 0.0

    try:
        reminders = ReminderLog.query.filter(
            ReminderLog.elder_id == elder.id,
            ReminderLog.fired_at >= dt_from,
            ReminderLog.fired_at <= dt_to
        ).count()
    except Exception:
        reminders = 0

    # Collect medicine details
    medicine_details = {}
    for record in records:
        med_id = record.medicine_id
        if med_id not in medicine_details:
            medicine_details[med_id] = {
                'name': record.medicine.name if record.medicine else 'Unknown',
                'dosage': record.medicine.dosage if record.medicine else 'N/A',
                'taken': 0,
                'taken_late': 0,
                'missed': 0,
                'total': 0
            }
        medicine_details[med_id]['total'] += 1
        if record.status == 'taken':
            medicine_details[med_id]['taken'] += 1
        elif record.status == 'taken_late':
            medicine_details[med_id]['taken_late'] += 1
        elif record.status == 'missed':
            medicine_details[med_id]['missed'] += 1

    # Upsert
    report = DailyReport.query.filter_by(
        elder_id=elder.id,
        caretaker_id=caretaker_id,
        report_date=report_date
    ).first()

    if not report:
        report = DailyReport(
            elder_id=elder.id,
            caretaker_id=caretaker_id,
            report_date=report_date
        )
        db.session.add(report)

    report.total_scheduled  = total
    report.total_taken       = taken
    report.total_taken_late  = taken_late
    report.total_missed      = missed
    report.total_reminders   = reminders
    report.adherence_percent = adherence

    return report, list(medicine_details.values())


def _format_email_body(elder_name: str, report_date: date,
                        total: int, taken: int, taken_late: int,
                        missed: int, reminders: int, adherence: float,
                        medicine_details: list = None) -> tuple:
    """Build a clean HTML daily report for email delivery."""
    date_str = report_date.strftime('%d-%b-%Y')
    subject = f"Daily Health Report — {elder_name} — {date_str}"

    adherence_status = "Excellent adherence" if adherence >= 80 else (
        "Needs attention" if adherence >= 60 else "Critical follow-up required"
    )
    adherence_color = '#2e7d32' if adherence >= 80 else ('#e65100' if adherence >= 60 else '#c62828')
    adherence_badge = f'<span style="display:inline-block;padding:4px 10px;border-radius:999px;background:{adherence_color};color:#fff;font-size:12px;font-weight:700">{adherence_status}</span>'

    summary_rows = [
        ('Total Scheduled Doses', str(total)),
        ('Taken On Time', str(taken)),
        ('Taken Late', str(taken_late)),
        ('Missed', str(missed)),
        ('Voice Reminders', str(reminders)),
    ]

    summary_table_rows = ''.join(
        f'<tr><td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;color:#64748b">{escape(label)}</td>'
        f'<td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;font-weight:700;color:#0f172a">{escape(value)}</td></tr>'
        for label, value in summary_rows
    )

    if medicine_details:
        medicine_rows = ''.join(
            f'<tr><td style="padding:10px 12px;border-bottom:1px solid #e2e8f0">{escape(str(med.get("name", "Unknown")))}</td>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #e2e8f0">{escape(str(med.get("dosage", "N/A")))}</td>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #e2e8f0">{escape(str(med.get("taken", 0)))}</td>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #e2e8f0">{escape(str(med.get("taken_late", 0)))}</td>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #e2e8f0">{escape(str(med.get("missed", 0)))}</td>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #e2e8f0">{escape("✅" if med.get("missed", 0) == 0 else "⚠️")}</td></tr>'
            for med in medicine_details
        )
    else:
        medicine_rows = '<tr><td colspan="6" style="padding:12px;color:#64748b">No medication entries were recorded for this day.</td></tr>'

    body = f"""
    <div style="font-family:Segoe UI, Arial, sans-serif;color:#0f172a;line-height:1.5;max-width:680px;margin:0 auto;">
      <div style="font-size:24px;font-weight:700;margin-bottom:6px;">Daily Health Report</div>
      <div style="font-size:14px;color:#64748b;margin-bottom:18px;">Patient: {escape(elder_name)} · Date: {escape(date_str)} · Generated: {escape(datetime.now().strftime('%d-%b-%Y at %I:%M %p'))}</div>

      <div style="border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;margin-bottom:20px;">
        <div style="background:#2563eb;color:#fff;padding:12px 16px;font-weight:700;">Medication Summary</div>
        <table style="width:100%;border-collapse:collapse;background:#fff;">
          <tbody>
            {summary_table_rows}
          </tbody>
        </table>
      </div>

      <div style="border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;margin-bottom:20px;">
        <div style="background:#f8fafc;padding:12px 16px;font-weight:700;color:#334155;">Performance Metrics</div>
        <div style="padding:16px;background:#fff;">
          <div style="font-size:16px;font-weight:700;margin-bottom:8px;">Overall Adherence: <span style="color:{adherence_color}">{adherence}%</span></div>
          <div>{adherence_badge}</div>
        </div>
      </div>

      <div style="border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;">
        <div style="background:#f8fafc;padding:12px 16px;font-weight:700;color:#334155;">Detailed Medication Breakdown</div>
        <table style="width:100%;border-collapse:collapse;background:#fff;">
          <thead>
            <tr style="background:#f8fafc;color:#64748b;text-align:left;">
              <th style="padding:10px 12px;font-size:12px;text-transform:uppercase;letter-spacing:0.04em;">Medicine</th>
              <th style="padding:10px 12px;font-size:12px;text-transform:uppercase;letter-spacing:0.04em;">Dose</th>
              <th style="padding:10px 12px;font-size:12px;text-transform:uppercase;letter-spacing:0.04em;">Taken</th>
              <th style="padding:10px 12px;font-size:12px;text-transform:uppercase;letter-spacing:0.04em;">Late</th>
              <th style="padding:10px 12px;font-size:12px;text-transform:uppercase;letter-spacing:0.04em;">Missed</th>
              <th style="padding:10px 12px;font-size:12px;text-transform:uppercase;letter-spacing:0.04em;">Status</th>
            </tr>
          </thead>
          <tbody>
            {medicine_rows}
          </tbody>
        </table>
      </div>

      <div style="margin-top:20px;padding:14px 16px;border-radius:10px;background:#eff6ff;color:#1d4ed8;font-size:13px;">
        Review any missed doses, reinforce the schedule, and monitor the next 24 hours for consistency.
      </div>

      <div style="margin-top:20px;font-size:12px;color:#64748b;">
        System Generated Report<br>
        AI-Powered Elderly Healthcare and Medication Assistance System<br>
        Report generated automatically at {escape(datetime.now().strftime('%d %B %Y, %I:%M %p'))}
      </div>
    </div>
    """
    return subject, body


# ── Endpoints ─────────────────────────────────────────────────────────────────

@reports_bp.route('/latest', methods=['GET'])
@jwt_required()
def get_latest_reports():
    """Get the latest daily report for each elder managed by this caretaker."""
    user = _get_user()
    elder_ids = _get_elder_ids(user)
    if not elder_ids:
        return jsonify({'reports': []}), 200

    reports = []
    for eid in elder_ids:
        report = DailyReport.query.filter_by(
            elder_id=eid, caretaker_id=user.id if user.role != 'admin' else None
        ).order_by(DailyReport.report_date.desc()).first()

        if not report:
            # Try any caretaker's report for this elder
            report = DailyReport.query.filter_by(
                elder_id=eid
            ).order_by(DailyReport.report_date.desc()).first()

        if report:
            elder = Elder.query.get(eid)
            d = report.to_dict()
            d['elder_name'] = elder.name if elder else '—'
            reports.append(d)

    return jsonify({'reports': reports}), 200


@reports_bp.route('/history', methods=['GET'])
@jwt_required()
def get_report_history():
    """Get paginated report history."""
    user     = _get_user()
    page     = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    elder_id = request.args.get('elder_id', type=int)

    query = DailyReport.query
    if user.role != 'admin':
        query = query.filter_by(caretaker_id=user.id)
    if elder_id:
        query = query.filter_by(elder_id=elder_id)

    paginated = query.order_by(DailyReport.report_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    items = []
    for r in paginated.items:
        d = r.to_dict()
        elder = Elder.query.get(r.elder_id) if r.elder_id else None
        d['elder_name'] = elder.name if elder else '—'
        items.append(d)

    return jsonify({
        'reports': items,
        'total':   paginated.total,
        'pages':   paginated.pages,
        'page':    paginated.page
    }), 200


@reports_bp.route('/<int:report_id>', methods=['GET'])
@jwt_required()
def get_report(report_id):
    """Get a single report by ID."""
    user = _get_user()
    report = DailyReport.query.get_or_404(report_id)

    if user.role != 'admin' and report.caretaker_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    elder = Elder.query.get(report.elder_id) if report.elder_id else None
    d = report.to_dict()
    d['elder_name'] = elder.name if elder else '—'
    return jsonify({'report': d}), 200


@reports_bp.route('/elder/<int:elder_id>', methods=['GET'])
@jwt_required()
def get_elder_reports(elder_id):
    """Get all reports for a specific elder."""
    user = _get_user()
    elder = Elder.query.get_or_404(elder_id)

    if user.role != 'admin' and elder.caretaker_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    reports = DailyReport.query.filter_by(elder_id=elder_id)\
        .order_by(DailyReport.report_date.desc()).limit(30).all()

    items = []
    for r in reports:
        d = r.to_dict()
        d['elder_name'] = elder.name
        items.append(d)

    return jsonify({'reports': items, 'elder_name': elder.name}), 200


@reports_bp.route('/generate-now', methods=['POST'])
@jwt_required()
def generate_now():
    """
    Generate and email today's report immediately.
    Used by the 'Send Report Now' dashboard button.
    """
    user = _get_user()
    data = request.get_json() or {}
    elder_id   = data.get('elder_id')
    report_date_str = data.get('date', date.today().isoformat())

    try:
        report_date = date.fromisoformat(report_date_str)
    except ValueError:
        report_date = date.today()

    if elder_id:
        elders = [Elder.query.get(elder_id)] if Elder.query.get(elder_id) else []
    else:
        if user.role == 'admin':
            elders = Elder.query.filter_by(is_active=True).all()
        else:
            elders = Elder.query.filter_by(caretaker_id=user.id, is_active=True).all()

    if not elders:
        return jsonify({'error': 'No elders found'}), 404

    caretaker = user
    generated = []

    for elder in elders:
        report, medicine_details = _build_report_for_elder(elder, caretaker.id, report_date)
        db.session.flush()

        subject, body = _format_email_body(
            elder_name=elder.name,
            report_date=report_date,
            total=report.total_scheduled,
            taken=report.total_taken,
            taken_late=report.total_taken_late,
            missed=report.total_missed,
            reminders=report.total_reminders,
            adherence=report.adherence_percent,
            medicine_details=medicine_details
        )

        _app = current_app._get_current_object()

        def _send_email(app=_app, r=report, subj=subject, bdy=body,
                         ct=caretaker, report_date=report_date):
            with app.app_context():
                from app.services.email_service import _send
                sent = _send(ct.email, subj, bdy)
                if sent:
                    # Update email_sent flag
                    dr = DailyReport.query.get(r.id)
                    if dr:
                        dr.email_sent    = True
                        dr.email_sent_at = datetime.now()
                        db.session.commit()

        threading.Thread(target=_send_email, daemon=True).start()

        generated.append({
            'elder_name':       elder.name,
            'total_scheduled':  report.total_scheduled,
            'total_taken':      report.total_taken,
            'total_taken_late': report.total_taken_late,
            'total_missed':     report.total_missed,
            'adherence':        report.adherence_percent,
            'email_to':         caretaker.email
        })

    db.session.commit()

    return jsonify({
        'message': f'Report generated for {len(generated)} elder(s). Email sending.',
        'reports': generated
    }), 200
