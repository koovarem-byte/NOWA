import customtkinter as ctk


def show_home(
    content,
    username=None,
    open_feed=None,
    open_profile=None
):

    for widget in content.winfo_children():
        widget.destroy()

    if username:
        greeting = f"👋 Добро пожаловать, {username}"
    else:
        greeting = "👋 Добро пожаловать в NOVA"

    title = ctk.CTkLabel(
        content,
        text=greeting,
        font=("Arial", 32, "bold")
    )
    title.pack(pady=(50, 10))

    subtitle = ctk.CTkLabel(
        content,
        text="Что хотите открыть?",
        font=("Arial", 18),
        text_color="gray"
    )
    subtitle.pack(pady=(0, 35))

    feed_button = ctk.CTkButton(
        content,
        text="📰 Лента",
        width=300,
        height=45,
        command=open_feed
    )
    feed_button.pack(pady=8)

    profile_button = ctk.CTkButton(
        content,
        text="👤 Мой профиль",
        width=300,
        height=45,
        command=open_profile
    )
    profile_button.pack(pady=8)

    messages_button = ctk.CTkButton(
        content,
        text="💬 Сообщения",
        width=300,
        height=45,
        state="disabled"
    )
    messages_button.pack(pady=8)

    search_button = ctk.CTkButton(
        content,
        text="🔍 Поиск",
        width=300,
        height=45,
        state="disabled"
    )
    search_button.pack(pady=8)