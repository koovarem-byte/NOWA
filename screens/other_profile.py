import customtkinter as ctk

from database import (
    get_post_count,
    get_followers_count,
    get_user_posts,
    is_following,
    follow_user,
    unfollow_user
)

from screens.messages import show_chat


def show_other_profile(content, current_user, username):

    # очищаем экран
    for widget in content.winfo_children():
        widget.destroy()

    # Заголовок
    title = ctk.CTkLabel(
        content,
        text=f"👤 {username}",
        font=("Arial", 30, "bold")
    )
    title.pack(pady=(30, 20))

    # Статистика
    posts = get_post_count(username)
    followers = get_followers_count(username)

    stats = ctk.CTkLabel(
        content,
        text=f"📝 Постов: {posts}      👥 Подписчиков: {followers}",
        font=("Arial", 18)
    )
    stats.pack(pady=(0, 20))

    # Если открыт НЕ свой профиль
    if current_user != username:

        def toggle_follow():

            if is_following(current_user, username):
                unfollow_user(current_user, username)
            else:
                follow_user(current_user, username)

            show_other_profile(
                content,
                current_user,
                username
            )

        if is_following(current_user, username):
            follow_text = "✅ Вы подписаны"
        else:
            follow_text = "➕ Подписаться"

        follow_button = ctk.CTkButton(
            content,
            text=follow_text,
            width=220,
            height=40,
            command=toggle_follow
        )

        follow_button.pack(
            pady=(0, 10)
        )

        message_button = ctk.CTkButton(
            content,
            text="💬 Написать сообщение",
            width=220,
            height=40,
            command=lambda: show_chat(
                content,
                current_user,
                username
            )
        )

        message_button.pack(
            pady=(0, 25)
        )

    # Заголовок публикаций
    posts_title = ctk.CTkLabel(
        content,
        text="Публикации",
        font=("Arial", 22, "bold")
    )

    posts_title.pack()

    user_posts = get_user_posts(username)

    if len(user_posts) == 0:

        empty = ctk.CTkLabel(
            content,
            text="У пользователя пока нет публикаций.",
            font=("Arial", 16)
        )

        empty.pack(pady=20)

        return

    posts_frame = ctk.CTkScrollableFrame(
        content,
        corner_radius=15
    )

    posts_frame.pack(
        fill="both",
        expand=True,
        padx=25,
        pady=(10, 20)
    )

    for post in reversed(user_posts):

        card = ctk.CTkFrame(
            posts_frame,
            corner_radius=15
        )

        card.pack(
            fill="x",
            padx=10,
            pady=8
        )

        post_label = ctk.CTkLabel(
            card,
            text=post,
            font=("Arial", 16),
            wraplength=700,
            justify="left"
        )

        post_label.pack(
            anchor="w",
            padx=20,
            pady=18
        )