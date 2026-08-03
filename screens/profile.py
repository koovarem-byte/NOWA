import customtkinter as ctk

from database import (
    get_post_count,
    get_followers_count,
    get_user_posts
)


def show_profile(content, username):

    for widget in content.winfo_children():
        widget.destroy()

    title = ctk.CTkLabel(
        content,
        text=f"👤 {username}",
        font=("Arial", 30, "bold")
    )
    title.pack(pady=(30, 20))

    post_count = get_post_count(username)
    followers_count = get_followers_count(username)

    stats = ctk.CTkLabel(
        content,
        text=(
            f"📝 Постов: {post_count}"
            f"      👥 Подписчиков: {followers_count}"
        ),
        font=("Arial", 18)
    )
    stats.pack(pady=(0, 25))

    publications_title = ctk.CTkLabel(
        content,
        text="Мои публикации",
        font=("Arial", 22, "bold")
    )
    publications_title.pack(pady=(0, 10))

    posts_area = ctk.CTkScrollableFrame(
        content,
        width=750,
        height=500,
        corner_radius=15
    )
    posts_area.pack(
        fill="both",
        expand=True,
        padx=40,
        pady=(0, 30)
    )

    user_posts = get_user_posts(username)

    if len(user_posts) == 0:

        empty_label = ctk.CTkLabel(
            posts_area,
            text="У вас пока нет публикаций.",
            font=("Arial", 16),
            text_color="gray"
        )
        empty_label.pack(pady=30)

        return

    for post in reversed(user_posts):

        card = ctk.CTkFrame(
            posts_area,
            corner_radius=15
        )
        card.pack(
            fill="x",
            padx=15,
            pady=8
        )

        post_text = ctk.CTkLabel(
            card,
            text=post,
            font=("Arial", 16),
            wraplength=650,
            justify="left"
        )
        post_text.pack(
            anchor="w",
            padx=20,
            pady=18
        )