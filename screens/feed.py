import customtkinter as ctk

from database import (
    get_all_posts,
    get_likes,
    add_like,
    remove_like,
    has_liked,
    get_comments,
    add_comment
)


def toggle_like(content, username, author, text):

    if has_liked(author, text, username):
        remove_like(author, text, username)
    else:
        add_like(author, text, username)

    show_feed(content, username)


def show_feed(content, username):

    for widget in content.winfo_children():
        widget.destroy()

    title = ctk.CTkLabel(
        content,
        text="📰 Лента NOVA",
        font=("Arial", 30, "bold")
    )

    title.pack(pady=(20, 15))

    posts = get_all_posts()

    if len(posts) == 0:

        empty = ctk.CTkLabel(
            content,
            text="Пока нет публикаций.",
            font=("Arial", 18)
        )

        empty.pack(pady=50)

        return

    feed = ctk.CTkScrollableFrame(content)

    feed.pack(
        fill="both",
        expand=True,
        padx=15,
        pady=10
    )

    for author, text in reversed(posts):

        card = ctk.CTkFrame(
            feed,
            corner_radius=15
        )

        card.pack(
            fill="x",
            padx=10,
            pady=8
        )

        author_label = ctk.CTkLabel(
            card,
            text=f"👤 {author}",
            font=("Arial", 18, "bold")
        )

        author_label.pack(
            anchor="w",
            padx=20,
            pady=(15, 5)
        )

        text_label = ctk.CTkLabel(
            card,
            text=text,
            font=("Arial", 16),
            wraplength=700,
            justify="left"
        )

        text_label.pack(
            anchor="w",
            padx=20
        )

        likes = get_likes(author, text)

        liked = has_liked(
            author,
            text,
            username
        )

        heart = "❤️" if liked else "🤍"
        like_button = ctk.CTkButton(
            card,
            text=f"{heart} {likes}",
            width=90,
            height=35,
            command=lambda a=author, t=text: toggle_like(
                content,
                username,
                a,
                t
            )
        )

        like_button.pack(
            anchor="w",
            padx=20,
            pady=(10, 8)
        )

        comments = get_comments(author, text)

        for user, user_comment in comments:
            comment_label = ctk.CTkLabel(
                card,
                text=f"💬 {user}: {user_comment}",
                font=("Arial", 14),
                wraplength=650,
                justify="left"
            )

            comment_label.pack(
                anchor="w",
                padx=30,
                pady=2
            )

        comment_entry = ctk.CTkEntry(
            card,
            placeholder_text="Написать комментарий..."
        )

        comment_entry.pack(
            fill="x",
            padx=20,
            pady=(10, 5)
        )

        def send_comment(
                a=author,
                t=text,
                entry=comment_entry
        ):

            new_comment = entry.get().strip()

            if new_comment == "":
                return

            add_comment(
                a,
                t,
                username,
                new_comment
            )

            show_feed(content, username)

        send_button = ctk.CTkButton(
            card,
            text="Отправить",
            command=send_comment
        )

        send_button.pack(
            anchor="e",
            padx=20,
            pady=(0, 15)
        )
