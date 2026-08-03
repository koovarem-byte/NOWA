import customtkinter as ctk

from database import login_user


def show_login(
    content,
    on_login_success,
    open_register
):

    for widget in content.winfo_children():
        widget.destroy()

    title = ctk.CTkLabel(
        content,
        text="NOVA",
        font=("Arial", 36, "bold")
    )
    title.pack(pady=(80, 10))

    subtitle = ctk.CTkLabel(
        content,
        text="Войдите в свой аккаунт",
        font=("Arial", 18),
        text_color="gray"
    )
    subtitle.pack(pady=(0, 30))

    email_entry = ctk.CTkEntry(
        content,
        width=320,
        height=45,
        placeholder_text="Почта"
    )
    email_entry.pack(pady=10)

    password_entry = ctk.CTkEntry(
        content,
        width=320,
        height=45,
        placeholder_text="Пароль",
        show="*"
    )
    password_entry.pack(pady=10)

    message_label = ctk.CTkLabel(
        content,
        text="",
        font=("Arial", 14)
    )
    message_label.pack(pady=10)

    def try_login():

        email = email_entry.get().strip()
        password = password_entry.get().strip()

        if email == "" or password == "":
            message_label.configure(
                text="Заполните почту и пароль.",
                text_color="#FF5C5C"
            )
            return

        username = login_user(email, password)

        if username:
            on_login_success(username)
        else:
            message_label.configure(
                text="Неверная почта или пароль.",
                text_color="#FF5C5C"
            )

    login_button = ctk.CTkButton(
        content,
        text="Войти",
        width=320,
        height=45,
        command=try_login
    )
    login_button.pack(pady=(10, 15))

    register_button = ctk.CTkButton(
        content,
        text="Создать аккаунт",
        width=320,
        height=45,
        fg_color="transparent",
        border_width=1,
        command=open_register
    )
    register_button.pack()