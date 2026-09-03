/**
 * Auto Voice Engine
 * ==================
 * Browser audio is DISABLED.
 * All Telugu voice plays from PC speakers via MCI (voice_scheduler.py).
 * This file only handles:
 *   - Visual popup/toast when reminder arrives via WebSocket
 *   - Taken/Snooze button actions
 *   - Voice commands (optional)
 */
'use strict';

let _currentReminder = null;
let _repeatTimer     = null;
let _currentAudio    = null;

// ── Called by pwa.js when WebSocket 'medicine_reminder' event arrives ─────────
function autoPlayReminder(data) {
    stopCurrentReminder();

    data.medicine_id = data.medicine_id || 0;
    _currentReminder = {
        scheduleId:  data.schedule_id,
        elderId:     data.elder_id,
        medicineId:  data.medicine_id,
        level:       data.level       || 1,
        reminderNum: data.reminder_num || 1,
    };

    // Show visual popup only — NO browser audio
    // PC speakers handle audio via MCI (voice_scheduler.py)
    const level      = data.level       || 1;
    const reminderNum = data.reminder_num || 1;
    const fullscreen  = data.fullscreen || level >= 3 || reminderNum >= 5;

    if (fullscreen || level >= 2 || reminderNum >= 3) {
        showReminderPopup(data, level);
    } else {
        showReminderToast(data, level);
    }
}

function stopCurrentReminder() {
    clearInterval(_repeatTimer);
    _repeatTimer     = null;
    _currentReminder = null;
    if (_currentAudio) {
        try { _currentAudio.pause(); } catch(e) {}
        _currentAudio = null;
    }
}

// ── Visual Popup ──────────────────────────────────────────────────────────────
function showReminderToast(data, level) {
    if (typeof Toast === 'undefined') return;
    const med = data.medicine_name || 'medicine';
    const num = data.reminder_num  || 1;
    const colors = { 1: 'info', 2: 'warning', 3: 'error' };
    Toast.show(`💊 <strong>${med}</strong> — Reminder ${num}/6`,
        colors[level] || 'info', level === 1 ? 15000 : 30000);
}

function showReminderPopup(data, level) {
    document.getElementById('reminder-popup-overlay')?.remove();

    const reminderNum  = data.reminder_num  || 1;
    const maxReminders = data.max_reminders || 6;
    const snoozeOk     = !data.snooze_disabled && reminderNum < maxReminders;
    const colors = { 1: '#1976d2', 2: '#fb8c00', 3: '#e53935' };
    const icons  = { 1: '💊', 2: '⚠️', 3: '🚨' };
    const labels = { 1: 'Medicine Reminder', 2: '⚠️ 2nd Reminder', 3: '🚨 Critical Alert' };
    const isFullscreen = data.fullscreen || level >= 3 || reminderNum >= 5;
    const bg = isFullscreen
        ? 'position:fixed;inset:0;background:rgba(0,0,0,0.92);z-index:99999;display:flex;align-items:center;justify-content:center'
        : 'position:fixed;bottom:24px;right:24px;z-index:9999;max-width:440px';

    document.body.insertAdjacentHTML('beforeend', `
    <div id="reminder-popup-overlay" style="${bg}" role="alertdialog">
      <div style="background:#fff;border-radius:20px;padding:36px;max-width:500px;
                  width:90%;box-shadow:0 20px 60px rgba(0,0,0,0.5);text-align:center;
                  border-top:8px solid ${colors[level]||colors[1]}">
        <div style="font-size:64px;margin-bottom:8px">${icons[level]||icons[1]}</div>
        <div style="background:${colors[level]||colors[1]};color:white;padding:6px 20px;
                    border-radius:20px;font-size:14px;font-weight:700;
                    display:inline-block;margin-bottom:8px">
          ${labels[level]||labels[1]} — ${reminderNum}/${maxReminders}
        </div>
        <h2 style="font-size:26px;font-weight:800;margin:8px 0 4px;color:#1a1a2e">
          ${data.medicine_name||''}
        </h2>
        <p style="font-size:18px;color:#546e7a;margin:0 0 4px">${data.dosage||''}</p>
        <p style="font-size:16px;color:#1976d2;font-weight:700;margin:0 0 16px">
          ⏰ ${data.scheduled_time||''}
        </p>
        <div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap">
          <button onclick="reminderTaken(${data.schedule_id},${data.elder_id},${data.medicine_id||0})"
            style="background:#2e7d32;color:white;border:none;border-radius:14px;
                   padding:14px 28px;font-size:19px;font-weight:700;cursor:pointer;flex:1">
            ✅ Taken
          </button>
          ${snoozeOk ? `
          <button onclick="reminderSnooze(${data.schedule_id},${data.elder_id})"
            style="background:#e65100;color:white;border:none;border-radius:14px;
                   padding:14px 28px;font-size:19px;font-weight:700;cursor:pointer;flex:1">
            ⏰ Snooze 10 min
          </button>` : ''}
        </div>
      </div>
    </div>`);
}

