/**
 * PWA + Push + WebSocket + Voice Auto-Play
 * ==========================================
 * This file handles:
 *   1. Service Worker registration
 *   2. Push notification subscription (Web Push API - free, no Firebase)
 *   3. WebSocket connection (Flask-SocketIO)
 *   4. Automatic voice playback on medicine_reminder event
 *   5. Full-screen popup for Level 3 reminders
 *   6. Real-time dashboard updates
 */

// ── 1. Service Worker Registration ───────────────────────────────────────────
async function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) {
    console.warn('Service Worker not supported');
    return null;
  }
  try {
    const reg = await navigator.serviceWorker.register('/static/sw.js', { scope: '/' });
    console.log('Service Worker registered:', reg.scope);

    // Listen for token requests from SW
    navigator.serviceWorker.addEventListener('message', (event) => {
      if (event.data && event.data.type === 'GET_TOKEN') {
        const token = TokenManager.getAccessToken();
        event.ports[0].postMessage({ token });
      }
    });

    return reg;
  } catch (e) {
    console.error('SW registration failed:', e);
    return null;
  }
}

// ── 2. Push Notification Subscription ────────────────────────────────────────
async function subscribeToPush() {
  if (!('PushManager' in window)) {
    console.warn('Push API not supported');
    return false;
  }

  try {
    // Request notification permission
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      Toast.warning('Enable notifications to receive medicine reminders automatically.');
      return false;
    }

    const reg = await navigator.serviceWorker.ready;

    // Get VAPID public key from server
    const keyResp = await API.get('/push/vapid-public-key');
    if (!keyResp || !keyResp.public_key) {
      console.warn('No VAPID key — push notifications disabled');
      return false;
    }

    const applicationServerKey = _urlB64ToUint8Array(keyResp.public_key);

    // Subscribe
    const subscription = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey,
    });

    // Send subscription to server
    await API.post('/push/subscribe', { subscription: subscription.toJSON() });
    console.log('Push subscription saved');
    Toast.success('🔔 Medicine reminders enabled! You will receive alerts automatically.');
    return true;

  } catch (e) {
    console.error('Push subscription failed:', e);
    return false;
  }
}

// ── 3. WebSocket Connection (Real-Time Updates) ───────────────────────────────
let _socket = null;

