// Pi Dashboard — Service Worker v1.0
// Push bildirimleri + temel PWA desteği

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(clients.claim()));

// ── Push bildirimi geldiğinde ──────────────────────
self.addEventListener('push', e => {
    let data = { title: '⏰ Pi Dashboard', body: 'Yeni hatırlatıcı' };
    try { data = e.data.json(); } catch {}

    e.waitUntil(
        self.registration.showNotification(data.title, {
            body:      data.body,
            icon:      '/static/icon.png',
            badge:     '/static/icon.png',
            vibrate:   [200, 100, 200],
            tag:       'pi-reminder',
            renotify:  true,
            requireInteraction: false,
        })
    );
});

// ── Bildirime tıklanınca uygulamayı öne getir ─────
self.addEventListener('notificationclick', e => {
    e.notification.close();
    e.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
            for (const c of list) {
                if ('focus' in c) return c.focus();
            }
            if (clients.openWindow) return clients.openWindow('/');
        })
    );
});
