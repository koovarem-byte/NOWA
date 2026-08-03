from auth import register,login

print("===== NOVA =====")

print("1. Войти")
print("2. Регистрация")
print("3. Выход")

choice = input("Выберите действие: ")

if choice == "1":
    login()

elif choice == "2":
    register()

elif choice == "3":
    print("Выход")

else:
    print("Такого пункта нет")