function initWebSocket() {
  if (typeof io === 'undefined') {
    console.warn('Socket.IO not loaded');
    return;
  }

  _socket = io({
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionDelay: 2000,
    reconnectionAttempts: 10,
  });

  _socket.on('connect', () => {
    console.log('✅ WebSocket connected');

    // Get current user
    const user = TokenManager.getUser();
    if (user) {
      // Join rooms for current user so reminder events reach the active page
      _socket.emit('join_room', { room: `caretaker_${user.id}` });
      _socket.emit('join_room', { room: `elder_${user.id}` });
      console.log(`✅ Joined caretaker_${user.id} and elder_${user.id} rooms`);

      // Join ALL elder rooms so reminders auto-play without manual selection
      API.get('/elders?per_page=100').then(data => {
        if (data && data._ok && data.elders && data.elders.length) {
          console.log(`📋 Found ${data.elders.length} elder(s), joining rooms...`);
          data.elders.forEach(e => {
            _socket.emit('join_room', { room: `elder_${e.id}` });
            console.log(`  ✅ Joined elder_${e.id} room (${e.name})`);
            // Log scheduled reminders for this elder (diagnostic)
            API.get(`/schedules/today/${e.id}`).then(sd => {
              if (sd && sd._ok && sd.schedules && sd.schedules.length) {
                const upcoming = sd.schedules.map(s => `${s.medicine_name} at ${s.scheduled_time}`).join('; ');
                console.log(`📅 Reminder Scheduled for elder_${e.id}: ${upcoming}`);
              }
            }).catch(() => {});
          });
        }
      }).catch(e => console.warn('Failed to get elders:', e));
    }
  });

  _socket.on('disconnect', () => {
    console.warn('⚠️ WebSocket disconnected - reminders will be delayed until reconnection');
  });

  _socket.on('reconnect', () => {
    console.log('🔄 WebSocket reconnected, rejoin rooms...');
  });

  // ── Medicine Reminder (auto-play voice + show popup) ──────────────────────
  _socket.on('medicine_reminder', (data) => {
    console.log('🔔 Received medicine_reminder via WebSocket:', {
      elder: data.elder_name,
      medicine: data.medicine_name,
      level: data.level,
      reminder: data.reminder_num,
      has_text_te: !!data.text_te,
      has_text_en: !!data.text_en,
      has_audio_url: !!data.audio_url_te,
      has_voice_mod: !!data.voice_mod
    });
    console.log('📣 Reminder Triggered:', `${data.medicine_name} for ${data.elder_name} at ${data.scheduled_time} (R${data.reminder_num})`);
    
    // Ensure audio context is unlocked
    if (typeof unlockAudio === 'function') {
      console.log('🔓 Unlocking audio...');
      unlockAudio();
    }
    
    // Call autoPlayReminder (imported from auto_voice.js)
    if (typeof autoPlayReminder === 'function') {
      console.log('✅ Calling autoPlayReminder from auto_voice.js');
      try {
        autoPlayReminder(data);
      } catch(err) {
        console.error('❌ autoPlayReminder error:', err);
        // Fallback
        if (typeof handleMedicineReminder === 'function') {
          console.log('🔄 Fallback to handleMedicineReminder');
          handleMedicineReminder(data);
        }
      }
    } else {
      console.warn('⚠️ autoPlayReminder not found, using fallback');
      if (typeof handleMedicineReminder === 'function') {
        handleMedicineReminder(data);
      }
    }
  });

  // ── Live adherence update (no page refresh needed) ────────────────────────
  _socket.on('adherence_update', (data) => {
    console.log('✅ Adherence update:', data);
    Toast.info(`✅ ${data.elder_name}: ${data.medicine_name} marked as ${data.status}`);
    // Refresh dashboard table if on dashboard page
    if (typeof loadTodaySchedule === 'function') loadTodaySchedule();
    if (typeof loadStats === 'function') loadStats();
  });

  // ── New alert (live bell badge update) ────────────────────────────────────
  _socket.on('alert_update', (data) => {
    console.log('🚨 Alert update:', data);
    loadAlertsBadge();
    if (typeof loadRecentAlerts === 'function') loadRecentAlerts();
    // Browser notification for new alert
    if (Notification.permission === 'granted' && data.severity === 'critical') {
      new Notification('🚨 Critical Alert', {
        body: data.message,
        icon: '/static/icons/icon-192.png',
        requireInteraction: true,
      });
    }
  });

  // ── Dashboard refresh ─────────────────────────────────────────────────────
  _socket.on('dashboard_refresh', () => {
    if (typeof loadDashboardData === 'function') loadDashboardData();
  });
}

// ── 4. Voice Auto-Play ────────────────────────────────────────────────────────
let _currentUtterance = null;
let _level3Interval = null;

function handleMedicineReminder(data) {
  const level = data.level || 1;
  const hasTeluguPayload = Boolean(data.text_te || data.audio_url_te);
  const lang = hasTeluguPayload ? 'te' : (localStorage.getItem('preferred_lang') || 'te');
  const text = lang === 'te' ? data.text_te : data.text_en;

  // Stop any current speech
  _stopCurrentVoice();

  // Auto-play voice immediately
  _speakReminder(text, level, lang);

  // Show popup
  if (level >= 2) {
    showReminderPopup(data, level);
  } else {
    showReminderToast(data, level);
  }

  // Level 3: repeat voice every 60 seconds until acknowledged
  if (level === 3) {
    _level3Interval = setInterval(() => {
      if (_getReminderPopup()) {
        _speakReminder(text, level, lang);
      } else {
        clearInterval(_level3Interval);
      }
    }, 60000);
  }
}

function _speakReminder(text, level, lang) {
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();

  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = lang === 'te' ? 'te-IN' : 'en-IN';
  utter.rate = level === 1 ? 0.75 : level === 2 ? 0.85 : 0.95;
  utter.pitch = level === 3 ? 1.2 : 1.0;
  utter.volume = level === 1 ? 0.8 : 1.0;

  // Select best voice for language
  const voices = window.speechSynthesis.getVoices();
  const preferred = voices.find(v =>
    v.lang === (lang === 'te' ? 'te-IN' : 'en-IN')
  ) || voices.find(v => v.lang.startsWith(lang === 'te' ? 'te' : 'en'));
  if (preferred) utter.voice = preferred;

  _currentUtterance = utter;
  window.speechSynthesis.speak(utter);
}

function _stopCurrentVoice() {
  window.speechSynthesis?.cancel();
  clearInterval(_level3Interval);
  _currentUtterance = null;
}

