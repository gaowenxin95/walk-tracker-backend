const CACHE_NAME = "walk-tracker-v4";
const APP_SHELL = [
  "/",
  "/manifest.webmanifest",
  "/icons/icon.svg",
  "/assets/sport-hero.svg"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
    ))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  if (
    url.pathname.startsWith("/stats") ||
    url.pathname.startsWith("/records") ||
    url.pathname === "/captcha" ||
    url.pathname.startsWith("/captcha-image/") ||
    url.pathname === "/me" ||
    url.pathname === "/login" ||
    url.pathname === "/logout" ||
    url.pathname === "/profile"
  ) {
    event.respondWith(fetch(event.request));
    return;
  }

  if (url.pathname === "/") {
    event.respondWith(
      fetch(event.request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return response;
      }).catch(() => caches.match(event.request))
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => (
      cached || fetch(event.request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return response;
      })
    ))
  );
});
