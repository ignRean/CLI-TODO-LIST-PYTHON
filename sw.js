const CACHE_NAME = "pytodo-v2.2.4";

// Tier 1: Core application shell (< 350 KB total)
const CORE_SHELL = [
  "/",
  "/index.html",
  "/style.css",
  "/main.js",
  "/main.py",
  "/manifest.json",
  "https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/css/xterm.css",
  "https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/lib/xterm.js",
  "https://cdn.jsdelivr.net/npm/@xterm/addon-fit@0.10.0/lib/addon-fit.js",
  "https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.js",
  "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"
];

// Tier 2: Heavy WebAssembly binaries (streamed resiliently in background)
const DEFERRED_BINARIES = [
  "https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.asm.wasm",
  "https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.asm.js",
  "https://cdn.jsdelivr.net/pyodide/v0.26.2/full/python_stdlib.zip"
];

// Helper: Network fetch with configurable timeout (prevents 2G socket hangs)
function timeoutFetch(request, timeoutMs = 1800) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(request, { signal: controller.signal }).finally(() => clearTimeout(timer));
}

// Resilient installation: Non-atomic caching with Promise.allSettled
self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(async (cache) => {
      // 1. Pre-cache critical core shell
      await Promise.allSettled(
        CORE_SHELL.map((url) =>
          cache.add(url).catch((err) => console.warn("[SW] Core asset cache skip:", url, err))
        )
      );

      // 2. Queue deferred heavy binaries without blocking immediate activation
      Promise.allSettled(
        DEFERRED_BINARIES.map((url) =>
          cache.add(url).catch((err) => console.warn("[SW] Heavy binary queued for runtime:", url, err))
        )
      );
    })
  );
});

// Purge obsolete cache buckets during activation
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) return caches.delete(key);
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Strategic fetch handling:
// 1. Supabase API: Pass-through (never cache live DB transactions)
// 2. App code: Network-First with 1.8s timeout, instant fallback to cache
// 3. Static CDNs & Binaries: Cache-First for instant 0ms offline execution
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // 1. Supabase API pass-through
  if (url.origin.includes("supabase.co")) {
    return;
  }

  // 2. Application code: Network-First with fast timeout fallback
  const isAppCode =
    url.origin === self.location.origin &&
    (url.pathname === "/" ||
     url.pathname.endsWith(".html") ||
     url.pathname.endsWith(".js") ||
     url.pathname.endsWith(".py") ||
     url.pathname.endsWith(".css"));

  if (isAppCode) {
    event.respondWith(
      timeoutFetch(event.request, 1800)
        .then((response) => {
          if (response && response.status === 200) {
            const resClone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, resClone));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // 3. Heavy static CDN assets: Cache-First
  event.respondWith(
    caches.match(event.request).then((cached) => {
      return (
        cached ||
        fetch(event.request).then((response) => {
          if (response && response.status === 200) {
            const resClone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, resClone));
          }
          return response;
        })
      );
    })
  );
});