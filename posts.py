from database import (
    get_all_posts,
    get_comments,
    add_comment,
    get_likes,
    add_like,
    has_liked,
    remove_like,
)


def create_post(username):

    print()
    print("===== НОВЫЙ ПОСТ =====")

    text = input("Введите текст поста: ").strip()

    if text == "":
        print("Пост не может быть пустым.")
        return

    with open("posts.txt", "a", encoding="utf-8") as file:
        file.write(f"{username},{text}\n")

    print("Пост опубликован!")


def show_posts():

    print()
    print("===== ЛЕНТА =====")

    try:

        with open("posts.txt", "r", encoding="utf-8") as file:
            posts = file.readlines()

        if len(posts) == 0:
            print("Пока нет ни одного поста.")
            return

        for post in posts:
            print(post.strip())

    except FileNotFoundError:

        print("Пока нет ни одного поста.")


def show_feed(username):

    all_posts = get_all_posts()

    print("\n===== ЛЕНТА NOVA =====")

    if len(all_posts) == 0:

        print("В ленте пока нет публикаций.")
        input("\nНажмите Enter для возврата...")
        return

    reversed_posts = list(reversed(all_posts))

    for number, post in enumerate(reversed_posts, start=1):

        post_author, post_text = post

        while True:

            print("\n============================")
            print(f"Пост №{number}")
            print("Пользователь:", post_author)
            print("Публикация:", post_text)

            likes = get_likes(post_author, post_text)

            print(f"\n❤️ Лайков: {likes}")

            comments = get_comments(post_author, post_text)

            print("\n💬 Комментарии:")

            if len(comments) == 0:

                print("Пока нет комментариев.")

            else:

                for comment_author, comment_text in comments:
                    print(f"{comment_author}: {comment_text}")

            print("\n1. ❤️ Лайкнуть / убрать лайк")
            print("2. 💬 Написать комментарий")
            print("3. Следующий пост")
            print("4. Выйти из ленты")

            choice = input("Выберите действие: ")

            if choice == "1":

                if has_liked(post_author, post_text, username):

                    remove_like(post_author, post_text, username)

                    print("💔 Лайк убран!")

                else:

                    add_like(post_author, post_text, username)

                    print("❤️ Лайк поставлен!")

            elif choice == "2":

                comment = input("Введите комментарий: ").strip()

                if comment == "":
                    print("Комментарий не может быть пустым.")
                else:
                    add_comment(
                        post_author,
                        post_text,
                        username,
                        comment,
                    )

                    print("💬 Комментарий добавлен!")

            elif choice == "3":

                break

            elif choice == "4":

                return

            else:

                print("Введите число от 1 до 4.")

    input("\nКонец ленты. Нажмите Enter для возврата...")