# Required Environment Variables (Render / Production)

Set these environment variables in your deployment platform (Render). Do NOT commit secrets to Git.

- `FLASK_ENV` - Set to `production` in production.
- `SECRET_KEY` - Strong random secret for Flask sessions.
- `JWT_SECRET_KEY` - Strong random secret for JWT tokens.
- `DATABASE_URL` - Database connection string (e.g. `postgres://user:pass@host:5432/dbname`).
- `MAIL_USE_SMTP` - `True` or `False`. If `True`, SMTP is used; otherwise Gmail API is preferred.
- `MAIL_USERNAME` - SMTP username (if `MAIL_USE_SMTP` is `True`).
- `MAIL_PASSWORD` - SMTP password or app password.
- `MAIL_DEFAULT_SENDER` - Default From address for emails.
- `MAIL_USE_SMTP` - (duplicate intentionally to highlight) boolean flag to enable SMTP fallback.
- `VAPID_PUBLIC_KEY` - VAPID public key for Web Push.
- `VAPID_PRIVATE_KEY` - VAPID private key (keep secret).
- `VAPID_CLAIMS_EMAIL` - Contact email used in VAPID claims (e.g. `admin@yourdomain.com`).
- `SARVAM_API_KEY` - Optional: API key for Sarvam AI Bulbul TTS.
- `OPENAI_API_KEY` - Optional: OpenAI key for chatbot augmentation.
- `PORT` - Port Render sets automatically; app reads `PORT` if provided.
- `MAIL_USE_SMTP` - (note) configure to `True` when using SMTP credentials.

Optional (for advanced setups):
- `SOCKETIO_MESSAGE_QUEUE` - Redis URL if using message queue for Socket.IO across multiple instances.
- `AUDIO_DIR` - Path for generated audio files (default: `app/static/audio`).

Gmail API deployment notes:
- If you prefer Gmail API over SMTP, store the `gmail_token.json` content in a secure secret (e.g., `GMAIL_TOKEN_JSON`) and write it to `gmail_token.json` on startup using a small script. DO NOT store `gmail_credentials.json` in source control.

Security checklist after deployment:
- Rotate any credentials that were exposed in local files.
- Ensure `SECRET_KEY` and `JWT_SECRET_KEY` are >32 bytes and random.
- Keep `VAPID_PRIVATE_KEY` secret.
