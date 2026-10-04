const CACHE = 'malaeb-shell-v1';
const SHELL = ['/', '/index.html', '/booking.html', '/map.html', '/display.html', '/owner.html', '/style.css', '/script.js', '/manifest.webmanifest', '/icons/icon-192.png', '/icons/icon-512.png', '/privacy.html', '/terms.html'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
  if (event.request.method !== 'GET') return;
  event.respondWith(fetch(event.request).then(response => {
    if (response.ok && (event.request.mode === 'navigate' || SHELL.includes(url.pathname))) {
      const copy = response.clone(); caches.open(CACHE).then(cache => cache.put(event.request, copy));
    }
    return response;
  }).catch(() => caches.match(event.request).then(cached => cached || caches.match('/index.html'))));
});
