// Регистрируем service worker — так сайт можно поставить на телефон как приложение
if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
}

const csrf = document.querySelector('meta[name="csrf"]').content;

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
        bubble.textContent = message.text;
        const time = document.createElement("span");
        time.className = "time";
        time.textContent = message.time;
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
    if (chat.dataset.poll === "1") {
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