// ── Popup action handlers ─────────────────────────────────────────────────────
async function reminderTaken(scheduleId, elderId, medicineId) {
    stopCurrentReminder();
    document.getElementById('reminder-popup-overlay')?.remove();
    const r = await API.post('/reminders/taken', {
        schedule_id: scheduleId, elder_id: elderId, medicine_id: medicineId
    });
    if (r && r._ok) {
        if (typeof Toast !== 'undefined') Toast.success('✅ Medicine marked as taken!');
        if (typeof loadTodaySchedule === 'function') loadTodaySchedule();
        if (typeof evLoadDoses === 'function') evLoadDoses();
    }
}

async function reminderSnooze(scheduleId, elderId) {
    stopCurrentReminder();
    document.getElementById('reminder-popup-overlay')?.remove();
    const r = await API.post('/reminders/snooze', {
        schedule_id: scheduleId, elder_id: elderId
    });
    if (r && r._ok) {
        const msg = r.snooze_disabled ? '⚠️ Snooze limit reached.' : '⏰ Snoozed for 10 minutes.';
        if (typeof Toast !== 'undefined') Toast.warning(msg);
    }
}

// ── Voice commands (speech-to-text only, no TTS playback) ────────────────────
function startVoiceCommand(lang, onResult, onError) {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { if (onError) onError('Not supported'); return; }
    const rec = new SR();
    rec.lang = lang === 'te' ? 'te-IN' : 'en-IN';
    rec.onresult = async (e) => {
        const text = e.results[0][0].transcript;
        if (onResult) onResult(text, { type: 'chat', text });
    };
    rec.onerror = () => { if (onError) onError('Could not hear'); };
    rec.start();
}

// ── Pending reminder check on page load (visual only) ─────────────────────────
async function checkAndPlayPendingReminders(elderId) {
    if (!elderId || !TokenManager.isLoggedIn()) return;
    try {
        const data = await API.get(`/reminders/active/${elderId}`);
        if (!data || !data._ok || !data.reminders.length) return;
        const top = data.reminders.sort((a, b) => b.reminder_level - a.reminder_level)[0];
        if (!top) return;
        // Show popup only — PC speaker plays audio
        setTimeout(() => {
            showReminderPopup({
                level:          top.reminder_level,
                reminder_num:   top.reminder_level * 2 - 1,
                max_reminders:  6,
                medicine_name:  top.medicine_name  || 'medicine',
                dosage:         top.medicine_dosage || '',
                scheduled_time: top.scheduled_time  || '',
                schedule_id:    top.schedule_id,
                elder_id:       top.elder_id,
                medicine_id:    top.medicine_id    || 0,
                snooze_disabled: top.reminder_level >= 3,
                fullscreen:     top.reminder_level >= 3,
            }, top.reminder_level);
        }, 1000);
    } catch (e) {}
}

// ── Unlock audio (kept for compatibility) ─────────────────────────────────────
function unlockAudio() {}

// ── Exports ───────────────────────────────────────────────────────────────────
window.autoPlayReminder             = autoPlayReminder;
window.stopCurrentReminder          = stopCurrentReminder;
window.checkAndPlayPendingReminders = checkAndPlayPendingReminders;
window.unlockAudio                  = unlockAudio;
window.startVoiceCommand            = startVoiceCommand;
window.showReminderPopup            = showReminderPopup;
window.showReminderToast            = showReminderToast;
window.reminderTaken                = reminderTaken;
window.reminderSnooze               = reminderSnooze;
