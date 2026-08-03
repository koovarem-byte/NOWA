import customtkinter as ctk

from database import save_user, check_email


def show_register(content, on_register_success, open_login):

    for widget in content.winfo_children():
        widget.destroy()

    title = ctk.CTkLabel(
        content,
        text="Регистрация NOVA",
        font=("Arial", 34, "bold")
    )
    title.pack(pady=(70, 10))

    subtitle = ctk.CTkLabel(
        content,
        text="Создайте новый аккаунт",
        font=("Arial", 17),
        text_color="gray"
    )
    subtitle.pack(pady=(0, 25))

    username_entry = ctk.CTkEntry(
        content,
        width=320,
        height=45,
        placeholder_text="Имя пользователя"
    )
    username_entry.pack(pady=8)

    email_entry = ctk.CTkEntry(
        content,
        width=320,
        height=45,
        placeholder_text="Почта"
    )
    email_entry.pack(pady=8)

    password_entry = ctk.CTkEntry(
        content,
        width=320,
        height=45,
        placeholder_text="Пароль",
        show="*"
    )
    password_entry.pack(pady=8)

    message_label = ctk.CTkLabel(
        content,
        text="",
        font=("Arial", 14)
    )
    message_label.pack(pady=10)

    def try_register():

        username = username_entry.get().strip()
        email = email_entry.get().strip()
        password = password_entry.get().strip()

        if username == "" or email == "" or password == "":
            message_label.configure(
                text="Заполните все поля.",
                text_color="#FF5C5C"
            )
            return

        if check_email(email):
            message_label.configure(
                text="Такая почта уже зарегистрирована.",
                text_color="#FF5C5C"
            )
            return

        save_user(username, email, password)

        message_label.configure(
            text="Аккаунт создан!",
            text_color="#4CD964"
        )

        on_register_success(username)

    register_button = ctk.CTkButton(
        content,
        text="Создать аккаунт",
        width=320,
        height=45,
        command=try_register
    )
    register_button.pack(pady=(10, 15))

    login_button = ctk.CTkButton(
        content,
        text="Уже есть аккаунт? Войти",
        width=320,
        height=45,
        fg_color="transparent",
        border_width=1,
        command=open_login
    )
    login_button.pack()