// ── 5. Reminder Popups ────────────────────────────────────────────────────────
function showReminderToast(data, level) {
  const colors = { 1: 'info', 2: 'warning', 3: 'error' };
  Toast.show(
    `💊 <strong>${data.medicine_name}</strong> ${data.dosage} — ${data.scheduled_time}`,
    colors[level] || 'info',
    level === 1 ? 15000 : 30000
  );
}

function showReminderPopup(data, level) {
  // Remove existing popup
  document.getElementById('reminder-popup-overlay')?.remove();

  const isFullscreen = level === 3 || data.fullscreen;
  const hasTeluguPayload = Boolean(data.text_te || data.audio_url_te);
  const lang = hasTeluguPayload ? 'te' : (localStorage.getItem('preferred_lang') || 'te');
  const reminderText = (lang === 'te' ? data.text_te : data.text_en)
    || `Time to take ${data.medicine_name || 'medicine'} ${data.dosage || ''}.`;

  const levelColors = { 2: '#fb8c00', 3: '#e53935' };
  const levelLabels = { 2: '⚠️ Second Reminder', 3: '🚨 CRITICAL ALERT' };
  const bg = isFullscreen
    ? 'position:fixed;inset:0;background:rgba(0,0,0,0.92);z-index:99999;display:flex;align-items:center;justify-content:center'
    : 'position:fixed;bottom:24px;right:24px;z-index:9999;max-width:420px';

  const html = `
  <div id="reminder-popup-overlay" style="${bg}" role="alertdialog" aria-modal="true">
    <div style="background:#fff;border-radius:20px;padding:36px;max-width:500px;width:90%;
                box-shadow:0 20px 60px rgba(0,0,0,0.5);text-align:center;
                border-top:8px solid ${levelColors[level] || '#1976d2'}">

      <!-- Icon -->
      <div style="font-size:64px;margin-bottom:16px">${level === 3 ? '🚨' : '💊'}</div>

      <!-- Level Badge -->
      <div style="background:${levelColors[level] || '#1976d2'};color:white;
                  padding:6px 20px;border-radius:20px;font-size:14px;
                  font-weight:700;display:inline-block;margin-bottom:16px">
        ${levelLabels[level] || 'Medicine Reminder'}
      </div>

      <!-- Medicine Info -->
      <h2 style="font-size:28px;font-weight:800;margin:0 0 8px;color:#1a1a2e">
        ${data.medicine_name}
      </h2>
      <p style="font-size:20px;color:#546e7a;margin:0 0 8px">${data.dosage}</p>
      <p style="font-size:18px;color:#1976d2;font-weight:700;margin:0 0 20px">
        ⏰ Scheduled: ${data.scheduled_time}
      </p>

      <!-- Reminder Text -->
      <div style="background:#f5f5f5;border-radius:12px;padding:16px;margin-bottom:24px;
                  font-size:16px;color:#333;line-height:1.6;text-align:left">
        ${reminderText}
      </div>

      <!-- Action Buttons -->
      <div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap">
        <button onclick="reminderTaken(${data.schedule_id},${data.elder_id},${data.medicine_id || 0})"
          style="background:#2e7d32;color:white;border:none;border-radius:14px;
                 padding:16px 32px;font-size:20px;font-weight:700;cursor:pointer;
                 min-width:150px;flex:1">
          ✅ Taken
        </button>
        ${!data.snooze_disabled ? `
        <button onclick="reminderSnooze(${data.schedule_id},${data.elder_id})"
          style="background:#e65100;color:white;border:none;border-radius:14px;
                 padding:16px 32px;font-size:20px;font-weight:700;cursor:pointer;
                 min-width:150px;flex:1">
          ⏰ Snooze 10 min
        </button>` : ''}
      </div>

      <!-- Re-play voice button -->
      <button onclick="_speakReminder('${reminderText.replace(/'/g, "\\'")}', ${level}, '${lang}')"
        style="background:none;border:1px solid #ccc;border-radius:10px;
               padding:10px 20px;font-size:16px;cursor:pointer;margin-top:16px;color:#546e7a">
        🔊 Play Again
      </button>
    </div>
  </div>`;

  document.body.insertAdjacentHTML('beforeend', html);
}

function _getReminderPopup() {
  return document.getElementById('reminder-popup-overlay');
}

async function reminderTaken(scheduleId, elderId, medicineId) {
  _stopCurrentVoice();
  if (typeof stopCurrentReminder === 'function') stopCurrentReminder();
  document.getElementById('reminder-popup-overlay')?.remove();
  const data = await API.post('/reminders/taken', {
    schedule_id: scheduleId, elder_id: elderId, medicine_id: medicineId
  });
  if (data && data._ok) {
    Toast.success('✅ Medicine marked as taken!');
    if (typeof loadTodaySchedule === 'function') loadTodaySchedule();
    if (typeof evLoadDoses === 'function') evLoadDoses();
  }
}

