/* FlowDesk service worker: makes the app open offline and load instantly.
   - App files: served from cache, refreshed in the background (a new version applies on next launch).
   - Chart library and fonts: cached on first use.
   - Market data (Binance): always live, never cached. */
const VERSION = "flowdesk-v1";
const APP_SHELL = ["./", "./index.html", "./manifest.webmanifest", "./icons/icon-192.png", "./icons/icon-512.png", "./icons/apple-touch-icon.png", "./icons/favicon-32.png"];
const CHART_LIB = "https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js";

self.addEventListener("install", e => {
  e.waitUntil((async () => {
    const c = await caches.open(VERSION);
    await c.addAll(APP_SHELL);
    try { await c.add(new Request(CHART_LIB, { mode: "cors" })); } catch {}
    await self.skipWaiting();
  })());
});
self.addEventListener("activate", e => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k !== VERSION) await caches.delete(k);
    await self.clients.claim();
  })());
});

async function staleWhileRevalidate(req, key = req) {
  const c = await caches.open(VERSION), hit = await c.match(key, { ignoreSearch: true });
  const net = fetch(req).then(r => { if (r && r.ok) c.put(key, r.clone()); return r; }).catch(() => null);
  return hit || (await net) || new Response("Offline", { status: 503, statusText: "Offline" });
}
async function cacheFirst(req) {
  const c = await caches.open(VERSION), hit = await c.match(req);
  if (hit) return hit;
  const r = await fetch(req); if (r && (r.ok || r.type === "opaque")) c.put(req, r.clone()); return r;
}

self.addEventListener("fetch", e => {
  const req = e.request; if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (/binance\.(com|us)$/.test(url.hostname)) return;                       // live data: network only
  if (req.mode === "navigate") { e.respondWith(staleWhileRevalidate(req, "./index.html")); return; }
  if (url.origin === location.origin) { e.respondWith(staleWhileRevalidate(req)); return; }
  if (url.hostname === "unpkg.com" || url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com") { e.respondWith(cacheFirst(req)); return; }
});
