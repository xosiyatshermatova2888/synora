// Minimal app-shell service worker for the /waiter PWA. Scope: static build
// assets + the page's own HTML document, so the app can still *open* while
// offline. Deliberately does NOT touch /api/* — API data caching and the
// offline order queue live in JS (src/lib/offline/), kept separate so a
// stale SW cache can never silently serve stale API data.
const CACHE_NAME = "synora-waiter-shell-v1";

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return; // never intercept API calls

  const isStaticAsset = url.pathname.startsWith("/_next/static/");
  const isNavigation = request.mode === "navigate";
  if (!isStaticAsset && !isNavigation) return;

  if (isStaticAsset) {
    // Cache-first: build assets are content-hashed, safe to keep forever.
    event.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ||
          fetch(request).then((response) => {
            if (response.ok) {
              const copy = response.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
            }
            return response;
          })
      )
    );
    return;
  }

  // Navigation (the page document itself): network-first so a reconnected
  // waiter always gets the latest build, falling back to the last cached
  // shell when offline.
  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        }
        return response;
      })
      .catch(() => caches.match(request))
  );
});