async function reminderSnooze(scheduleId, elderId) {
  _stopCurrentVoice();
  if (typeof stopCurrentReminder === 'function') stopCurrentReminder();
  document.getElementById('reminder-popup-overlay')?.remove();
  const data = await API.post('/reminders/snooze', {
    schedule_id: scheduleId, elder_id: elderId
  });
  if (data && data._ok) {
    const msg = data.snooze_disabled
      ? '⚠️ Maximum snoozes reached — escalating to critical.'
      : '⏰ Snoozed for 10 minutes.';
    Toast.warning(msg);
  }
}

// ── 6. Language Preference ────────────────────────────────────────────────────
function setReminderLanguage(lang) {
  localStorage.setItem('preferred_lang', lang);
  Toast.info(lang === 'te' ? '🗣️ Telugu selected for voice reminders' : '🗣️ English selected');
}

// ── 7. Utility ────────────────────────────────────────────────────────────────
function _urlB64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  return Uint8Array.from([...raw].map(c => c.charCodeAt(0)));
}

// ── 8. Init (called on every page load) ──────────────────────────────────────
async function initPWA() {
  if (!TokenManager.isLoggedIn()) return;

  // Register Service Worker
  const swReg = await registerServiceWorker();

  // Connect WebSocket
  initWebSocket();

  // Pre-load voices for TTS
  window.speechSynthesis?.getVoices();
  window.speechSynthesis?.addEventListener('voiceschanged', () => {
    window.speechSynthesis.getVoices();
  });

  // Preload Telugu MP3 buffers (best-effort)
  try { if (typeof preloadTeluguMP3s === 'function') preloadTeluguMP3s(); } catch(e) { console.warn('Preload MP3s failed', e); }

  // Auto-subscribe to push if permission already granted
  if (Notification.permission === 'granted' && swReg) {
    subscribeToPush().catch(console.warn);
  }

  // Show "Enable Notifications" prompt if not yet asked
  if (Notification.permission === 'default') {
    setTimeout(() => {
      const banner = document.createElement('div');
      banner.id = 'notif-banner';
      banner.style.cssText = `
        position:fixed;bottom:0;left:0;right:0;z-index:9998;
        background:#1565c0;color:white;padding:14px 20px;
        display:flex;align-items:center;justify-content:space-between;
        font-size:15px;box-shadow:0 -4px 16px rgba(0,0,0,0.2)`;
      banner.innerHTML = `
        <span>🔔 Enable notifications to receive medicine reminders when the app is not open</span>
        <div style="display:flex;gap:8px;margin-left:16px;flex-shrink:0">
          <button onclick="subscribeToPush().then(()=>document.getElementById('notif-banner').remove())"
            style="background:white;color:#1565c0;border:none;border-radius:8px;
                   padding:8px 16px;font-size:14px;font-weight:700;cursor:pointer">
            Enable
          </button>
          <button onclick="document.getElementById('notif-banner').remove()"
            style="background:rgba(255,255,255,0.2);color:white;border:none;
                   border-radius:8px;padding:8px 12px;cursor:pointer">✕</button>
        </div>`;
      document.body.appendChild(banner);
    }, 3000);
  }
}

// ── Initialize PWA on page load ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  console.log('✅ DOMContentLoaded: Initializing PWA...');
  // Initialize WebSocket if we're on a page that needs it
  if (typeof initWebSocket === 'function') {
    console.log('✅ Calling initWebSocket...');
    initWebSocket();
  }
  // Try to register service worker
  if (typeof registerServiceWorker === 'function') {
    console.log('✅ Registering Service Worker...');
    registerServiceWorker().catch(e => console.warn('SW registration optional:', e));
  }
  // Show notification banner if needed
  setTimeout(() => {
    if (typeof showNotificationBanner === 'function') {
      console.log('✅ Showing notification banner...');
      showNotificationBanner();
    }
  }, 500);
});

// Also initialize on window load as fallback
window.addEventListener('load', () => {
  console.log('✅ Window load: PWA re-check');
  // Double-check socket is connected
  if (typeof initWebSocket === 'function' && (!window._socket || !window._socket.connected)) {
    console.log('✅ WebSocket not connected, attempting to initialize...');
    initWebSocket();
  }
});
