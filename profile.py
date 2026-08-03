from database import (get_user_posts, delete_user_post, edit_user_post,get_followers_count,follow_user,
is_following,unfollow_user)


def show_profile(username):

    while True:

        print("\n===== ПРОФИЛЬ =====")
        print("Пользователь:", username)

        posts = get_user_posts(username)

        print("\nМои посты:")

        if len(posts) == 0:
            print("Постов пока нет.")
        else:
            for number, post in enumerate(posts, start=1):
                print(f"{number}. {post}")

        print("\n1. Редактировать пост")
        print("2. Удалить пост")
        print("3. Назад")

        choice = input("Выберите действие: ")

        if choice == "1":

            if len(posts) == 0:
                print("Редактировать нечего.")
                continue

            number = int(input("Введите номер поста: "))
            new_text = input("Введите новый текст: ")

            edit_user_post(username, number, new_text)

            print("Пост успешно изменён!")

        elif choice == "2":

            if len(posts) == 0:
                print("Удалять нечего.")
                continue

            number = int(input("Введите номер поста: "))

            if delete_user_post(username, number):
                print("Пост успешно удалён!")
            else:
                print("Такого поста не существует.")

        elif choice == "3":
            break

        else:
            print("Такого пункта нет.")


def show_user_profile(current_user, username):

    while True:

        print("\n===== ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ =====")
        print("👤", username)
        print("👥 Подписчиков:", get_followers_count(username))

        posts = get_user_posts(username)

        print("📝 Постов:", len(posts))

        if len(posts) == 0:
            print("\nУ пользователя пока нет постов.")
        else:
            print("\nПосты:\n")

            for number, post in enumerate(posts, start=1):
                print(f"{number}. {post}")

        print()

        if current_user == username:
            print("Это ваш профиль.")
            input("\nНажмите Enter...")
            break

        if is_following(current_user, username):
            print("1. Отписаться")
        else:
            print("1. Подписаться")

        print("2. Назад")

        choice = input("\nВыберите действие: ")

        if choice == "1":

            if is_following(current_user, username):

                unfollow_user(current_user, username)
                print("\n💔 Вы отписались.")

            else:

                follow_user(current_user, username)
                print("\n❤️ Вы подписались.")

            input("\nНажмите Enter...")

        elif choice == "2":
            break