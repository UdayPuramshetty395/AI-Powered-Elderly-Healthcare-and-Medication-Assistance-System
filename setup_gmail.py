"""
Gmail API One-Time Setup
========================
Run this ONCE to authorize Gmail API access.
After this, emails work on ALL networks (college WiFi, no hotspot needed).

Steps:
1. Go to https://console.cloud.google.com/
2. Create a new project (e.g. "ElderCare")
3. Enable Gmail API: APIs & Services → Library → search "Gmail API" → Enable
4. Create credentials: APIs & Services → Credentials → Create Credentials
   → OAuth client ID → Desktop app → Download JSON
5. Rename downloaded file to: gmail_credentials.json
6. Place it in this folder (same folder as this script)
7. Run: python setup_gmail.py
8. Browser opens → sign in with udaypuramshetty395@gmail.com → Allow
9. gmail_token.json is created → emails will work automatically

"""
import os

CREDS_FILE = 'gmail_credentials.json'
TOKEN_FILE = 'gmail_token.json'
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

if not os.path.exists(CREDS_FILE):
    print(f'ERROR: {CREDS_FILE} not found.')
    print()
    print('Steps to get it:')
    print('1. Go to https://console.cloud.google.com/')
    print('2. Create project → Enable Gmail API')
    print('3. Credentials → OAuth client ID → Desktop app → Download JSON')
    print(f'4. Save it as: {CREDS_FILE}')
    print('5. Run this script again')
    exit(1)

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())

    print('='*50)
    print('SUCCESS! gmail_token.json created.')
    print('Gmail API is now configured.')
    print('Emails will work on ALL networks.')
    print('='*50)

    # Send a test email
    print()
    print('Sending test email...')
    from googleapiclient.discovery import build
    import base64
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
    msg = MIMEMultipart()
    msg['To']      = 'udaypuramshetty395@gmail.com'
    msg['Subject'] = '✅ ElderCare Gmail API Test'
    msg.attach(MIMEText(
        'Gmail API is working!\n\nYou will now receive medicine reminders '
        'and alerts automatically.\n\n--- AI-Powered Elderly Healthcare System',
        'plain'
    ))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId='me', body={'raw': raw}).execute()
    print('Test email sent to udaypuramshetty395@gmail.com ✅')
    print()
    print('Restart the Flask app: start.bat')

except ImportError:
    print('Installing required package...')
    os.system('venv\\Scripts\\python.exe -m pip install google-auth-oauthlib --quiet')
    print('Done. Run this script again.')
except Exception as e:
    print(f'Error: {e}')
