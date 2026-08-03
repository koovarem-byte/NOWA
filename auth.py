from web.app import user_menu
from database import save_user, check_email,login_user

def register():
    print("=== Регистрация NOVA ===")

    username = input("Введите имя: ")
    email = input("Введите почту: ")

    if check_email(email):
        print("Такая почта уже зарегестрирована")
        return

    password = input("Введите пароль: ")
    save_user(username, email, password)

    print()
    print("Аккаунт создан!")
    print("Добро пожаловать,", username)

    user_menu(username)

def login():

        print("=== Вход NOVA ===")

        email = input("Введите почту: ")

        password = input("Введите пароль: ")

        username = login_user(email, password)

        if username:
            print("Добро пожаловать,", username)

            print("ПЕРЕД МЕНЮ")

            user_menu(username)

        else:
            print("Неверная почта или пароль")