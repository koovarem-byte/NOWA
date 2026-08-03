import customtkinter as ctk

from database import create_post


def show_create_post(content, username, go_back):

    # Очищаем экран
    for widget in content.winfo_children():
        widget.destroy()

    # Заголовок
    title = ctk.CTkLabel(
        content,
        text="✍ Создать публикацию",
        font=("Arial", 30, "bold")
    )
    title.pack(pady=(35, 20))

    # Поле ввода
    post_text = ctk.CTkTextbox(
        content,
        width=700,
        height=220,
        font=("Arial", 16)
    )
    post_text.pack(pady=15)

    message = ctk.CTkLabel(
        content,
        text=""
    )
    message.pack(pady=10)

    def publish():

        text = post_text.get("1.0", "end").strip()

        if text == "":
            message.configure(
                text="Введите текст публикации.",
                text_color="red"
            )
            return

        create_post(username,text)

        message.configure(
            text="Публикация успешно создана!",
            text_color="green"
        )

        go_back()

    publish_button = ctk.CTkButton(
        content,
        text="🚀 Опубликовать",
        width=250,
        height=45,
        command=publish
    )
    publish_button.pack(pady=15)