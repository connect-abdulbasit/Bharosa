/* Bharosa service worker: makes the app SHELL load with no signal.
 * It caches pages' HTML + static assets only. API calls (another origin, and always private data) are never touched,
 * so nothing about a person is ever stored by the worker. Saved answers live in IndexedDB (see lib/offline.ts). */
const VERSION = "bharosa-v3";
const SHELL = `${VERSION}-shell`;
const ASSETS = `${VERSION}-assets`;
const PRECACHE = ["/offline", "/", "/login", "/icon.svg"];

// Cache a page's HTML AND the hashed JS/CSS it needs, so the page also works with no signal when it was never opened.
async function precachePage(url) {
  const shell = await caches.open(SHELL);
  const res = await fetch(url, { credentials: "same-origin" });
  if (!res.ok) return;
  await shell.put(url, res.clone());
  const html = await res.text();
  const assets = [...new Set(html.match(/\/_next\/static\/[^"'\s\\)]+\.(?:js|css)/g) || [])];
  const store = await caches.open(ASSETS);
  await Promise.allSettled(assets.map((a) => store.add(a)));
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    Promise.allSettled(PRECACHE.map((u) => (u.endsWith(".svg") ? caches.open(SHELL).then((c) => c.add(u)) : precachePage(u)))).then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("message", (event) => {
  if (event.data === "skip-waiting") self.skipWaiting();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // API + other origins: never cached

  // Pages: network first (always fresh when online), fall back to the cached copy, then the offline page.
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(SHELL).then((c) => c.put(req, copy));
          }
          return res;
        })
        // Not cached: redirect (do NOT serve /offline HTML at this URL, the Next router would then try to hydrate the wrong route).
        .catch(async () => (await caches.match(req)) || Response.redirect("/offline", 302)),
    );
    return;
  }

  // Hashed build files, fonts, icons: cache first, refresh in the background.
  if (url.pathname.startsWith("/_next/static/") || /\.(?:woff2?|svg|png|ico|css|js)$/.test(url.pathname)) {
    event.respondWith(
      caches.open(ASSETS).then(async (cache) => {
        const hit = await cache.match(req);
        const refresh = fetch(req)
          .then((res) => {
            if (res.ok) cache.put(req, res.clone());
            return res;
          })
          .catch(() => hit);
        return hit || refresh;
      }),
    );
  }
});
