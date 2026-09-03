/**
 * Dashboard JS - Real-time dashboard with auto-refresh
 */

let dashboardRefreshInterval = null;

document.addEventListener('DOMContentLoaded', () => {
    if (!requireAuth()) return;
    loadDashboardData();

    // Auto-refresh every 30 seconds
    dashboardRefreshInterval = setInterval(() => {
        loadStats();
        loadTodaySchedule();
        loadRecentAlerts();
        loadLatestReportCard();
    }, 30000);

    // Update schedule time badge
    setInterval(updateScheduleTimeBadge, 1000);
});

function updateScheduleTimeBadge() {
    const el = document.getElementById('schedule-time-badge');
    if (el) el.textContent = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
}

async function loadDashboardData() {
    document.getElementById('last-refreshed') && (document.getElementById('last-refreshed').textContent = '');
    await Promise.all([
        loadStats(),
        loadTodaySchedule(),
        loadAdherenceChart(),
        loadRecentAlerts()
    ]);
    const el = document.getElementById('last-refreshed');
    if (el) el.textContent = 'Updated ' + new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

async function loadStats() {
    const data = await API.get('/dashboard/stats');
    if (!data || !data._ok) return;

    document.getElementById('stat-total-elders').textContent = data.total_elders || 0;
    document.getElementById('stat-active-medicines').textContent = data.total_active_medicines || 0;
    document.getElementById('stat-today-doses').textContent = `${data.today_taken || 0}/${data.today_schedules || 0}`;

    const adherenceEl = document.getElementById('stat-adherence-rate');
    if (adherenceEl) {
        const rate = data.monthly_adherence_rate || 0;
        adherenceEl.textContent = `${rate}%`;
        adherenceEl.parentElement.parentElement.className = `stat-card stat-card-${Utils.adherenceColor(rate)}`;
    }
    document.getElementById('stat-unread-alerts').textContent = data.unread_alerts || 0;
}

async function loadTodaySchedule() {
    const tbody = document.getElementById('today-schedule-tbody');
    if (!tbody) return;

    const data = await API.get('/dashboard/today-schedule');
    if (!data || !data._ok || !data.schedules.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">No medication schedules for today</td></tr>';
        return;
    }

    const now = new Date();
    const nowMinutes = now.getHours() * 60 + now.getMinutes();

    tbody.innerHTML = data.schedules.map(s => {
        const status = s.adherence_status || 'pending';
        const [h, m] = s.scheduled_time.split(':');
        const doseMinutes = parseInt(h) * 60 + parseInt(m);
        const diff = doseMinutes - nowMinutes;

        let rowClass = '';
        let urgencyBadge = '';

        if (status === 'pending') {
            if (diff < 0 && diff > -60) {
                rowClass = 'table-danger';
                urgencyBadge = `<span class="badge bg-danger ms-1" style="font-size:10px;animation:blink 1s infinite">OVERDUE</span>`;
            } else if (diff >= 0 && diff <= 15) {
                rowClass = 'table-warning';
                urgencyBadge = `<span class="badge bg-warning text-dark ms-1" style="font-size:10px">DUE SOON</span>`;
            }
        }

        return `
        <tr class="${rowClass}">
            <td>
                <strong>${Utils.formatTime(s.scheduled_time)}</strong>
                ${urgencyBadge}
            </td>
            <td><i class="bi bi-person-fill text-primary me-1"></i>${s.elder_name}</td>
            <td><i class="bi bi-capsule me-1 text-success"></i>${s.medicine_name}</td>
            <td><span class="badge bg-light text-dark border">${s.medicine_dosage}</span></td>
            <td>${Utils.statusBadge(status)}</td>
        </tr>`;
    }).join('');
}

async function loadAdherenceChart() {
    const ctx = document.getElementById('adherenceChart');
    if (!ctx) return;

    const data = await API.get('/dashboard/adherence-chart?days=7');
    if (!data || !data._ok) return;

    if (window.dashboardChart) window.dashboardChart.destroy();

    window.dashboardChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.chart_data.map(d => d.day),
            datasets: [{
                label: 'Taken',
                data: data.chart_data.map(d => d.taken),
                backgroundColor: 'rgba(67, 160, 71, 0.8)',
                borderColor: '#43a047',
                borderWidth: 1,
                borderRadius: 4
            }, {
                label: 'Missed',
                data: data.chart_data.map(d => d.missed),
                backgroundColor: 'rgba(229, 57, 53, 0.8)',
                borderColor: '#e53935',
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top' },
                tooltip: {
                    callbacks: {
                        footer: (items) => {
                            const idx = items[0].dataIndex;
                            return `Adherence: ${data.chart_data[idx].rate}%`;
                        }
                    }
                }
            },
            scales: {
                x: { stacked: false },
                y: { beginAtZero: true, ticks: { stepSize: 1 } }
            }
        }
    });

    const el = document.getElementById('chart-refresh-indicator');
    if (el) el.textContent = 'Updated ' + new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
}

