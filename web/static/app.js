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

// Чат: отправка без перезагрузки и проверка новых сообщений
const chat = document.querySelector(".chat");
if (chat) {
    const log = document.getElementById("chat-log");
    const form = document.getElementById("chat-form");
    const input = form.querySelector('input[name="text"]');

    const lastId = () => {
        const bubbles = log.querySelectorAll(".bubble");
        return bubbles.length ? Number(bubbles[bubbles.length - 1].dataset.id) : 0;
    };

    const addBubble = (message) => {
        if (log.querySelector(`[data-id="${message.id}"]`)) return;
        log.querySelector(".empty")?.remove();
        const bubble = document.createElement("div");
        bubble.className = "bubble" + (message.mine ? " mine" : "");
        bubble.dataset.id = message.id;
        const text = document.createElement("span");
        text.className = "msg";
        text.textContent = message.text;
        bubble.appendChild(text);
        const time = document.createElement("span");
        time.className = "time";
        time.textContent = (message.expires ? "🕒 " : "") + formatTime(message.time, "time");
        bubble.appendChild(time);
        log.appendChild(bubble);
        log.scrollTop = log.scrollHeight;
    };

    log.scrollTop = log.scrollHeight;

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const text = input.value.trim();
        if (!text) return;
        input.value = "";

        const body = new FormData();
        body.append("text", text);
        body.append("csrf", csrf);
        const response = await fetch(location.pathname, {
            method: "POST",
            headers: { "Accept": "application/json" },
            body,
        });
        if (response.ok) {
            addBubble(await response.json());
        } else {
            input.value = text;
        }
    });

    // В экономном режиме не опрашиваем сервер — обновление по кнопке
    if (polling) {
        const poll = async () => {
            if (document.visibilityState === "visible") {
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
