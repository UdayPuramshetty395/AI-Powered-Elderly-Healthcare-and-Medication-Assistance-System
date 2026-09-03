# Deployment Guide — Elderly Healthcare & Medication Assistance System

This document shows how to prepare the project for GitHub and deploy to Render. It keeps the existing app behavior and preserves email, voice, push, SocketIO and scheduler functionality.

1) Local setup (quick)
 - Create a Python virtualenv and activate it.
 - Install deps:
```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
```
 - Create a `.env` file (copy the repository `.env` as a starting point) and set secrets.
 - Run locally:
```powershell
\.venv\Scripts\python.exe run.py
```

2) GitHub preparation
 - Ensure the following files are in `.gitignore`: `venv/`, `.env`, `elderly_healthcare.db`, `gmail_credentials.json`, `gmail_token.json`, `.agent_credentials.json`, `__pycache__/`, `*.pyc`.
 - If any secret files are already committed, purge them from history (see next section).

3) Sensitive files removal (if tracked)
 - To remove files from the current index without rewriting history:
```bash
git rm --cached .env gmail_credentials.json gmail_token.json elderly_healthcare.db .agent_credentials.json
git commit -m "remove local secrets from index"
git push
```
 - To purge secrets from Git history (recommended if secrets were pushed):
   - Use `git filter-repo` (preferred):
```bash
pip install git-filter-repo
git clone --mirror <repo-url> repo.git
cd repo.git
git filter-repo --invert-paths --paths .env --paths gmail_credentials.json --paths gmail_token.json --paths elderly_healthcare.db --paths .agent_credentials.json
git push --force
```
   - If `git filter-repo` is not available, `git filter-branch` can be used but is slower and more error-prone.
 - After history rewrite: rotate any exposed credentials (Gmail OAuth client, VAPID keys, JWT secrets, admin passwords).

4) Required environment variables (Render / production)
 - `FLASK_ENV=production`
 - `SECRET_KEY` (strong random value)
 - `JWT_SECRET_KEY` (strong random value)
 - `DATABASE_URL` (e.g., postgres://user:pass@host:5432/dbname)
 - `MAIL_USE_SMTP` (true/false)
 - If using SMTP:
   - `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`
 - If using Gmail API:
  - Store `gmail_token.json` securely in Render secrets and write it to disk at startup (see notes)
  - A helper script `scripts/write_gmail_token.py` is included in the repository. It supports two deployment patterns:
    - `GMAIL_TOKEN_JSON` — raw JSON content of the token written directly to `gmail_token.json`.
    - `GMAIL_TOKEN_JSON_B64` — base64-encoded JSON written and decoded at startup.
    Example start command on Render:

```text
python scripts/write_gmail_token.py && python run.py
```
 - `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIMS_EMAIL`
 - `SARVAM_API_KEY` (optional)
 - `OPENAI_API_KEY` (optional)
 - `PORT` (Render sets automatically)

5) Gmail in cloud
 - Two options:
   A) SMTP: set `MAIL_USE_SMTP=true` and provide `MAIL_USERNAME` and `MAIL_PASSWORD` (App Password recommended).
   B) Gmail API: upload `gmail_token.json` into Render as a secret file and write it to the app root at deploy-time. Alternatively store the token JSON content in a secret env var and write a small startup script to save it to `gmail_token.json`.

6) VAPID / Push
 - Generate VAPID keys locally (if not present) and set `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY` as secrets in Render. Keep the private key safe.

7) Database (Postgres on Render)
 - Locally app uses SQLite. For production use Postgres and set `DATABASE_URL` accordingly. Ensure `psycopg2-binary` is available in `requirements.txt` if needed.
 - Run migrations:
```powershell
\.venv\Scripts\flask db init   # only first time
\.venv\Scripts\flask db migrate -m "init"
\.venv\Scripts\flask db upgrade
```

8) SocketIO & production command
 - Simple and safe Render command (single process):
```text
web: python run.py
```
 - For better performance with many concurrent sockets, consider `gunicorn` + `eventlet` and a single worker; do NOT run multiple workers if the scheduler is enabled in the same process.
 - Example (advanced, requires testing):
```text
web: gunicorn -k eventlet -w 1 "run:app"
```
 - NOTE: If using multiple web instances, move APScheduler to a dedicated worker or disable it in web processes.

9) APScheduler considerations
 - The app starts APScheduler in `create_app()` unless skipped by reloader checks. Multiple running web processes will create duplicate scheduler jobs.
 - Options:
   - Keep a single web instance (recommended for small deployments).
   - Run a dedicated scheduler service (background service) that imports the app and calls `init_scheduler(app)`.
   - Use an external worker (e.g., Render background worker) to run scheduled tasks only.

10) Running the local voice agent
 - The local agent `reminder_agent.py` is intended for Windows machines to play audio locally. Keep `start_agent.bat` for convenience.
 - To run:
```powershell
\.venv\Scripts\activate
python reminder_agent.py --poll --repeat-minutes 2
```

11) Testing
 - Install dev deps and run tests:
```powershell
\.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pip install pytest
python -m pytest -q
```

12) Troubleshooting notes
 - If email fails, verify `gmail_token.json` or SMTP credentials.
 - If push fails, verify VAPID keys and browser subscription.
 - If voice generation fails in cloud, use Sarvam/edge/gTTS fallbacks; cloud servers cannot play to local speakers — keep `reminder_agent.py` for local playback.

Contact / Next steps
 - After pushing to GitHub, I can supply a `render.yaml` and step-by-step Render instructions and the exact secrets list to add. I can also produce a script to write `gmail_token.json` from a secret env var at startup.
