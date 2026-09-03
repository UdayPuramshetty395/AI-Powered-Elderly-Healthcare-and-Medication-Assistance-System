/**
 * Schedule JS - Medication schedule management
 */

document.addEventListener('DOMContentLoaded', () => {
    if (!requireAuth()) return;
    const path = window.location.pathname;
    if (path === '/schedules') {
        loadEldersDropdown(false);   // load dropdown first (auto-selects if one elder)
        loadSchedules();             // then load schedules
    }
    else if (path === '/schedules/add') initAddScheduleForm();
});

async function loadSchedules() {
    showTableLoading('schedules-tbody', 9);
    const elderId = document.getElementById('filter-elder')?.value || '';
    let endpoint = '/schedules';
    if (elderId) endpoint += `?elder_id=${elderId}`;

    const data = await API.get(endpoint);
    if (!data || !data._ok) {
        showTableEmpty('schedules-tbody', 9, 'Failed to load schedules');
        return;
    }

    const tbody = document.getElementById('schedules-tbody');
    if (!data.schedules.length) {
        showTableEmpty('schedules-tbody', 9, 'No schedules found. Add medicine schedules to begin tracking.');
        return;
    }

    tbody.innerHTML = data.schedules.map((s, idx) => `
        <tr>
            <td>${idx + 1}</td>
            <td><strong>${Utils.formatTime(s.scheduled_time)}</strong></td>
            <td>${s.elder_name}</td>
            <td>${s.medicine_name}</td>
            <td><span class="badge bg-light text-dark border">${s.medicine_dosage || ''}</span></td>
            <td><span class="badge bg-info-subtle text-info">${Utils.capitalize(s.recurrence)}</span></td>
            <td>${s.meal_timing ? s.meal_timing.replace('_', ' ') : 'Anytime'}</td>
            <td>${Utils.statusBadge(s.is_active ? 'active' : 'inactive')}</td>
            <td>
                <div class="d-flex gap-1">
                    <button onclick="toggleSchedule(${s.id}, ${s.is_active})"
                            class="btn btn-sm ${s.is_active ? 'btn-outline-danger' : 'btn-outline-success'}">
                        <i class="bi bi-${s.is_active ? 'pause-circle' : 'play-circle'}"></i>
                    </button>
                    <button onclick="deleteSchedule(${s.id})" class="btn btn-sm btn-outline-danger">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

function initAddScheduleForm() {
    loadEldersDropdown(true);

    const elderSelect = document.getElementById('elder_id');
    elderSelect?.addEventListener('change', async () => {
        const elderId = elderSelect.value;
        const medSelect = document.getElementById('medicine_id');
        medSelect.innerHTML = '<option value="">Loading...</option>';
        medSelect.disabled = true;

        if (!elderId) {
            medSelect.innerHTML = '<option value="">Select elder first...</option>';
            return;
        }

        const data = await API.get(`/medicines/elder/${elderId}`);
        if (data && data._ok && data.medicines.length) {
            medSelect.innerHTML = '<option value="">Choose medicine...</option>' +
                data.medicines.map(m => `<option value="${m.id}">${m.name} (${m.dosage})</option>`).join('');
            medSelect.disabled = false;
        } else {
            medSelect.innerHTML = '<option value="">No active medicines for this elder</option>';
        }
    });

    const form = document.getElementById('add-schedule-form');
    form?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = document.getElementById('submit-btn');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating...';

        const payload = {
            elder_id: parseInt(document.getElementById('elder_id').value),
            medicine_id: parseInt(document.getElementById('medicine_id').value),
            scheduled_time: document.getElementById('scheduled_time').value,
            recurrence: document.getElementById('recurrence').value,
            day_of_week: document.getElementById('day_of_week').value,
            meal_timing: document.getElementById('meal_timing').value,
            notes: document.getElementById('notes').value.trim()
        };

        if (!payload.elder_id || !payload.medicine_id || !payload.scheduled_time) {
            Toast.error('Please fill in all required fields');
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="bi bi-calendar-check me-2"></i>Create Schedule';
            return;
        }

        const data = await API.post('/schedules', payload);
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="bi bi-calendar-check me-2"></i>Create Schedule';

        if (data && data._ok) {
            Toast.success('Schedule created successfully!');
            setTimeout(() => { window.location.href = '/schedules'; }, 800);
        } else {
            Toast.error(data?.error || 'Failed to create schedule');
        }
    });
}

async function loadEldersDropdown(forForm = false) {
    const selectId = forForm ? 'elder_id' : 'filter-elder';
    const select = document.getElementById(selectId);
    if (!select) return;

    const data = await API.get('/elders?per_page=100');
    if (!data || !data._ok) return;

    const options = data.elders.map(e => `<option value="${e.id}">${e.name}</option>`).join('');
    if (forForm) {
        select.innerHTML = '<option value="">Choose elder...</option>' + options;
    } else {
        select.innerHTML = '<option value="">All Elders</option>' + options;
        // Use onchange (not addEventListener) to avoid duplicate listeners
        select.onchange = loadSchedules;
    }

    // Auto-select if only one elder
    if (data.elders.length === 1) {
        select.value = data.elders[0].id;
        // Don't fire change here — would cause loop on list page
        // Just set value silently; loadSchedules already called on init
    }
}

async function toggleSchedule(scheduleId, currentStatus) {
    const data = await API.put(`/schedules/${scheduleId}`, { is_active: !currentStatus });
    if (data && data._ok) {
        Toast.success('Schedule updated');
        loadSchedules();
    }
}

async function deleteSchedule(scheduleId) {
    if (!confirmAction('Delete this schedule?')) return;
    const data = await API.delete(`/schedules/${scheduleId}`);
    if (data && data._ok) {
        Toast.success('Schedule deleted');
        loadSchedules();
    }
}
