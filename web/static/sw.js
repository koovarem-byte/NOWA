// Service worker NOWA.
// 1. Оформление берём из кэша — приложение открывается быстро даже на плохом интернете.
// 2. Открытые страницы сохраняем — без сети их можно перечитать.
// 3. Если страницы нет в кэше и сети нет — показываем «нет сети».
const CACHE = "nowa-v7";
const PAGES = "nowa-pages-v1";
const MAX_PAGES = 40;
const SHELL = ["/static/style.css", "/static/app.js", "/static/icon.svg", "/offline"];

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((key) => key !== CACHE && key !== PAGES).map((key) => caches.delete(key)))
        )
    );
    self.clients.claim();
});

const rememberPage = async (request, response) => {
    const cache = await caches.open(PAGES);
    await cache.put(request, response);
    const keys = await cache.keys();
    // Храним только последние страницы, чтобы не забивать память телефона
    for (const old of keys.slice(0, Math.max(0, keys.length - MAX_PAGES))) {
        await cache.delete(old);
    }
};

self.addEventListener("fetch", (event) => {
    const request = event.request;
    if (request.method !== "GET") return;
    const url = new URL(request.url);
    if (url.origin !== location.origin) return;

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

    if (request.mode === "navigate") {
        event.respondWith(
            fetch(request)
                .then((response) => {
                    if (response.ok && !response.redirected) {
                        const copy = response.clone();
                        event.waitUntil(rememberPage(request, copy));
                    }
                    return response;
                })
                .catch(async () => (await caches.match(request, { cacheName: PAGES })) || caches.match("/offline"))
        );
    }
});

// ---------- Пуш-уведомления ----------

self.addEventListener("push", (event) => {
    let data = {};
    try { data = event.data ? event.data.json() : {}; } catch (error) { data = { body: event.data.text() }; }
    event.waitUntil(
        self.registration.showNotification(data.title || "NOWA", {
            body: data.body || "",
            icon: "/static/icon-192.png",
            badge: "/static/icon-192.png",
            tag: data.tag,
            renotify: Boolean(data.tag),
            data: { url: data.url || "/feed" },
        })
    );
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    const url = new URL(event.notification.data.url, self.location.origin).href;
    event.waitUntil(
        self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
            for (const client of windows) {
                if (client.url === url && "focus" in client) return client.focus();
            }
            return self.clients.openWindow(url);
        })
    );
});
