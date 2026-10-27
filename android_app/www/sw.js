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
