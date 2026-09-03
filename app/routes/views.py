from flask import Blueprint, render_template, redirect, url_for

views_bp = Blueprint('views', __name__)


@views_bp.route('/')
def index():
    return render_template('index.html')


@views_bp.route('/login')
def login():
    return render_template('login.html')


@views_bp.route('/register')
def register():
    return render_template('register.html')


@views_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@views_bp.route('/elders')
def elders():
    return render_template('elder/list.html')


@views_bp.route('/elders/add')
def add_elder():
    return render_template('elder/add.html')


@views_bp.route('/elders/<int:elder_id>')
def elder_detail(elder_id):
    return render_template('elder/detail.html', elder_id=elder_id)


@views_bp.route('/medicines')
def medicines():
    return render_template('medicine/list.html')


@views_bp.route('/medicines/add')
def add_medicine():
    return render_template('medicine/add.html')


@views_bp.route('/schedules')
def schedules():
    return render_template('schedule/list.html')


@views_bp.route('/schedules/add')
def add_schedule():
    return render_template('schedule/add.html')


@views_bp.route('/adherence')
def adherence():
    return render_template('adherence/tracker.html')


@views_bp.route('/chatbot')
def chatbot():
    return render_template('chatbot/chat.html')


@views_bp.route('/reminders')
def reminders():
    return render_template('reminders.html')


@views_bp.route('/wellness')
def wellness():
    return render_template('wellness.html')


@views_bp.route('/elder-view')
def elder_view():
    """Elder-friendly simple interface."""
    return render_template('elder_view.html')


@views_bp.route('/analytics')
def analytics():
    return render_template('analytics.html')


@views_bp.route('/reports')
def reports():
    return render_template('reports.html')


@views_bp.route('/settings')
def settings():
    return render_template('settings.html')


@views_bp.route('/profile')
def profile():
    return render_template('profile.html')
