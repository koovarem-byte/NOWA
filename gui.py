import customtkinter as ctk

from screens.home import show_home
from screens.login import show_login
from screens.register import show_register
from screens.feed import show_feed
from screens.profile import show_profile
from screens.create_post import show_create_post
from screens.search import show_search

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


app = ctk.CTk()
app.title("NOVA")
app.geometry("1200x800")
app.minsize(1000, 700)

current_user = None


# ---------------- ЛЕВАЯ ПАНЕЛЬ ----------------

sidebar = ctk.CTkFrame(
    app,
    width=220,
    corner_radius=0
)
sidebar.pack(
    side="left",
    fill="y"
)

sidebar.pack_propagate(False)


# ---------------- ПРАВАЯ ПАНЕЛЬ ----------------

content = ctk.CTkFrame(
    app,
    corner_radius=0
)
content.pack(
    side="right",
    fill="both",
    expand=True
)


# ---------------- ЛОГОТИП ----------------

logo = ctk.CTkLabel(
    sidebar,
    text="NOVA",
    font=("Arial", 32, "bold"),
    text_color="#007AFF"
)
logo.pack(pady=(35, 10))


user_label = ctk.CTkLabel(
    sidebar,
    text="Вы не вошли",
    font=("Arial", 14),
    text_color="gray"
)
user_label.pack(pady=(0, 30))


# ---------------- НАВИГАЦИЯ ----------------

def open_home():
    show_home(
        content,
        current_user,
        open_feed,
        open_profile
    )


def open_feed():
    show_feed(content,current_user)


def open_profile():

    if current_user is None:
        open_login()
        return

    show_profile(
        content,
        current_user
    )

def open_search():

    if current_user is None:
        open_login()
        return

    show_search(
        content,
        current_user
    )
    
def open_create_post():

    if current_user is None:
        return

    show_create_post(
        content,
        current_user,
        open_feed
    )

def open_login():
    show_login(
        content,
        login_success,
        open_register
    )


def open_register():
    show_register(
        content,
        register_success,
        open_login
    )


# ---------------- ВХОД И РЕГИСТРАЦИЯ ----------------

def login_success(username):

    global current_user

    current_user = username

    user_label.configure(
        text=f"👤 {username}",
        text_color="white"
    )

    open_home()


def register_success(username):

    global current_user

    current_user = username

    user_label.configure(
        text=f"👤 {username}",
        text_color="white"
    )

    open_home()


# ---------------- КНОПКИ МЕНЮ ----------------

home_button = ctk.CTkButton(
    sidebar,
    text="🏠 Главная",
    width=180,
    height=42,
    command=open_home
)
home_button.pack(pady=6)


feed_button = ctk.CTkButton(
    sidebar,
    text="📰 Лента",
    width=180,
    height=42,
    command=open_feed
)
feed_button.pack(pady=6)


profile_button = ctk.CTkButton(
    sidebar,
    text="👤 Профиль",
    width=180,
    height=42,
    command=open_profile
)
profile_button.pack(pady=6)

search_button = ctk.CTkButton(
    sidebar,
    text="🔍 Поиск",
    width=180,
    height=42,
    command=open_search
)

search_button.pack(pady=6)


create_post_button = ctk.CTkButton(
        sidebar,
        text="➕ Создать пост",
        width=180,
        height=42,
        command=open_create_post
    )

create_post_button.pack(pady=6)

login_button = ctk.CTkButton(
    sidebar,
    text="🔐 Вход",
    width=180,
    height=42,
    command=open_login
)
login_button.pack(pady=6)


register_button = ctk.CTkButton(
    sidebar,
    text="📝 Регистрация",
    width=180,
    height=42,
    command=open_register
)
register_button.pack(pady=6)


# При запуске открываем вход
open_login()

app.mainloop()