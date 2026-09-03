"""
Email Service — Beautiful HTML emails + PDF reports.
Uses Gmail API (HTTPS) or SMTP fallback.
"""
import logging
import smtplib
import os
import tempfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

logger = logging.getLogger(__name__)

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOKEN_PATH = os.path.join(BASE_DIR, 'gmail_token.json')

_email_log: list = []


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_creds():
    try:
        from flask import current_app
        return (current_app.config.get('MAIL_USERNAME', ''),
                current_app.config.get('MAIL_PASSWORD', ''))
    except Exception:
        return (os.environ.get('MAIL_USERNAME', ''),
                os.environ.get('MAIL_PASSWORD', ''))


def _smtp_enabled() -> bool:
    try:
        from flask import current_app
        raw_value = current_app.config.get('MAIL_USE_SMTP', os.environ.get('MAIL_USE_SMTP', 'False'))
    except Exception:
        raw_value = os.environ.get('MAIL_USE_SMTP', 'False')

    if isinstance(raw_value, bool):
        return raw_value
    return str(raw_value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _html_base(title: str, color: str, icon: str, content: str) -> str:
    """Wrap content in a beautiful HTML email template."""
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#f0f4f8;margin:0;padding:0}}
  .wrap{{max-width:600px;margin:32px auto;background:#fff;border-radius:16px;
         box-shadow:0 4px 24px rgba(0,0,0,.10);overflow:hidden}}
  .header{{background:{color};padding:32px 28px;text-align:center;color:#fff}}
  .header .icon{{font-size:48px;margin-bottom:8px}}
  .header h1{{margin:0;font-size:24px;font-weight:700}}
  .header p{{margin:6px 0 0;opacity:.85;font-size:14px}}
  .body{{padding:28px}}
  .row{{display:flex;padding:10px 0;border-bottom:1px solid #f0f4f8}}
  .row:last-child{{border-bottom:none}}
  .label{{color:#64748b;font-size:13px;width:160px;flex-shrink:0;font-weight:600}}
  .value{{color:#1a202c;font-size:14px;font-weight:500}}
  .badge{{display:inline-block;padding:4px 14px;border-radius:20px;
          font-size:13px;font-weight:700}}
  .taken{{background:#e8f5e9;color:#2e7d32}}
  .missed{{background:#ffebee;color:#c62828}}
  .late{{background:#fff8e1;color:#e65100}}
  .section-title{{font-size:13px;font-weight:700;color:#64748b;
                  text-transform:uppercase;letter-spacing:.5px;
                  margin:20px 0 8px;padding-bottom:6px;
                  border-bottom:2px solid #e2e8f0}}
  .footer{{background:#f8fafc;padding:16px 28px;text-align:center;
           color:#94a3b8;font-size:12px;border-top:1px solid #e2e8f0}}
  .progress-bar{{height:10px;background:#e2e8f0;border-radius:6px;overflow:hidden;margin:8px 0}}
  .progress-fill{{height:100%;border-radius:6px}}
</style></head><body>
<div class="wrap">
  <div class="header">
    <div class="icon">{icon}</div>
    <h1>{title}</h1>
    <p>AI-Powered Elderly Healthcare System</p>
  </div>
  <div class="body">{content}</div>
  <div class="footer">
    🏥 AI-Powered Elderly Healthcare and Medication Assistance System<br>
    Generated: {datetime.now().strftime('%d %B %Y, %I:%M %p')}
  </div>
</div></body></html>"""


# ── PDF Generator ─────────────────────────────────────────────────────────────

def _generate_pdf(title: str, rows: list, summary: str = '') -> str:
    """Generate a styled PDF report. Returns temp file path."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                         Table, TableStyle, HRFlowable)
        from reportlab.lib.enums import TA_CENTER, TA_LEFT

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False,
                                          prefix='eldercare_') as f:
            path = f.name

        doc = SimpleDocTemplate(path, pagesize=A4,
                                  leftMargin=2*cm, rightMargin=2*cm,
                                  topMargin=2*cm, bottomMargin=2*cm)

        styles = getSampleStyleSheet()
        title_style  = ParagraphStyle('T', fontSize=18, fontName='Helvetica-Bold',
                                       textColor=colors.HexColor('#1565c0'),
                                       spaceAfter=6, alignment=TA_CENTER)
        sub_style    = ParagraphStyle('S', fontSize=10, textColor=colors.grey,
                                       spaceAfter=16, alignment=TA_CENTER)
        section_style= ParagraphStyle('SE', fontSize=11, fontName='Helvetica-Bold',
                                       textColor=colors.HexColor('#1565c0'),
                                       spaceBefore=14, spaceAfter=6)
        note_style   = ParagraphStyle('N', fontSize=10, textColor=colors.HexColor('#546e7a'),
                                       spaceAfter=4, leftIndent=4)

        story = [
            Paragraph('🏥 AI-Powered Elderly Healthcare System', title_style),
            Paragraph(title, ParagraphStyle('T2', fontSize=14,
                       fontName='Helvetica-Bold', spaceAfter=4, alignment=TA_CENTER)),
            Paragraph(f'Generated: {datetime.now().strftime("%d %B %Y, %I:%M %p")}', sub_style),
            HRFlowable(width='100%', thickness=2, color=colors.HexColor('#1565c0')),
            Spacer(1, 12),
        ]

        # Table
        if rows:
            table_data = [['Field', 'Value']]
            for label, value in rows:
                table_data.append([label, value])

            t = Table(table_data, colWidths=[6*cm, 11*cm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1565c0')),
                ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
                ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE',   (0, 0), (-1, 0), 11),
                ('ALIGN',      (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME',   (0, 1), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE',   (0, 1), (-1, -1), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1),
                 [colors.white, colors.HexColor('#f0f4f8')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('TOPPADDING',  (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ]))
            story.append(t)
            story.append(Spacer(1, 16))

        if summary:
            story.append(HRFlowable(width='100%', thickness=1,
                                     color=colors.HexColor('#e2e8f0')))
            story.append(Spacer(1, 8))
            story.append(Paragraph(summary, note_style))

        doc.build(story)
        return path
    except Exception as e:
        logger.error(f'PDF generation failed: {e}')
        return ''


# ── Email sender ──────────────────────────────────────────────────────────────

def _send_via_gmail_api(to: str, subject: str, html: str,
                         pdf_path: str = '') -> bool:
    if not os.path.exists(TOKEN_PATH):
        return False
    try:
        import base64
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from google.auth.transport.requests import Request

        creds = Credentials.from_authorized_user_file(TOKEN_PATH)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        service = build('gmail', 'v1', credentials=creds, cache_discovery=False)

        msg = MIMEMultipart('mixed')
        msg['To']      = to
        msg['Subject'] = subject
        alt = MIMEMultipart('alternative')
        alt.attach(MIMEText(html, 'html', 'utf-8'))
        msg.attach(alt)

        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as f:
                part = MIMEBase('application', 'pdf')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', 'attachment',
                                  filename=os.path.basename(pdf_path))
                msg.attach(part)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId='me', body={'raw': raw}).execute()
        logger.info(f'Gmail API → {to} | {subject}')
        return True
    except Exception as e:
        logger.warning(f'Gmail API failed: {e}')
        return False


def _send_via_smtp(to: str, subject: str, html: str,
                    pdf_path: str = '') -> bool:
    if not _smtp_enabled():
        return False

    user, pwd = _get_creds()
    if not user or not pwd:
        return False
    try:
        msg = MIMEMultipart('mixed')
        msg['From']    = user
        msg['To']      = to
        msg['Subject'] = subject
        alt = MIMEMultipart('alternative')
        alt.attach(MIMEText(html, 'html', 'utf-8'))
        msg.attach(alt)

        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as f:
                part = MIMEBase('application', 'pdf')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', 'attachment',
                                  filename=os.path.basename(pdf_path))
                msg.attach(part)

        with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as s:
            s.ehlo(); s.starttls(); s.login(user, pwd)
            s.sendmail(user, to, msg.as_string())
        logger.info(f'SMTP → {to} | {subject}')
        return True
    except Exception as e:
        logger.warning(f'SMTP failed: {e}')
        return False


def _send(to: str, subject: str, html: str, pdf_path: str = '') -> bool:
    if _send_via_gmail_api(to, subject, html, pdf_path):
        _log_email(to, subject, 'sent_api')
        return True
    if _smtp_enabled() and _send_via_smtp(to, subject, html, pdf_path):
        _log_email(to, subject, 'sent_smtp')
        return True
    _log_email(to, subject, 'network_blocked')
    logger.warning(f'All email methods failed — logged for demo: {subject}')
    return False


def _log_email(to, subject, status):
    _email_log.append({'to': to, 'subject': subject, 'status': status,
                        'sent_at': datetime.now().isoformat()})
    if len(_email_log) > 100:
        _email_log.pop(0)


def get_email_log():
    return list(reversed(_email_log))


def test_email_config() -> dict:
    """Return diagnostic status for Gmail API and SMTP email configuration."""
    results = {
        'gmail_api_token_path': TOKEN_PATH,
        'gmail_api_token_exists': os.path.exists(TOKEN_PATH),
        'gmail_api_available': False,
        'gmail_api_error': None,
        'smtp_enabled': _smtp_enabled(),
        'smtp_username_set': False,
        'smtp_login_ok': False,
        'smtp_error': None,
    }

    # Gmail API diagnostics
    if results['gmail_api_token_exists']:
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            creds = Credentials.from_authorized_user_file(TOKEN_PATH)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            results['gmail_api_available'] = creds.valid
            if not creds.valid:
                results['gmail_api_error'] = 'Gmail API credentials are invalid or expired.'
        except Exception as e:
            results['gmail_api_error'] = str(e)

    # SMTP diagnostics
    smtp_user, smtp_pass = _get_creds()
    results['smtp_username_set'] = bool(smtp_user and smtp_pass)
    if results['smtp_enabled'] and results['smtp_username_set']:
        try:
            with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_user, smtp_pass)
            results['smtp_login_ok'] = True
        except Exception as e:
            results['smtp_error'] = str(e)

    return results


# ── Public email functions ────────────────────────────────────────────────────

def send_dose_taken_email(caretaker_email, caretaker_name, elder_name,
                           medicine_name, dosage, taken_at, scheduled_time,
                           is_late=False):
    status  = 'TAKEN LATE' if is_late else 'TAKEN ON TIME'
    color   = '#e65100' if is_late else '#2e7d32'
    icon    = '🕐' if is_late else '✅'
    badge   = f'<span class="badge late">TAKEN LATE</span>' if is_late \
              else '<span class="badge taken">TAKEN ON TIME</span>'
    subject = f"{icon} Medicine {'Taken Late' if is_late else 'Taken'} — {elder_name}"

    content = f"""
    <p style="color:#546e7a;font-size:14px;margin-bottom:20px">
      Dear <strong>{caretaker_name}</strong>,<br>
      This is an automated confirmation for <strong>{elder_name}</strong>.
    </p>
    <div class="section-title">Patient Information</div>
    <div class="row"><span class="label">Patient Name</span>
      <span class="value"><strong>{elder_name}</strong></span></div>
    <div class="row"><span class="label">Status</span>
      <span class="value">{badge}</span></div>
    <div class="section-title">Medication Details</div>
    <div class="row"><span class="label">Medicine</span>
      <span class="value"><strong>{medicine_name}</strong></span></div>
    <div class="row"><span class="label">Dosage</span>
      <span class="value">{dosage}</span></div>
    <div class="row"><span class="label">Scheduled Time</span>
      <span class="value">{scheduled_time}</span></div>
    <div class="row"><span class="label">Taken At</span>
      <span class="value">{taken_at.strftime('%d %B %Y, %I:%M %p')}</span></div>
    <div style="background:{'#fff8e1' if is_late else '#e8f5e9'};border-radius:12px;
                padding:16px;margin-top:20px;border-left:4px solid {color}">
      {'⚠️ Medicine was taken late. Please ensure future doses are on time.' if is_late
       else '✅ Medicine taken on time. Great health compliance!'}
    </div>"""

    html = _html_base(f'Medicine {"Taken Late" if is_late else "Confirmed"}',
                       color, icon, content)

    rows = [
        ('Patient Name', elder_name),
        ('Status', status),
        ('Medicine', f'{medicine_name} {dosage}'),
        ('Scheduled Time', scheduled_time),
        ('Taken At', taken_at.strftime('%d %B %Y, %I:%M %p')),
    ]
    pdf = _generate_pdf(f'Medicine Confirmation — {elder_name}', rows)
    result = _send(caretaker_email, subject, html, pdf)
    if pdf and os.path.exists(pdf):
        try: os.unlink(pdf)
        except Exception: pass
    return result


def send_missed_dose_email(caretaker_email, caretaker_name, elder_name,
                            medicine_name, dosage, scheduled_time,
                            missed_count=1, reminders_sent=6):
    urgent  = missed_count >= 3
    color   = '#c62828' if urgent else '#e53935'
    icon    = '🚨' if urgent else '⚠️'
    subject = f"{icon} {'URGENT: ' if urgent else ''}Missed Medicine — {elder_name}"

    content = f"""
    <p style="color:#546e7a;font-size:14px;margin-bottom:20px">
      Dear <strong>{caretaker_name}</strong>,<br>
      <strong>{elder_name}</strong> has not taken their prescribed medication.
    </p>
    <div class="section-title">Alert Details</div>
    <div class="row"><span class="label">Patient</span>
      <span class="value"><strong>{elder_name}</strong></span></div>
    <div class="row"><span class="label">Status</span>
      <span class="value"><span class="badge missed">MISSED</span></span></div>
    <div class="row"><span class="label">Medicine</span>
      <span class="value"><strong>{medicine_name} {dosage}</strong></span></div>
    <div class="row"><span class="label">Scheduled Time</span>
      <span class="value">{scheduled_time}</span></div>
    <div class="row"><span class="label">Reminders Sent</span>
      <span class="value">{reminders_sent} of 6</span></div>
    <div class="row"><span class="label">Consecutive Misses</span>
      <span class="value">{missed_count}</span></div>
    <div style="background:#ffebee;border-radius:12px;padding:16px;margin-top:20px;
                border-left:4px solid {color}">
      {'🚨 <strong>CRITICAL:</strong> Multiple consecutive missed doses. Please check immediately.'
       if urgent else '⚠️ Please follow up with the patient to ensure medication is taken.'}
    </div>
    <div style="margin-top:16px;padding:14px;background:#f8fafc;border-radius:10px">
      <strong>Required Actions:</strong><br>
      1. Call the patient immediately<br>
      2. Ensure medication is taken<br>
      3. Contact doctor if needed
    </div>"""

    html = _html_base(f'Missed Medication Alert', color, icon, content)
    rows = [
        ('Patient', elder_name),
        ('Status', 'MISSED ❌'),
        ('Medicine', f'{medicine_name} {dosage}'),
        ('Scheduled', scheduled_time),
        ('Reminders Sent', f'{reminders_sent} of 6'),
        ('Consecutive Misses', str(missed_count)),
    ]
    pdf = _generate_pdf(f'Missed Medicine Alert — {elder_name}', rows)
    result = _send(caretaker_email, subject, html, pdf)
    if pdf and os.path.exists(pdf): 
        try: os.unlink(pdf)
        except Exception: pass
    return result


def send_daily_summary_email(caretaker_email, caretaker_name, summary: list):
    if not summary:
        return False
    today_str = datetime.now().strftime('%d %B %Y')
    subject   = f'📊 Daily Health Report — {today_str}'

    rows_html = ''
    for s in summary:
        rate    = s['rate']
        color   = '#2e7d32' if rate >= 80 else ('#e65100' if rate >= 60 else '#c62828')
        emoji   = '✅' if rate >= 80 else ('⚠️' if rate >= 60 else '🚨')
        bar     = f'<div class="progress-bar"><div class="progress-fill" style="width:{rate}%;background:{color}"></div></div>'
        rows_html += f"""
        <div style="border:1px solid #e2e8f0;border-radius:12px;padding:16px;margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
            <strong style="font-size:15px">{s['elder']}</strong>
            <span style="font-size:22px;font-weight:700;color:{color}">{rate}% {emoji}</span>
          </div>
          {bar}
          <div style="display:flex;gap:12px;margin-top:10px;font-size:13px">
            <span style="background:#e8f5e9;color:#2e7d32;padding:4px 10px;border-radius:8px">✅ Taken: {s['taken']}</span>
            <span style="background:#fff8e1;color:#e65100;padding:4px 10px;border-radius:8px">🕐 Late: {s.get('taken_late',0)}</span>
            <span style="background:#ffebee;color:#c62828;padding:4px 10px;border-radius:8px">❌ Missed: {s['missed']}</span>
            <span style="background:#e3f2fd;color:#1565c0;padding:4px 10px;border-radius:8px">🔔 Reminders: {s.get('reminders',0)}</span>
          </div>
        </div>"""

    content = f"""
    <p style="color:#546e7a;font-size:14px;margin-bottom:20px">
      Dear <strong>{caretaker_name}</strong>,<br>
      Here is today's medication adherence summary for your patients.
    </p>
    <div class="section-title">Daily Report — {today_str}</div>
    {rows_html}
    <div style="background:#e3f2fd;border-radius:12px;padding:14px;margin-top:8px;
                font-size:13px;color:#1565c0">
      ✅ ≥80% — Good adherence &nbsp;|&nbsp;
      ⚠️ 60–79% — Needs attention &nbsp;|&nbsp;
      🚨 &lt;60% — Critical
    </div>"""

    html = _html_base('Daily Medication Report', '#1565c0', '📊', content)

    pdf_rows = []
    for s in summary:
        pdf_rows.append(('Patient', s['elder']))
        pdf_rows.append(('Scheduled', str(s['total'])))
        pdf_rows.append(('Taken', str(s['taken'])))
        pdf_rows.append(('Taken Late', str(s.get('taken_late', 0))))
        pdf_rows.append(('Missed', str(s['missed'])))
        pdf_rows.append(('Reminders', str(s.get('reminders', 0))))
        pdf_rows.append(('Adherence %', f"{s['rate']}%"))
        pdf_rows.append(('', ''))

    pdf = _generate_pdf(f'Daily Health Report — {today_str}', pdf_rows)
    result = _send(caretaker_email, subject, html, pdf)
    if pdf and os.path.exists(pdf):
        try: os.unlink(pdf)
        except Exception: pass
    return result
