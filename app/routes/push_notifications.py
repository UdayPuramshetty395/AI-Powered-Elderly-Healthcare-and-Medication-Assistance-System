"""
Push Notification API
POST /api/push/subscribe        — save browser push subscription
DELETE /api/push/unsubscribe    — remove subscription
GET  /api/push/vapid-public-key — return VAPID public key for browser
POST /api/push/test             — send a test push to current user
"""
import json
import os
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.user import User

push_bp = Blueprint('push', __name__)

# In-memory subscription store (use Redis/DB for production)
# Structure: { user_id: [subscription_dict, ...] }
_subscriptions: dict = {}


def _get_user():
    return User.query.get(int(get_jwt_identity()))


@push_bp.route('/vapid-public-key', methods=['GET'])
def get_vapid_key():
    """Return the VAPID public key for the browser to subscribe."""
    key = os.environ.get('VAPID_PUBLIC_KEY', '')
    return jsonify({'public_key': key}), 200


@push_bp.route('/subscribe', methods=['POST'])
@jwt_required()
def subscribe():
    """Save a browser push subscription."""
    user = _get_user()
    data = request.get_json()
    subscription = data.get('subscription')
    if not subscription:
        return jsonify({'error': 'subscription required'}), 400

    user_id = str(user.id)
    if user_id not in _subscriptions:
        _subscriptions[user_id] = []

    # Avoid duplicates (match by endpoint)
    endpoint = subscription.get('endpoint', '')
    existing = [s for s in _subscriptions[user_id]
                if s.get('endpoint') != endpoint]
    existing.append(subscription)
    _subscriptions[user_id] = existing

    return jsonify({'message': 'Subscribed successfully',
                    'count': len(existing)}), 200


@push_bp.route('/unsubscribe', methods=['DELETE'])
@jwt_required()
def unsubscribe():
    user = _get_user()
    data = request.get_json() or {}
    endpoint = data.get('endpoint', '')
    user_id = str(user.id)

    if user_id in _subscriptions:
        _subscriptions[user_id] = [
            s for s in _subscriptions[user_id]
            if s.get('endpoint') != endpoint
        ]

    return jsonify({'message': 'Unsubscribed'}), 200


@push_bp.route('/test', methods=['POST'])
@jwt_required()
def test_push():
    """Send a test push notification to the current user."""
    user = _get_user()
    user_id = str(user.id)
    subs = _subscriptions.get(user_id, [])
    if not subs:
        return jsonify({'error': 'No active subscription. Enable notifications first.'}), 400

    from app.services.push_service import PushService
    results = []
    for sub in subs:
        ok = PushService.send_push(
            subscription_info=sub,
            title='✅ Test Notification',
            body='Push notifications are working! Reminders will arrive automatically.',
            data={'type': 'test', 'url': '/dashboard'},
            tag='test'
        )
        results.append(ok)

    success = any(results)
    return jsonify({
        'success': success,
        'sent': sum(results),
        'message': 'Test push sent!' if success else 'Push failed — check VAPID keys'
    }), 200 if success else 500


def get_subscriptions_for_user(user_id: int) -> list:
    """Get all push subscriptions for a user (used by services)."""
    return _subscriptions.get(str(user_id), [])
