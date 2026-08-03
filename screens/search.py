import customtkinter as ctk

from database import search_user
from screens.other_profile import show_other_profile


def show_search(content, current_user):

    for widget in content.winfo_children():
        widget.destroy()

    title = ctk.CTkLabel(
        content,
        text="🔍 Поиск пользователей",
        font=("Arial", 30, "bold")
    )
    title.pack(pady=(25, 20))

    search_entry = ctk.CTkEntry(
        content,
        width=350,
        height=40,
        placeholder_text="Введите имя пользователя"
    )
    search_entry.pack(pady=10)

    result_label = ctk.CTkLabel(
        content,
        text="",
        font=("Arial", 16)
    )
    result_label.pack(pady=15)

    def find():

        username = search_entry.get().strip()

        if username == "":
            return

        user = search_user(username)

        if user is None:

            result_label.configure(
                text="Пользователь не найден",
                text_color="red"
            )

            return

        show_other_profile(
            content,
            current_user,
            user[0]
        )

    search_button = ctk.CTkButton(
        content,
        text="Найти",
        command=find
    )

    search_button.pack(pady=10)