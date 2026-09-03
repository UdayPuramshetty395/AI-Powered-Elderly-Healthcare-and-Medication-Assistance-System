"""Run only the APScheduler jobs in a dedicated process.

This script creates the Flask app without starting the web server and ensures the
reminder scheduler from `app.services.reminder_service` is started. Use this as
a background worker on Render or other hosts to avoid duplicate jobs.
"""
from app import create_app
import time
import logging

logger = logging.getLogger(__name__)


def main():
    app = create_app()

    # The scheduler in app.services.reminder_service registers itself using the
    # app context when the app is created. We just keep the process alive.
    logger.info("Scheduler process started. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Scheduler process stopping.")


if __name__ == '__main__':
    main()