async function loadRecentAlerts() {
    const container = document.getElementById('recent-alerts');
    if (!container) return;

    const data = await API.get('/alerts/unread');
    if (!data || !data._ok || !data.alerts.length) {
        container.innerHTML = '<p class="text-center text-muted py-3 mb-0"><i class="bi bi-check-circle-fill text-success me-1"></i>No unread alerts</p>';
        return;
    }

    container.innerHTML = data.alerts.slice(0, 6).map(alert => `
        <div class="alert-item severity-${alert.severity} ${alert.is_read ? '' : 'unread'} mb-2">
            <div class="d-flex justify-content-between align-items-start mb-1">
                <strong class="text-dark" style="font-size:12px">${alert.alert_type.replace('_', ' ').toUpperCase()}</strong>
                ${Utils.severityBadge(alert.severity)}
            </div>
            <p class="mb-1 small">${alert.message}</p>
            <div class="d-flex justify-content-between align-items-center">
                <small class="text-muted">${Utils.timeAgo(alert.sent_at)}</small>
                <button onclick="markAlertRead(${alert.id})" class="btn btn-sm btn-outline-primary py-0" style="font-size:11px">
                    Mark Read
                </button>
            </div>
        </div>
    `).join('');
}

async function markAlertRead(alertId) {
    const data = await API.put(`/alerts/${alertId}/read`);
    if (data && data._ok) {
        Toast.success('Alert marked as read');
        await loadRecentAlerts();
        await loadAlertsBadge();
    }
}

async function loadDashboardData() {
    if (document.getElementById('last-refreshed')) {
        document.getElementById('last-refreshed').textContent = '';
    }
    await Promise.all([
        loadStats(),
        loadTodaySchedule(),
        loadAdherenceChart(),
        loadRecentAlerts(),
        loadLatestReportCard()
    ]);
    const el = document.getElementById('last-refreshed');
    if (el) el.textContent = 'Updated ' + new Date().toLocaleTimeString('en-IN',
        { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

async function loadLatestReportCard() {
    const container = document.getElementById('latest-report-body');
    if (!container) return;

    const data = await API.get('/reports/latest');
    if (!data || !data._ok || !data.reports.length) {
        container.innerHTML = `
            <div class="text-center text-muted py-3">
                <i class="bi bi-clipboard-x" style="font-size:32px;display:block;margin-bottom:8px"></i>
                No report yet today.<br>
                <small>Auto-generated at 9 PM daily.</small>
            </div>`;
        return;
    }

    const reports = data.reports;
    container.innerHTML = reports.map(r => {
        const adhColor = r.adherence_percent >= 80 ? 'success'
                       : r.adherence_percent >= 60 ? 'warning' : 'danger';
        return `
        <div class="mb-3 pb-3 border-bottom">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <strong>${r.elder_name}</strong>
                <span class="badge bg-${adhColor}">${r.adherence_percent}%</span>
            </div>
            <div class="row g-1 text-center" style="font-size:12px">
                <div class="col-3">
                    <div class="p-1 rounded" style="background:#e3f2fd">
                        <div class="fw-700">${r.total_scheduled}</div>
                        <div class="text-muted">Total</div>
                    </div>
                </div>
                <div class="col-3">
                    <div class="p-1 rounded" style="background:#e8f5e9">
                        <div class="fw-700 text-success">${r.total_taken}</div>
                        <div class="text-muted">Taken</div>
                    </div>
                </div>
                <div class="col-3">
                    <div class="p-1 rounded" style="background:#fff8e1">
                        <div class="fw-700 text-warning">${r.total_taken_late}</div>
                        <div class="text-muted">Late</div>
                    </div>
                </div>
                <div class="col-3">
                    <div class="p-1 rounded" style="background:#ffebee">
                        <div class="fw-700 text-danger">${r.total_missed}</div>
                        <div class="text-muted">Missed</div>
                    </div>
                </div>
            </div>
            <div class="mt-2 d-flex justify-content-between align-items-center">
                <small class="text-muted">Reminders: ${r.total_reminders}</small>
                <span class="badge ${r.email_sent ? 'bg-success' : 'bg-secondary'}" style="font-size:10px">
                    ${r.email_sent ? '📧 Email Sent' : '⏳ Email Pending'}
                </span>
            </div>
        </div>`;
    }).join('').replace(/<div class="mb-3 pb-3 border-bottom">(?!.*<div class="mb-3)/s,
        '<div class="mb-3 pb-2">');
}

async function sendReportNowDashboard() {
    const btn = event.target;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Sending...';

    const data = await API.post('/reports/generate-now', {});
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-send me-1"></i>Send Now';

    if (data && data._ok) {
        Toast.success('✅ Report generated and email sent!');
        loadLatestReportCard();
    } else {
        Toast.error(data?.error || 'Failed to generate report');
    }
}
