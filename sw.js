const CACHE_NAME = "aram-guide-v5";
const CORE_ASSETS = [
  "./index.html",
  "./styles.css?rev=5",
  "./analytics-config.js?rev=5",
  "./analytics.js?rev=5",
  "./app.js?rev=5",
  "./data/guides.json?rev=5",
];
const CORE_ASSET_URLS = new Set(
  CORE_ASSETS.map((path) => new URL(path, self.registration.scope).href),
);
const INDEX_URL = new URL("./index.html", self.registration.scope).href;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(CORE_ASSETS))
      .then(() => self.skipWaiting()),
  );
});

async function activateCurrentCache() {
  const names = await caches.keys();
  await Promise.all(
    names
      .filter((name) => name.startsWith("aram-guide-") && name !== CACHE_NAME)
      .map((name) => caches.delete(name)),
  );
  await self.clients.claim();
}

self.addEventListener("activate", (event) => {
  event.waitUntil(activateCurrentCache());
});

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  const response = await fetch(request);
  if (response.ok) {
    const cache = await caches.open(CACHE_NAME);
    await cache.put(request, response.clone());
  }
  return response;
}

async function networkFirstNavigation(request) {
  try {
    return await fetch(request);
  } catch {
    const cached = await caches.match(INDEX_URL);
    return cached || Response.error();
  }
}

function isPersistentImage(url) {
  return url.origin === self.location.origin
    && (url.pathname.includes("/assets/guides/")
      || url.pathname.includes("/assets/champions/"));
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (request.mode === "navigate") {
    event.respondWith(networkFirstNavigation(request));
    return;
  }
  if (isPersistentImage(url) || CORE_ASSET_URLS.has(request.url)) {
    event.respondWith(cacheFirst(request));
  }
});
