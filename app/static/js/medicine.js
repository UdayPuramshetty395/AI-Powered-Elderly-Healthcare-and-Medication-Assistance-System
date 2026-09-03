/**
 * Medicine JS - Medicine management
 */

document.addEventListener('DOMContentLoaded', () => {
    if (!requireAuth()) return;
    const path = window.location.pathname;
    if (path === '/medicines') loadMedicines();
    else if (path === '/medicines/add') initAddMedicineForm();
});

async function loadMedicines() {
    showTableLoading('medicines-tbody', 9);
    const elderId = document.getElementById('filter-elder')?.value || '';
    const status = document.getElementById('filter-status')?.value || '';
    let endpoint = '/medicines?per_page=50';
    if (elderId) endpoint += `&elder_id=${elderId}`;
    if (status) endpoint += `&is_active=${status}`;

    const data = await API.get(endpoint);
    if (!data || !data._ok) {
        showTableEmpty('medicines-tbody', 9, 'Failed to load medicines');
        return;
    }

    const tbody = document.getElementById('medicines-tbody');
    if (!data.medicines.length) {
        showTableEmpty('medicines-tbody', 9, 'No medicines found');
        return;
    }

    tbody.innerHTML = data.medicines.map((m, idx) => `
        <tr>
            <td>${idx + 1}</td>
            <td>
                <div class="fw-600">${m.name}</div>
                ${m.generic_name ? `<small class="text-muted">${m.generic_name}</small>` : ''}
            </td>
            <td>${m.elder_name || '—'}</td>
            <td><span class="badge bg-light text-dark border">${m.dosage}</span></td>
            <td>${m.frequency}</td>
            <td><span class="badge bg-info-subtle text-info">${m.route}</span></td>
            <td>${Utils.formatDate(m.start_date)}</td>
            <td>${Utils.statusBadge(m.is_active ? 'active' : 'inactive')}</td>
            <td>
                <div class="d-flex gap-1">
                    <button onclick="toggleMedicineStatus(${m.id}, ${m.is_active})" 
                            class="btn btn-sm ${m.is_active ? 'btn-outline-danger' : 'btn-outline-success'}" 
                            title="${m.is_active ? 'Deactivate' : 'Activate'}">
                        <i class="bi bi-${m.is_active ? 'pause-circle' : 'play-circle'}"></i>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

function initAddMedicineForm() {
    loadEldersDropdown();

    const form = document.getElementById('add-medicine-form');
    if (!form) return;

    // Default start date to today
    const startDateInput = document.getElementById('start_date');
    if (startDateInput) startDateInput.value = new Date().toISOString().split('T')[0];

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = document.getElementById('submit-btn');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Adding...';

        const payload = {
            elder_id: parseInt(document.getElementById('elder_id').value),
            name: document.getElementById('name').value.trim(),
            generic_name: document.getElementById('generic_name').value.trim(),
            dosage: document.getElementById('dosage').value.trim(),
            frequency: document.getElementById('frequency').value,
            route: document.getElementById('route').value,
            start_date: document.getElementById('start_date').value || null,
            end_date: document.getElementById('end_date').value || null,
            prescribed_by: document.getElementById('prescribed_by').value.trim(),
            purpose: document.getElementById('purpose').value.trim(),
            instructions: document.getElementById('instructions').value.trim(),
            side_effects: document.getElementById('side_effects').value.trim()
        };

        if (!payload.elder_id || !payload.name || !payload.dosage || !payload.frequency) {
            Toast.error('Please fill in all required fields');
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="bi bi-plus-lg me-2"></i>Add Medicine';
            return;
        }

        const data = await API.post('/medicines', payload);
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="bi bi-plus-lg me-2"></i>Add Medicine';

        if (data && data._ok) {
            Toast.success('Medicine added successfully!');
            setTimeout(() => { window.location.href = '/medicines'; }, 800);
        } else {
            Toast.error(data?.error || 'Failed to add medicine');
        }
    });
}

async function loadEldersDropdown() {
    const select = document.getElementById('elder_id') || document.getElementById('filter-elder');
    if (!select) return;

    const data = await API.get('/elders?per_page=100');
    if (!data || !data._ok) return;

    const options = data.elders.map(e => `<option value="${e.id}">${e.name} (Age ${e.age})</option>`).join('');
    if (select.id === 'elder_id') {
        select.innerHTML = '<option value="">Choose an elder...</option>' + options;
    } else {
        select.innerHTML = '<option value="">All Elders</option>' + options;
    }

    // Auto-select if only one elder exists
    const realOptions = data.elders;
    if (realOptions.length === 1) {
        select.value = realOptions[0].id;
        select.dispatchEvent(new Event('change'));
    }
}

async function toggleMedicineStatus(medicineId, currentStatus) {
    const action = currentStatus ? 'deactivate' : 'activate';
    if (!confirmAction(`${Utils.capitalize(action)} this medicine?`)) return;

    const data = await API.put(`/medicines/${medicineId}`, { is_active: !currentStatus });
    if (data && data._ok) {
        Toast.success(`Medicine ${action}d`);
        loadMedicines();
    } else {
        Toast.error(data?.error || 'Failed to update medicine');
    }
}

// Search and filter
document.getElementById('medicine-search')?.addEventListener('input', Utils.debounce(loadMedicines, 400));
document.getElementById('filter-elder')?.addEventListener('change', loadMedicines);
document.getElementById('filter-status')?.addEventListener('change', loadMedicines);

// Load elder dropdown for filter on list page
if (window.location.pathname === '/medicines') {
    document.addEventListener('DOMContentLoaded', loadEldersDropdown);
}
