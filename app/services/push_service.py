"""
Web Push Notification Service (Free — no Firebase account needed)
Uses VAPID + pywebpush to send push notifications via the Web Push Protocol.
Works when browser is minimized, in background, or on another tab.
Requires the user to have subscribed via the PWA service worker.
"""
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '').replace('\\n', '\n')
VAPID_EMAIL = os.environ.get('VAPID_CLAIMS_EMAIL', 'admin@elderlycare.local')


class PushService:

    @staticmethod
    def send_push(subscription_info: dict, title: str, body: str,
                  data: dict = None, icon: str = '/static/icons/icon-192.png',
                  badge: str = '/static/icons/badge-72.png',
                  tag: str = 'medicine-reminder',
                  require_interaction: bool = False,
                  actions: list = None) -> bool:
        """
        Send a Web Push notification to a subscribed browser.
        Works when the app is not open.

        subscription_info: dict from browser PushManager.subscribe()
        Returns True on success, False on failure.
        """
        if not VAPID_PUBLIC_KEY or not VAPID_PRIVATE_KEY:
            logger.warning('VAPID keys not configured — push skipped')
            return False

        try:
            from pywebpush import webpush, WebPushException

            payload = json.dumps({
                'title': title,
                'body': body,
                'icon': icon,
                'badge': badge,
                'tag': tag,
                'requireInteraction': require_interaction,
                'actions': actions or [],
                'data': data or {},
                'timestamp': int(datetime.now().timestamp() * 1000),
            })

            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={
                    'sub': f'mailto:{VAPID_EMAIL}',
                }
            )
            logger.info(f'Push sent: {title}')
            return True

        except Exception as e:
            logger.error(f'Push failed: {e}')
            return False

    @staticmethod
    def send_medicine_reminder(subscription_info: dict, elder_name: str,
                                medicine_name: str, dosage: str,
                                scheduled_time: str, level: int,
                                schedule_id: int, elder_id: int,
                                medicine_id: int = 0) -> bool:
        """Send a medicine reminder push notification."""
        titles = {
            1: f'💊 Medicine Time — {elder_name}',
            2: f'⚠️ Reminder — {elder_name} has not taken medicine',
            3: f'🚨 CRITICAL — Medicine not taken!',
        }
        bodies = {
            1: f'Time to take {medicine_name} {dosage}. Scheduled: {scheduled_time}',
            2: f'{medicine_name} {dosage} still not confirmed. Please take immediately.',
            3: f'URGENT: {medicine_name} {dosage} not taken! Health at risk.',
        }
        actions = [
            {'action': 'taken', 'title': '✅ Taken'},
            {'action': 'snooze', 'title': '⏰ Snooze 10 min'},
        ]
        if level == 3:
            actions = [{'action': 'taken', 'title': '✅ Mark as Taken'}]

        return PushService.send_push(
            subscription_info=subscription_info,
            title=titles.get(level, titles[1]),
            body=bodies.get(level, bodies[1]),
            data={
                'type': 'medicine_reminder',
                'level': level,
                'schedule_id': schedule_id,
                'elder_id': elder_id,
                'medicine_id': medicine_id,
                'medicine_name': medicine_name,
                'dosage': dosage,
                'url': '/elder-view',
            },
            tag=f'reminder-{schedule_id}',
            require_interaction=level >= 2,
            actions=actions
        )

    @staticmethod
    def send_caretaker_alert(subscription_info: dict, elder_name: str,
                              medicine_name: str, scheduled_time: str,
                              level: int) -> bool:
        """Send caretaker escalation push notification."""
        severity_labels = {1: 'Missed Dose', 2: '⚠️ Multiple Missed Doses', 3: '🚨 Critical'}
        return PushService.send_push(
            subscription_info=subscription_info,
            title=f'Medication Alert — {severity_labels.get(level, "Alert")}',
            body=(f'{elder_name} has not taken {medicine_name} '
                  f'scheduled at {scheduled_time}. Status: Not Confirmed.'),
            data={
                'type': 'caretaker_alert',
                'elder_name': elder_name,
                'medicine_name': medicine_name,
                'url': '/dashboard',
            },
            tag=f'caretaker-alert-{elder_name}',
            require_interaction=True,
        )
