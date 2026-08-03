import customtkinter as ctk

from database import (
    send_message,
    get_messages
)


def show_chat(content, current_user, other_user):

    # Очищаем предыдущий экран
    for widget in content.winfo_children():
        widget.destroy()

    # Заголовок чата
    title = ctk.CTkLabel(
        content,
        text=f"💬 {other_user}",
        font=("Arial", 28, "bold")
    )

    title.pack(
        pady=(20, 10)
    )

    # Область сообщений
    messages_frame = ctk.CTkScrollableFrame(
        content,
        corner_radius=15
    )

    messages_frame.pack(
        fill="both",
        expand=True,
        padx=25,
        pady=(5, 10)
    )

    # Получаем переписку двух пользователей
    messages = get_messages(
        current_user,
        other_user
    )

    # Если сообщений ещё нет
    if len(messages) == 0:

        empty_label = ctk.CTkLabel(
            messages_frame,
            text="Сообщений пока нет.\nНапиши первым 👋",
            font=("Arial", 16),
            text_color="gray"
        )

        empty_label.pack(
            pady=40
        )

    # Показываем сообщения
    else:

        for sender, message in messages:

            # Наше сообщение
            if sender == current_user:

                message_label = ctk.CTkLabel(
                    messages_frame,
                    text=message,
                    font=("Arial", 16),
                    fg_color="#007AFF",
                    corner_radius=15,
                    wraplength=500,
                    justify="left"
                )

                message_label.pack(
                    anchor="e",
                    padx=15,
                    pady=5,
                    ipadx=12,
                    ipady=8
                )

            # Сообщение собеседника
            else:

                message_label = ctk.CTkLabel(
                    messages_frame,
                    text=message,
                    font=("Arial", 16),
                    fg_color="#333333",
                    corner_radius=15,
                    wraplength=500,
                    justify="left"
                )

                message_label.pack(
                    anchor="w",
                    padx=15,
                    pady=5,
                    ipadx=12,
                    ipady=8
                )

    # Нижняя панель
    bottom_frame = ctk.CTkFrame(
        content,
        corner_radius=15
    )

    bottom_frame.pack(
        fill="x",
        padx=25,
        pady=(0, 20)
    )

    # Поле ввода
    message_entry = ctk.CTkEntry(
        bottom_frame,
        placeholder_text="Сообщение...",
        height=45
    )

    message_entry.pack(
        side="left",
        fill="x",
        expand=True,
        padx=(10, 5),
        pady=10
    )

    # Функция отправки
    def send():

        message = message_entry.get().strip()

        if message == "":
            return

        send_message(
            current_user,
            other_user,
            message
        )

        # Обновляем чат
        show_chat(
            content,
            current_user,
            other_user
        )

    # Кнопка отправки
    send_button = ctk.CTkButton(
        bottom_frame,
        text="➤",
        width=55,
        height=45,
        command=send
    )

    send_button.pack(
        side="right",
        padx=(5, 10),
        pady=10
    )