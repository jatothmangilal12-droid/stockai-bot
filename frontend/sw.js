// StockAI Service Worker
const CACHE_NAME = 'stockai-cache-v1';
const ASSETS = [
  '/',
  'css/style.css',
  'js/app.js',
  'js/charts.js',
  'manifest.json'
];


self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) return caches.delete(key);
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  // Let API requests bypass cache
  if (e.request.url.includes('/api/') || e.request.url.includes('/ws')) {
    return;
  }
  e.respondWith(
    caches.match(e.request).then((res) => res || fetch(e.request)).catch(() => fetch(e.request))
  );
});

// Push Notification Event Listener (Web Push)
self.addEventListener('push', (e) => {
  let data = { title: '🚨 StockAI Breakout Alert', body: 'New intraday breakout trade setup detected!', url: '/#view-ai-trade' };
  try {
    if (e.data) {
      data = Object.assign(data, e.data.json());
    }
  } catch (err) {}

  const options = {
    body: data.body,
    icon: '/assets/icon.png',
    badge: '/favicon.png',
    vibrate: [300, 100, 300, 100, 500],
    tag: 'stockai-breakout-alert',
    renotify: true,
    requireInteraction: true,
    data: data.url || '/#view-ai-trade'
  };

  e.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Notification Click Event Listener
self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const targetUrl = e.notification.data || '/#view-ai-trade';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ('focus' in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
