// Service worker NOWA: кэширует оформление, чтобы приложение открывалось быстро
// даже на плохом интернете, и показывает страницу «нет сети», если связи нет совсем.
const CACHE = "nowa-v1";
const SHELL = ["/static/style.css", "/static/app.js", "/static/icon.svg", "/offline"];

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))
        )
    );
    self.clients.claim();
});

self.addEventListener("fetch", (event) => {
    const request = event.request;
    if (request.method !== "GET") return;
    const url = new URL(request.url);
    if (url.origin !== location.origin) return;

    // Статику отдаём из кэша и обновляем в фоне
    if (url.pathname.startsWith("/static/")) {
        event.respondWith(
            caches.match(request).then((cached) => {
                const fresh = fetch(request).then((response) => {
                    const copy = response.clone();
                    caches.open(CACHE).then((cache) => cache.put(request, copy));
                    return response;
                });
                return cached || fresh;
            })
        );
        return;
    }

    // Страницы — всегда из сети, а без сети показываем заглушку
    if (request.mode === "navigate") {
        event.respondWith(fetch(request).catch(() => caches.match("/offline")));
    }
});
