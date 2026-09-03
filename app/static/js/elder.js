/**
 * Elder JS - Elder CRUD operations
 */

let allElders = [];
let currentElderId = null;

document.addEventListener('DOMContentLoaded', () => {
    if (!requireAuth()) return;
    initElderPage();
});

async function initElderPage() {
    const page = document.body.dataset.page;
    if (page === 'elder-list') await loadElders();
    else if (page === 'elder-add') initAddElderForm();
    else if (page === 'elder-detail') {
        currentElderId = parseInt(document.body.dataset.elderId);
        await loadElderDetail(currentElderId);
    }
}

// ---- Elder List ----
async function loadElders(search = '') {
    showTableLoading('elders-tbody', 7);
    const endpoint = `/elders?search=${encodeURIComponent(search)}`;
    const data = await API.get(endpoint);

    if (!data || !data._ok) {
        Toast.error('Failed to load elders');
        showTableEmpty('elders-tbody', 7, 'Failed to load elder profiles');
        return;
    }

    allElders = data.elders || [];
    renderElderCards(allElders);

    const countEl = document.getElementById('elder-count');
    if (countEl) countEl.textContent = `${data.total || allElders.length} elders`;
}

function renderElderCards(elders) {
    const container = document.getElementById('elders-grid');
    if (!container) return;

    if (elders.length === 0) {
        container.innerHTML = `
            <div class="col-12">
                <div class="empty-state">
                    <i class="bi bi-people"></i>
                    <p>No elder profiles yet</p>
                    <a href="/elders/add" class="btn btn-primary mt-2">
                        <i class="bi bi-plus-lg me-2"></i>Add Elder
                    </a>
                </div>
            </div>`;
        return;
    }

    container.innerHTML = elders.map(elder => `
        <div class="col-lg-4 col-md-6 mb-4">
            <div class="card elder-card">
                <div class="elder-card-header">
                    <div class="elder-avatar">${elder.name[0].toUpperCase()}</div>
                    <h5 class="mb-1">${elder.name}</h5>
                    <small>${elder.age} years • ${Utils.capitalize(elder.gender)}</small>
                </div>
                <div class="elder-card-body">
                    ${elder.blood_group ? `
                        <div class="elder-info-item">
                            <i class="bi bi-droplet-fill"></i>
                            <span>Blood Group: <strong>${elder.blood_group}</strong></span>
                        </div>` : ''}
                    ${elder.medical_conditions ? `
                        <div class="elder-info-item">
                            <i class="bi bi-heart-pulse"></i>
                            <span>${elder.medical_conditions.substring(0, 50)}${elder.medical_conditions.length > 50 ? '...' : ''}</span>
                        </div>` : ''}
                    ${elder.emergency_contact ? `
                        <div class="elder-info-item">
                            <i class="bi bi-telephone-fill"></i>
                            <span>${elder.emergency_contact}</span>
                        </div>` : ''}
                    <div class="d-flex gap-2 mt-3">
                        <a href="/elders/${elder.id}" class="btn btn-primary btn-sm flex-1">
                            <i class="bi bi-eye me-1"></i>View
                        </a>
                        <button onclick="deleteElder(${elder.id}, '${elder.name}')" class="btn btn-outline-danger btn-sm">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `).join('');
}

// ---- Add Elder Form ----
function initAddElderForm() {
    const form = document.getElementById('add-elder-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = form.querySelector('[type="submit"]');
        setFormLoading(submitBtn, true);

        const formData = {
            name: document.getElementById('name').value.trim(),
            age: parseInt(document.getElementById('age').value),
            gender: document.getElementById('gender').value,
            blood_group: document.getElementById('blood_group').value,
            medical_conditions: document.getElementById('medical_conditions').value.trim(),
            allergies: document.getElementById('allergies').value.trim(),
            emergency_contact: document.getElementById('emergency_contact').value.trim(),
            emergency_contact_name: document.getElementById('emergency_contact_name').value.trim(),
            address: document.getElementById('address').value.trim(),
            notes: document.getElementById('notes').value.trim()
        };

        const data = await API.post('/elders', formData);
        setFormLoading(submitBtn, false);

        if (data && data._ok) {
            Toast.success('Elder profile created successfully!');
            setTimeout(() => { window.location.href = `/elders/${data.elder.id}`; }, 800);
        } else {
            Toast.error(data?.error || 'Failed to create elder profile');
        }
    });
}

// ---- Elder Detail ----
async function loadElderDetail(elderId) {
    const data = await API.get(`/elders/${elderId}/summary`);
    if (!data || !data._ok) {
        Toast.error('Failed to load elder details');
        return;
    }

    renderElderInfo(data.elder);
    renderElderStats(data.stats);
    await loadElderMedicines(elderId);
    await loadElderAdherence(elderId);
    await loadElderSchedules(elderId);
}

