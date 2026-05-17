// Bump this version whenever you deploy updates — it forces old caches to clear
const CACHE_NAME = 'weatherguard-v2';

self.addEventListener('install', (event) => {
  // Skip waiting immediately so the new SW activates right away
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  // Delete ALL old caches (any version other than current)
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET requests
  if (event.request.method !== 'GET') return;

  // Network-first for API calls and HTML navigation requests
  // This ensures the user always gets fresh HTML and API data
  if (
    url.pathname.startsWith('/api') ||
    event.request.mode === 'navigate' ||
    url.pathname.endsWith('.html')
  ) {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          // Only cache successful responses
          if (res && res.status === 200) {
            const cloned = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, cloned));
          }
          return res;
        })
        .catch(() => caches.match(event.request)) // Fallback to cache if offline
    );
    return;
  }

  // Network-first for JS/CSS/assets too (fetch fresh, cache as backup)
  event.respondWith(
    fetch(event.request)
      .then((res) => {
        if (res && res.status === 200) {
          const cloned = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, cloned));
        }
        return res;
      })
      .catch(() => caches.match(event.request)) // Fallback to cache if offline
  );
});
