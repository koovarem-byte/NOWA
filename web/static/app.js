// Регистрируем service worker — так сайт можно поставить на телефон как приложение
if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
}

const csrf = document.querySelector('meta[name="csrf"]').content;

// Время на сервере хранится в UTC — показываем его в часовом поясе пользователя
const formatTime = (iso, format) => {
    const date = new Date(iso);
    if (format === "time") {
        return date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
    }
    return date.toLocaleString("ru-RU", {
        day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
    });
};

const localizeTimes = (root = document) => {
    root.querySelectorAll("time.local").forEach((element) => {
        element.textContent = formatTime(element.getAttribute("datetime"), element.dataset.format);
    });
};
localizeTimes();

// Часовой пояс для отложенных постов и минимальное время — «сейчас»
document.querySelectorAll(".tz-offset").forEach((input) => {
    input.value = new Date().getTimezoneOffset();
});
document.querySelectorAll('input[name="publish_at"]').forEach((input) => {
    const soon = new Date(Date.now() + 5 * 60 * 1000);
    input.min = new Date(soon - soon.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
});
document.querySelectorAll("details.schedule").forEach((details) => {
    const button = details.closest("form").querySelector(".btn");
    details.addEventListener("toggle", () => {
        if (!details.open) details.querySelector("input").value = "";
        button.textContent = details.open ? "Запланировать" : "Опубликовать";
    });
});

// Превью фото перед публикацией
document.querySelectorAll('.compose input[type="file"][name="image"]').forEach((input) => {
    const preview = input.closest("form").querySelector(".photo-preview");
    input.addEventListener("change", () => {
        const file = input.files[0];
        if (preview.src) URL.revokeObjectURL(preview.src);
        preview.hidden = !file;
        if (file) preview.src = URL.createObjectURL(file);
    });
});

// Экономный режим: фото грузится только по нажатию
document.addEventListener("click", (event) => {
    const placeholder = event.target.closest(".photo-placeholder");
    if (!placeholder) return;
    event.preventDefault();
    const image = document.createElement("img");
    image.className = "photo";
    image.src = placeholder.dataset.src;
    placeholder.replaceWith(image);
});

// Лайки без перезагрузки страницы
document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!form.classList.contains("like-form")) return;
    event.preventDefault();

    const response = await fetch(form.action, {
        method: "POST",
        headers: { "Accept": "application/json", "X-CSRF-Token": csrf },
    });
    if (!response.ok) return form.submit();

    const data = await response.json();
    const button = form.querySelector("button");
    button.classList.toggle("liked", data.liked);
    button.querySelector(".heart").textContent = data.liked ? "❤️" : "🤍";
    button.querySelector(".count").textContent = data.count;
});

const polling = document.body.dataset.poll === "1";

// Счётчики непрочитанных в меню обновляются сами (кроме экономного режима)
if (polling) {
    const updateCounters = async () => {
        if (document.visibilityState === "visible") {
            try {
                const response = await fetch("/api/counters");
                if (response.ok) {
                    const counts = await response.json();
                    document.querySelectorAll("[data-counter]").forEach((badge) => {
                        const value = counts[badge.dataset.counter] || 0;
                        badge.textContent = value;
                        badge.hidden = value === 0;
                    });
                }
            } catch (error) {
                // Нет сети — попробуем позже
            }
        }
        setTimeout(updateCounters, 20000);
    };
    setTimeout(updateCounters, 20000);
}

// Поделиться ссылкой: системное меню телефона, а если его нет — копируем
document.addEventListener("click", async (event) => {
    const button = event.target.closest(".share-btn");
    if (!button) return;
    const { url, text } = button.dataset;
    if (navigator.share) {
        try {
            await navigator.share({ title: "NOWA", text, url });
            return;
        } catch (error) {
            if (error.name === "AbortError") return;
        }
    }
    try {
        await navigator.clipboard.writeText(`${text} ${url}`);
        const old = button.textContent;
        button.textContent = "✓ Ссылка скопирована";
        setTimeout(() => { button.textContent = old; }, 2000);
    } catch (error) {
        prompt("Скопируй ссылку:", url);
    }
});

// Выбрал время в маяке — сразу отмечаем вариант «В …»
document.querySelectorAll(".inline-time").forEach((input) => {
    input.addEventListener("input", () => {
        input.closest("label").querySelector('input[type="radio"]').checked = true;
    });
});

// При выходе стираем сохранённые страницы — чтобы на чужом телефоне ничего не осталось
document.querySelectorAll('form[action="/logout"]').forEach((form) => {
    form.addEventListener("submit", () => {
        if (window.caches) caches.keys().then((keys) => keys.forEach((key) => caches.delete(key)));
        try { localStorage.removeItem("nowa-outbox"); } catch (error) { /* нет доступа */ }
    });
});

// ---------- Очередь сообщений: пишешь без сети — уйдёт, когда связь вернётся ----------

const outbox = {
    load() {
        try { return JSON.parse(localStorage.getItem("nowa-outbox") || "[]"); } catch (error) { return []; }
    },
    save(items) {
        try { localStorage.setItem("nowa-outbox", JSON.stringify(items)); } catch (error) { /* нет места */ }
    },
    add(item) {
        const items = this.load();
        items.push(item);
        this.save(items);
    },
    remove(id) {
        this.save(this.load().filter((item) => item.id !== id));
    },
};

