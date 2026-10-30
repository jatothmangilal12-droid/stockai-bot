// StockAI Service Worker
const CACHE_NAME = 'stockai-cache-v2';
const ASSETS = [
  '/',
  'css/style.css',
  'js/app.js',
  'js/charts.js',
  'manifest.json'
];

self.addEventListener('install', (e) => {
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
  // Let API requests and WebSockets bypass cache completely
  if (e.request.url.includes('/api/') || e.request.url.includes('/ws')) {
    return;
  }
  // Network-First strategy: Always fetch newest version from network, fallback to cache if offline
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        if (res && res.status === 200 && e.request.method === 'GET') {
          const resClone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(e.request, resClone));
        }
        return res;
      })
      .catch(() => caches.match(e.request))
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
