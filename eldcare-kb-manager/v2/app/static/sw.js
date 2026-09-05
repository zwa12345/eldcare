// ELDCARE Service Worker（极简版，只做离线壳）
const CACHE = "eldcare-v1";

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(clients.claim());
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // 不缓存 API 和视频流
  if (url.pathname.startsWith("/api/") ||
      url.pathname.startsWith("/api/v2/player/stream/")) {
    return;
  }
  event.respondWith(
    caches.open(CACHE).then(cache =>
      cache.match(event.request).then(cached => {
        const fetched = fetch(event.request).then(resp => {
          if (resp.ok) cache.put(event.request, resp.clone());
          return resp;
        }).catch(() => cached);
        return cached || fetched;
      })
    )
  );
});
