const CACHE_PREFIX = "aram-guide-v21";
const CORE_CACHE = `${CACHE_PREFIX}-core`;
const DATA_CACHE = `${CACHE_PREFIX}-data`;
const RESOURCE_CACHE = `${CACHE_PREFIX}-resources`;

const CORE_ASSETS = [
  "./index.html",
  "./styles.css?rev=21",
  "./analytics-config.js?rev=21",
  "./analytics.js?rev=21",
  "./app.js?rev=21",
];

const CORE_URLS = new Set(CORE_ASSETS.map((path) => new URL(path, self.registration.scope).href));
const INDEX_URL = new URL("./index.html", self.registration.scope).href;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CORE_CACHE)
      .then((cache) => cache.addAll(CORE_ASSETS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const cacheNames = await caches.keys();
    await Promise.all(
      cacheNames
        .filter((name) => name.startsWith("aram-guide-") && !name.startsWith(CACHE_PREFIX))
        .map((name) => caches.delete(name)),
    );
    await self.clients.claim();
  })());
});

async function putIfCacheable(cacheName, request, response) {
  if (!response?.ok) return response;
  const cache = await caches.open(cacheName);
  await cache.put(request, response.clone());
  return response;
}

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;
  return putIfCacheable(cacheName, request, await fetch(request));
}

async function networkFirst(request, cacheName, fallbackUrl = null) {
  try {
    return await putIfCacheable(cacheName, request, await fetch(request));
  } catch {
    const cache = await caches.open(cacheName);
    return (await cache.match(request))
      || (fallbackUrl ? await cache.match(fallbackUrl) : null)
      || Response.error();
  }
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const refresh = fetch(request)
    .then((response) => putIfCacheable(cacheName, request, response))
    .catch(() => null);
  if (cached) {
    refresh.catch(() => {});
    return cached;
  }
  return (await refresh) || Response.error();
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(networkFirst(request, CORE_CACHE, INDEX_URL));
    return;
  }

  if (url.pathname.endsWith("/data/index.json")) {
    event.respondWith(networkFirst(request, DATA_CACHE));
    return;
  }

  if (url.pathname.includes("/data/heroes/") && url.pathname.endsWith(".json")) {
    event.respondWith(staleWhileRevalidate(request, DATA_CACHE));
    return;
  }

  if (url.pathname.includes("/assets/resources/")
      || url.pathname.includes("/assets/champions/")
      || url.pathname.includes("/assets/guides/")) {
    event.respondWith(cacheFirst(request, RESOURCE_CACHE));
    return;
  }

  if (CORE_URLS.has(request.url)) {
    event.respondWith(cacheFirst(request, CORE_CACHE));
  }
});