function renderElderInfo(elder) {
    const nameEl = document.getElementById('elder-name');
    const subtitleEl = document.getElementById('elder-subtitle');
    const avatarEl = document.getElementById('elder-avatar');

    if (nameEl) nameEl.textContent = elder.name;
    if (subtitleEl) subtitleEl.textContent = `${elder.age} years • ${Utils.capitalize(elder.gender)} • ${elder.blood_group || 'Unknown blood group'}`;
    if (avatarEl) avatarEl.textContent = elder.name[0].toUpperCase();

    const detailsContainer = document.getElementById('elder-details');
    if (detailsContainer) {
        detailsContainer.innerHTML = `
            ${elder.medical_conditions ? `
                <div class="mb-3">
                    <strong class="text-muted small">Medical Conditions</strong>
                    <p class="mb-0">${elder.medical_conditions}</p>
                </div>` : ''}
            ${elder.allergies ? `
                <div class="mb-3">
                    <strong class="text-muted small">Allergies</strong>
                    <p class="mb-0 text-danger">${elder.allergies}</p>
                </div>` : ''}
            ${elder.emergency_contact ? `
                <div class="mb-3">
                    <strong class="text-muted small">Emergency Contact</strong>
                    <p class="mb-0"><i class="bi bi-telephone me-2"></i>${elder.emergency_contact_name || ''} ${elder.emergency_contact}</p>
                </div>` : ''}
            ${elder.address ? `
                <div class="mb-3">
                    <strong class="text-muted small">Address</strong>
                    <p class="mb-0">${elder.address}</p>
                </div>` : ''}
        `;
    }
}

function renderElderStats(stats) {
    const medicinesEl = document.getElementById('stat-medicines');
    const dosesTakenEl = document.getElementById('stat-doses-taken');
    const adherenceEl = document.getElementById('stat-adherence');

    if (medicinesEl) medicinesEl.textContent = stats.active_medicines;
    if (dosesTakenEl) dosesTakenEl.textContent = stats.doses_taken;
    if (adherenceEl) {
        adherenceEl.textContent = `${stats.adherence_rate}%`;
        adherenceEl.className = `adherence-value adherence-${Utils.adherenceColor(stats.adherence_rate)}`;
    }
}

async function loadElderMedicines(elderId) {
    const container = document.getElementById('medicines-list');
    if (!container) return;

    const data = await API.get(`/medicines/elder/${elderId}`);
    if (!data || !data._ok || !data.medicines.length) {
        container.innerHTML = '<p class="text-muted text-center py-3">No medicines prescribed</p>';
        return;
    }

    container.innerHTML = data.medicines.map(med => `
        <div class="medicine-item">
            <div class="medicine-icon"><i class="bi bi-capsule"></i></div>
            <div class="flex-1">
                <div class="fw-600">${med.name}</div>
                <small class="text-muted">${med.dosage} • ${med.frequency}</small>
            </div>
            ${Utils.statusBadge(med.is_active ? 'active' : 'inactive')}
        </div>
    `).join('');
}

async function loadElderAdherence(elderId) {
    const data = await API.get(`/adherence/stats/${elderId}?days=7`);
    if (!data || !data._ok) return;

    const ctx = document.getElementById('adherence-chart');
    if (!ctx) return;

    if (window.elderAdherenceChart) window.elderAdherenceChart.destroy();

    window.elderAdherenceChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.daily_breakdown.map(d => d.day),
            datasets: [
                { label: 'Taken', data: data.daily_breakdown.map(d => d.taken), backgroundColor: '#43a047', borderRadius: 4 },
                { label: 'Missed', data: data.daily_breakdown.map(d => d.total - d.taken), backgroundColor: '#ef5350', borderRadius: 4 }
            ]
        },
        options: {
            responsive: true,
            plugins: { legend: { position: 'top' } },
            scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { stepSize: 1 } } }
        }
    });
}

async function loadElderSchedules(elderId) {
    const container = document.getElementById('schedules-list');
    if (!container) return;

    const data = await API.get(`/schedules/today/${elderId}`);
    if (!data || !data._ok) return;

    if (!data.schedules.length) {
        container.innerHTML = '<p class="text-muted text-center py-3">No schedules for today</p>';
        return;
    }

    container.innerHTML = data.schedules.map(s => `
        <div class="dose-card ${s.adherence_status || 'pending'}">
            <div class="dose-time">${Utils.formatTime(s.scheduled_time)}</div>
            <div class="flex-1">
                <div class="fw-600">${s.medicine_name}</div>
                <small class="text-muted">${s.medicine_dosage} • ${s.meal_timing?.replace('_', ' ')}</small>
            </div>
            <span class="dose-status-badge ${s.adherence_status || 'pending'}">
                ${Utils.capitalize(s.adherence_status || 'pending')}
            </span>
        </div>
    `).join('');
}

// ---- Delete Elder ----
async function deleteElder(elderId, name) {
    if (!confirmAction(`Are you sure you want to deactivate ${name}'s profile?`)) return;

    const data = await API.delete(`/elders/${elderId}`);
    if (data && data._ok) {
        Toast.success('Elder profile deactivated');
        await loadElders();
    } else {
        Toast.error(data?.error || 'Failed to deactivate elder');
    }
}

// ---- Search ----
const searchInput = document.getElementById('elder-search');
if (searchInput) {
    searchInput.addEventListener('input', Utils.debounce((e) => {
        loadElders(e.target.value);
    }, 400));
}

function setFormLoading(btn, loading) {
    if (!btn) return;
    btn.disabled = loading;
    btn.innerHTML = loading
        ? '<span class="spinner-border spinner-border-sm me-2"></span>Saving...'
        : '<i class="bi bi-check-lg me-2"></i>Save Elder Profile';
}
