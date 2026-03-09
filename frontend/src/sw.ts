/// <reference lib="webworker" />
import { cleanupOutdatedCaches, precacheAndRoute } from 'workbox-precaching'
import { clientsClaim } from 'workbox-core'
import { registerRoute } from 'workbox-routing'
import { NetworkOnly, CacheFirst, NetworkFirst } from 'workbox-strategies'
import { ExpirationPlugin } from 'workbox-expiration'

declare let self: ServiceWorkerGlobalScope

// ── Precaching (injected by vite-plugin-pwa) ─────────────────────────────
cleanupOutdatedCaches()
precacheAndRoute(self.__WB_MANIFEST)

// Skip waiting and claim clients immediately
self.skipWaiting()
clientsClaim()

// ── Cache-first for static assets (fonts, images, icons) ─────────────────
registerRoute(
  ({ request, url }) =>
    request.destination === 'image' ||
    request.destination === 'font' ||
    url.pathname.startsWith('/icons/'),
  new CacheFirst({
    cacheName: 'static-assets',
    plugins: [
      new ExpirationPlugin({ maxEntries: 100, maxAgeSeconds: 30 * 24 * 60 * 60 }),
    ],
  })
)

// ── Network-first for navigations (HTML pages) ───────────────────────────
registerRoute(
  ({ request }) => request.mode === 'navigate',
  new NetworkFirst({
    cacheName: 'pages',
    plugins: [
      new ExpirationPlugin({ maxEntries: 20, maxAgeSeconds: 7 * 24 * 60 * 60 }),
    ],
  })
)

// ── Network-first for API routes (offline fallback to cached responses) ──
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/'),
  new NetworkFirst({
    cacheName: 'api-cache',
    plugins: [
      new ExpirationPlugin({ maxEntries: 200, maxAgeSeconds: 24 * 60 * 60 }),
    ],
  })
)

// ── Network-only for WebSocket routes ────────────────────────────────────
registerRoute(
  ({ url }) => url.pathname.startsWith('/ws'),
  new NetworkOnly()
)

// ── Offline fallback ─────────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(async () => {
        const cached = await caches.match('/offline.html')
        if (cached) return cached
        return new Response(
          `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="theme-color" content="#0f172a">
  <title>O-Brain — Offline</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0f172a; color: #e2e8f0;
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh; padding: 2rem;
    }
    .container { text-align: center; max-width: 400px; }
    .icon { font-size: 4rem; margin-bottom: 1.5rem; }
    h1 { font-size: 1.5rem; font-weight: 700; margin-bottom: 0.5rem; }
    p { color: #94a3b8; font-size: 0.875rem; line-height: 1.6; margin-bottom: 1.5rem; }
    button {
      background: #7c3aed; color: white; border: none;
      padding: 0.75rem 1.5rem; border-radius: 0.5rem;
      font-size: 0.875rem; font-weight: 600; cursor: pointer;
    }
    button:hover { background: #6d28d9; }
  </style>
</head>
<body>
  <div class="container">
    <div class="icon">🧠</div>
    <h1>You're offline</h1>
    <p>Some features may be limited. Check your connection and try again.</p>
    <button onclick="location.reload()">Try Again</button>
  </div>
</body>
</html>`,
          { headers: { 'Content-Type': 'text/html' } }
        )
      }),
    )
  }
})

// ── Push notification handler ────────────────────────────────────────────
self.addEventListener('push', (event) => {
  if (!event.data) return

  let data: { title?: string; body?: string; url?: string; icon?: string }
  try {
    data = event.data.json()
  } catch {
    data = { title: 'New Notification', body: event.data.text() }
  }

  const options: NotificationOptions = {
    body: data.body || '',
    icon: data.icon || '/icons/icon-192x192.png',
    badge: '/icons/icon-192x192.png',
    data: { url: data.url || '/' },
  }

  event.waitUntil(
    self.registration.showNotification(data.title || 'O-Brain', options)
  )
})

// ── Notification click handler ───────────────────────────────────────────
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = event.notification.data?.url || '/'

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ('focus' in client) {
          client.focus()
          client.navigate(url)
          return
        }
      }
      return self.clients.openWindow(url)
    })
  )
})
