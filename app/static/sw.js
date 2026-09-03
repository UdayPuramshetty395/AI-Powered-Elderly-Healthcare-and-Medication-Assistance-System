/**
 * Service Worker — ElderCare PWA
 * ================================
 * Handles:
 *  1. Push notifications (even when browser is closed/minimized)
 *  2. Notification click actions (Taken / Snooze)
 *  3. Background sync for offline dose confirmations
 *  4. Cache-first strategy for app shell
 */

const CACHE_NAME = 'eldercare-v1';
const APP_SHELL = [
  '/',
  '/dashboard',
  '/elder-view',
  '/static/css/style.css',
  '/static/js/main.js',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
];

// ── Install: cache app shell ──────────────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

// ── Activate: clean old caches ────────────────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// ── Fetch: cache-first for static, network-first for API ─────────────────────
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/socket.io/')) {
    return; // Never cache API calls
  }
  event.respondWith(
    caches.match(event.request)
      .then(cached => cached || fetch(event.request)
        .then(response => {
          if (response && response.status === 200 && event.request.method === 'GET') {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(c => c.put(event.request, clone));
          }
          return response;
        })
      )
  );
});

// ── Push: receive and display notification ────────────────────────────────────
self.addEventListener('push', (event) => {
  if (!event.data) return;

  let payload;
  try {
    payload = event.data.json();
  } catch {
    payload = { title: 'Medicine Reminder', body: event.data.text() };
  }

  const title = payload.title || '💊 Medicine Reminder';
  const options = {
    body: payload.body || 'Time to take your medicine.',
    icon: payload.icon || '/static/icons/icon-192.png',
    badge: payload.badge || '/static/icons/badge-72.png',
    tag: payload.tag || 'medicine-reminder',
    requireInteraction: payload.requireInteraction || false,
    vibrate: [200, 100, 200, 100, 200],
    data: payload.data || {},
    actions: payload.actions || [
      { action: 'taken', title: '✅ Taken', icon: '/static/icons/icon-72.png' },
      { action: 'snooze', title: '⏰ Snooze 10 min', icon: '/static/icons/icon-72.png' },
    ],
  };

  // For critical Level 3: auto-repeat every 60s
  if (payload.data && payload.data.level === 3) {
    options.requireInteraction = true;
    options.vibrate = [500, 200, 500, 200, 500, 200, 500];
    options.silent = false;
  }

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// ── Notification click: handle Taken / Snooze actions ────────────────────────
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const data = event.notification.data || {};
  const action = event.action;
  const scheduleId = data.schedule_id;
  const elderId = data.elder_id;
  const medicineId = data.medicine_id;

  if (action === 'taken' && scheduleId && elderId) {
    // Mark dose as taken in background
    event.waitUntil(
      _markTaken(scheduleId, elderId, medicineId)
        .then(() => _openOrFocusApp('/elder-view'))
    );
  } else if (action === 'snooze' && scheduleId && elderId) {
    event.waitUntil(
      _snoozeReminder(scheduleId, elderId)
        .then(() => {
          self.registration.showNotification('⏰ Snoozed 10 Minutes', {
            body: `Reminder snoozed. You will be reminded again in 10 minutes.`,
            icon: '/static/icons/icon-192.png',
            tag: 'snooze-confirm',
          });
        })
    );
  } else {
    // Default: open app
    event.waitUntil(_openOrFocusApp(data.url || '/elder-view'));
  }
});

// ── Background sync: retry failed adherence posts ────────────────────────────
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-adherence') {
    event.waitUntil(_syncPendingAdherence());
  }
});

// ── Helpers ───────────────────────────────────────────────────────────────────

async function _markTaken(scheduleId, elderId, medicineId) {
  try {
    const token = await _getAuthToken();
    if (!token) return;
    await fetch('/api/reminders/taken', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        schedule_id: scheduleId,
        elder_id: elderId,
        medicine_id: medicineId || 0,
      }),
    });
  } catch (e) {
    // Queue for background sync
    const db = await _openDB();
    const tx = db.transaction('pending_adherence', 'readwrite');
    tx.objectStore('pending_adherence').put({
      schedule_id: scheduleId, elder_id: elderId,
      medicine_id: medicineId, status: 'taken', ts: Date.now()
    });
  }
}

async function _snoozeReminder(scheduleId, elderId) {
  try {
    const token = await _getAuthToken();
    if (!token) return;
    await fetch('/api/reminders/snooze', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ schedule_id: scheduleId, elder_id: elderId }),
    });
  } catch (e) {
    console.error('Snooze failed:', e);
  }
}

async function _syncPendingAdherence() {
  const db = await _openDB();
  const tx = db.transaction('pending_adherence', 'readonly');
  const store = tx.objectStore('pending_adherence');
  const items = await new Promise(r => {
    const req = store.getAll();
    req.onsuccess = () => r(req.result);
  });
  const token = await _getAuthToken();
  if (!token || !items.length) return;
  for (const item of items) {
    try {
      await fetch('/api/reminders/taken', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify(item),
      });
      const delTx = db.transaction('pending_adherence', 'readwrite');
      delTx.objectStore('pending_adherence').delete(item.id);
    } catch (e) { /* retry next sync */ }
  }
}

async function _getAuthToken() {
  const clients = await self.clients.matchAll();
  // Try to get token from client
  for (const client of clients) {
    const result = await new Promise(resolve => {
      const channel = new MessageChannel();
      channel.port1.onmessage = (e) => resolve(e.data);
      client.postMessage({ type: 'GET_TOKEN' }, [channel.port2]);
      setTimeout(() => resolve(null), 500);
    });
    if (result && result.token) return result.token;
  }
  return null;
}

async function _openOrFocusApp(url) {
  const clients = await self.clients.matchAll({ type: 'window' });
  for (const client of clients) {
    if (client.url.includes(self.registration.scope)) {
      await client.focus();
      client.navigate(url);
      return;
    }
  }
  await self.clients.openWindow(url);
}

function _openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('eldercare', 1);
    req.onupgradeneeded = (e) => {
      e.target.result.createObjectStore('pending_adherence',
        { keyPath: 'id', autoIncrement: true });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