const sendMessage = async (url, text) => {
    const body = new FormData();
    body.append("text", text);
    body.append("csrf", csrf);
    const response = await fetch(url, { method: "POST", headers: { "Accept": "application/json" }, body });
    if (!response.ok) {
        const error = new Error("send failed");
        error.fatal = response.status >= 400 && response.status < 500;
        throw error;
    }
    return response.json();
};

let flushing = false;
const flushOutbox = async () => {
    if (flushing || !navigator.onLine) return;
    flushing = true;
    for (const item of outbox.load()) {
        try {
            const message = await sendMessage(item.url, item.text);
            outbox.remove(item.id);
            document.dispatchEvent(new CustomEvent("nowa:sent", { detail: { local: item.id, message } }));
        } catch (error) {
            if (error.fatal) {
                outbox.remove(item.id);
                document.dispatchEvent(new CustomEvent("nowa:failed", { detail: { local: item.id } }));
            } else {
                break;
            }
        }
    }
    flushing = false;
};
window.addEventListener("online", flushOutbox);
setInterval(flushOutbox, 15000);
flushOutbox();

const updateNetworkBadge = () => document.body.classList.toggle("offline", !navigator.onLine);
window.addEventListener("online", updateNetworkBadge);
window.addEventListener("offline", updateNetworkBadge);
updateNetworkBadge();

// ---------- Чаты: личный и чат маяка ----------

const chat = document.querySelector(".chat");
if (chat) {
    const log = document.getElementById("chat-log");
    const form = document.getElementById("chat-form");
    const input = form.querySelector('input[name="text"]');
    const sendUrl = chat.dataset.send || location.pathname;

    const lastId = () => {
        const bubbles = log.querySelectorAll(".bubble[data-id]");
        return bubbles.length ? Number(bubbles[bubbles.length - 1].dataset.id) : 0;
    };

    const makeBubble = (message) => {
        log.querySelector(".empty")?.remove();
        const bubble = document.createElement("div");
        bubble.className = "bubble" + (message.mine ? " mine" : "");
        if (message.author && !message.mine) {
            const who = document.createElement("span");
            who.className = "who";
            who.textContent = message.author;
            bubble.appendChild(who);
        }
        const text = document.createElement("span");
        text.className = "msg";
        text.textContent = message.text;
        bubble.appendChild(text);
        const time = document.createElement("span");
        time.className = "time";
        bubble.appendChild(time);
        return bubble;
    };

    const setTime = (bubble, message) => {
        bubble.dataset.id = message.id;
        bubble.classList.remove("pending");
        bubble.querySelector(".time").textContent =
            (message.expires ? "🕒 " : "") + formatTime(message.time, "time");
    };

    const addBubble = (message) => {
        if (log.querySelector(`[data-id="${message.id}"]`)) return;
        const bubble = makeBubble(message);
        setTime(bubble, message);
        // Новые сообщения встают перед ещё не отправленными
        const firstPending = log.querySelector(".bubble.pending");
        log.insertBefore(bubble, firstPending);
        log.scrollTop = log.scrollHeight;
    };

    const addPending = (item) => {
        const bubble = makeBubble({ text: item.text, mine: true });
        bubble.classList.add("pending");
        bubble.dataset.local = item.id;
        bubble.querySelector(".time").textContent = "⏳";
        bubble.title = "Отправится, когда появится связь";
        log.appendChild(bubble);
        log.scrollTop = log.scrollHeight;
    };

    // Неотправленные сообщения этого чата показываем сразу
    outbox.load().filter((item) => item.url === sendUrl).forEach(addPending);

    document.addEventListener("nowa:sent", ({ detail }) => {
        const bubble = log.querySelector(`[data-local="${detail.local}"]`);
        if (!bubble) return;
        if (log.querySelector(`[data-id="${detail.message.id}"]`)) return bubble.remove();
        setTime(bubble, detail.message);
    });
    document.addEventListener("nowa:failed", ({ detail }) => {
        const bubble = log.querySelector(`[data-local="${detail.local}"]`);
        if (bubble) bubble.querySelector(".time").textContent = "⚠️ не отправлено";
    });

    log.scrollTop = log.scrollHeight;

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        const text = input.value.trim();
        if (!text) return;
        input.value = "";
        const item = { id: `${Date.now()}-${Math.random().toString(36).slice(2)}`, url: sendUrl, text };
        outbox.add(item);
        addPending(item);
        flushOutbox();
    });

    // В экономном режиме не опрашиваем сервер — обновление по кнопке
    if (polling) {
        const poll = async () => {
            if (document.visibilityState === "visible" && navigator.onLine) {
                try {
                    const response = await fetch(`${chat.dataset.api}?after=${lastId()}`);
                    if (response.ok) (await response.json()).forEach(addBubble);
                } catch (error) {
                    // Нет сети — попробуем в следующий раз
                }
            }
            setTimeout(poll, 3000);
        };
        setTimeout(poll, 3000);
    }
}
