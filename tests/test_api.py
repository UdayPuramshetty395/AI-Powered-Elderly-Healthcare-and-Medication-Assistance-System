"""
API Tests for Elderly Healthcare System
"""
import pytest
import json
from datetime import date
from app import create_app, db
from app.routes import settings as settings_module
from app.routes.reports import _format_email_body
from app.services.chatbot_service import ChatbotService


@pytest.fixture
def app():
    """Create test application."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(client):
    """Register and login to get JWT token."""
    # Register
    client.post('/api/auth/register', json={
        'username': 'testuser',
        'email': 'test@test.com',
        'password': 'Test@1234',
        'role': 'caretaker',
        'full_name': 'Test User'
    })
    # Login
    resp = client.post('/api/auth/login', json={
        'username': 'testuser',
        'password': 'Test@1234'
    })
    token = json.loads(resp.data)['access_token']
    return {'Authorization': f'Bearer {token}'}


def test_format_email_body_returns_html_report():
    subject, body = _format_email_body(
        elder_name='Srinivas Puramshetty',
        report_date=date(2026, 6, 27),
        total=3,
        taken=3,
        taken_late=0,
        missed=0,
        reminders=8,
        adherence=100.0,
        medicine_details=[{
            'name': 'Atorvastatin',
            'dosage': '100mg',
            'taken': 1,
            'taken_late': 0,
            'missed': 0,
            'total': 1,
        }],
    )

    assert 'Daily Health Report' in subject
    assert '<table' in body
    assert 'Atorvastatin' in body
    assert '![`' not in body
    assert '](' not in body


def test_chatbot_handles_short_greeting():
    service = ChatbotService()
    response = service.get_response('hi')

    assert response['source'] == 'rule_based'
    assert 'Healthcare Assistant' in response['text']
    assert response['suggestions']


def test_chatbot_handles_diabetes_sweets_query():
    service = ChatbotService()
    response = service.get_response('Can I eat heavy sweets despite having diabetes?')

    assert response['source'] == 'rule_based'
    assert 'sweets' in response['text'].lower() or 'sugar' in response['text'].lower()
    assert 'diabetes' in response['text'].lower()
    assert 'consult' in response['text'].lower() or 'doctor' in response['text'].lower()


# ---- Auth Tests ----
class TestAuth:
    def test_register_success(self, client):
        resp = client.post('/api/auth/register', json={
            'username': 'newuser',
            'email': 'new@test.com',
            'password': 'Test@1234',
            'role': 'caretaker'
        })
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert 'access_token' in data
        assert data['user']['username'] == 'newuser'

    def test_register_duplicate_username(self, client):
        client.post('/api/auth/register', json={
            'username': 'dupuser', 'email': 'dup@test.com',
            'password': 'Test@1234', 'role': 'caretaker'
        })
        resp = client.post('/api/auth/register', json={
            'username': 'dupuser', 'email': 'dup2@test.com',
            'password': 'Test@1234', 'role': 'caretaker'
        })
        assert resp.status_code == 409

    def test_login_success(self, client):
        client.post('/api/auth/register', json={
            'username': 'logintest', 'email': 'login@test.com',
            'password': 'Test@1234', 'role': 'caretaker'
        })
        resp = client.post('/api/auth/login', json={
            'username': 'logintest', 'password': 'Test@1234'
        })
        assert resp.status_code == 200
        assert 'access_token' in json.loads(resp.data)

    def test_login_wrong_password(self, client):
        client.post('/api/auth/register', json={
            'username': 'wrongpwd', 'email': 'wpwd@test.com',
            'password': 'Test@1234', 'role': 'caretaker'
        })
        resp = client.post('/api/auth/login', json={
            'username': 'wrongpwd', 'password': 'WrongPass1'
        })
        assert resp.status_code == 401

    def test_get_me(self, client, auth_headers):
        resp = client.get('/api/auth/me', headers=auth_headers)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['user']['username'] == 'testuser'

    def test_get_me_no_auth(self, client):
        resp = client.get('/api/auth/me')
        assert resp.status_code == 401

    def test_save_email_uses_registered_email_for_test(self, client, auth_headers, monkeypatch):
        captured = {}

        def fake_send_smtp_email(smtp_user, smtp_pass, to_email, subject, body):
            captured['to_email'] = to_email
            return {'success': True}

        monkeypatch.setattr(settings_module, '_send_smtp_email', fake_send_smtp_email)

        resp = client.post('/api/settings/email', headers=auth_headers, json={
            'username': 'smtp@example.com',
            'password': 'AppPass123'
        })

        assert resp.status_code == 200
        assert captured['to_email'] == 'test@test.com'


# ---- Elder Tests ----
class TestElders:
    def test_create_elder(self, client, auth_headers):
        resp = client.post('/api/elders', headers=auth_headers, json={
            'name': 'Test Elder',
            'age': 70,
            'gender': 'male'
        })
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert data['elder']['name'] == 'Test Elder'

    def test_get_elders(self, client, auth_headers):
        resp = client.get('/api/elders', headers=auth_headers)
        assert resp.status_code == 200
        assert 'elders' in json.loads(resp.data)

    def test_create_elder_missing_name(self, client, auth_headers):
        resp = client.post('/api/elders', headers=auth_headers, json={
            'age': 70, 'gender': 'male'
        })
        assert resp.status_code == 400

    def test_create_elder_invalid_age(self, client, auth_headers):
        resp = client.post('/api/elders', headers=auth_headers, json={
            'name': 'Test', 'age': -5, 'gender': 'male'
        })
        assert resp.status_code == 400

    def test_get_elder_by_id(self, client, auth_headers):
        resp = client.post('/api/elders', headers=auth_headers, json={
            'name': 'Test Elder', 'age': 65, 'gender': 'female'
        })
        elder_id = json.loads(resp.data)['elder']['id']
        resp = client.get(f'/api/elders/{elder_id}', headers=auth_headers)
        assert resp.status_code == 200

    def test_update_elder(self, client, auth_headers):
        resp = client.post('/api/elders', headers=auth_headers, json={
            'name': 'Original', 'age': 65, 'gender': 'female'
        })
        elder_id = json.loads(resp.data)['elder']['id']
        resp = client.put(f'/api/elders/{elder_id}', headers=auth_headers, json={'name': 'Updated'})
        assert resp.status_code == 200
        assert json.loads(resp.data)['elder']['name'] == 'Updated'

    def test_delete_elder(self, client, auth_headers):
        resp = client.post('/api/elders', headers=auth_headers, json={
            'name': 'To Delete', 'age': 72, 'gender': 'male'
        })
        elder_id = json.loads(resp.data)['elder']['id']
        resp = client.delete(f'/api/elders/{elder_id}', headers=auth_headers)
        assert resp.status_code == 200


# ---- Medicine Tests ----
class TestMedicines:
    def _create_elder(self, client, auth_headers):
        resp = client.post('/api/elders', headers=auth_headers, json={
            'name': 'Med Elder', 'age': 68, 'gender': 'male'
        })
        return json.loads(resp.data)['elder']['id']

    def test_create_medicine(self, client, auth_headers):
        elder_id = self._create_elder(client, auth_headers)
        resp = client.post('/api/medicines', headers=auth_headers, json={
            'elder_id': elder_id,
            'name': 'Metformin',
            'dosage': '500mg',
            'frequency': 'Twice daily'
        })
        assert resp.status_code == 201
        assert json.loads(resp.data)['medicine']['name'] == 'Metformin'

    def test_get_medicines_by_elder(self, client, auth_headers):
        elder_id = self._create_elder(client, auth_headers)
        client.post('/api/medicines', headers=auth_headers, json={
            'elder_id': elder_id, 'name': 'Aspirin',
            'dosage': '75mg', 'frequency': 'Once daily'
        })
        resp = client.get(f'/api/medicines/elder/{elder_id}', headers=auth_headers)
        assert resp.status_code == 200
        assert len(json.loads(resp.data)['medicines']) >= 1


# ---- Dashboard Tests ----
class TestDashboard:
    def test_get_stats(self, client, auth_headers):
        resp = client.get('/api/dashboard/stats', headers=auth_headers)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'total_elders' in data

    def test_get_adherence_chart(self, client, auth_headers):
        resp = client.get('/api/dashboard/adherence-chart', headers=auth_headers)
        assert resp.status_code == 200

    def test_get_today_schedule(self, client, auth_headers):
        resp = client.get('/api/dashboard/today-schedule', headers=auth_headers)
        assert resp.status_code == 200


# ---- Chatbot Tests ----
class TestChatbot:
    def test_send_message(self, client, auth_headers):
        resp = client.post('/api/chatbot/message', headers=auth_headers, json={
            'message': 'What is Metformin used for?'
        })
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'response' in data
        assert 'metformin' in data['response'].lower() or 'diabetes' in data['response'].lower()

    def test_get_suggestions(self, client, auth_headers):
        resp = client.get('/api/chatbot/suggestions', headers=auth_headers)
        assert resp.status_code == 200
        assert 'suggestions' in json.loads(resp.data)

    def test_empty_message(self, client, auth_headers):
        resp = client.post('/api/chatbot/message', headers=auth_headers, json={'message': ''})
        assert resp.status_code == 400

    def test_symptom_message_after_medication_context(self, client, auth_headers):
        # Simulate prior assistant response about Metformin in history
        user_id = 1
        from app.routes.chatbot import conversation_history
        conversation_history[str(user_id)] = [
            {'role': 'assistant', 'content': 'Metformin is used to treat type 2 diabetes.'}
        ]

        resp = client.post('/api/chatbot/message', headers=auth_headers, json={
            'message': 'I am feeling headache'
        })
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'headache' in data['response'].lower() or 'pain' in data['response'].lower() or 'medical' in data['response'].lower()
