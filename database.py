from supabase import create_client

SUPABASE_URL = "https://opwejgtbqeciehauajno.supabase.co"
SUPABASE_KEY = "sb_publishable_NAUC6kmAEiV1tZgssV6bdQ_IWWRtLUs"

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

def save_user(username, email, password):

    supabase.table("users").insert(
        {
            "username": username,
            "email": email,
            "password": password
        }
    ).execute()

def check_email(email):

    response = (
        supabase
        .table("users")
        .select("*")
        .eq("email", email)
        .execute()
    )

    return len(response.data) > 0

def login_user(email, password):

    response = (
        supabase
        .table("users")
        .select("*")
        .eq("email", email)
        .eq("password", password)
        .execute()
    )

    if len(response.data) == 0:
        return None

    return response.data[0]["username"]

def get_post_count(username):
    try:
        file = open("posts.txt", "r")

        posts = file.readlines()

        file.close()

        count = 0

        for post in posts:
            if post.startswith(username + ":"):
                count += 1

        return count

    except FileNotFoundError:
        return 0


def get_user(username):

    response = (
        supabase
        .table("users")
        .select("*")
        .eq("username", username)
        .execute()
    )

    if len(response.data) == 0:
        return None

    user = response.data[0]

    return (
        user["username"],
        user["email"],
        user["password"]
    )

def get_user_posts(username):

        try:
            file = open("posts.txt", "r")

            posts = file.readlines()

            file.close()

            user_posts = []

            for post in posts:

                if post.startswith(username + ":"):
                    text = post.replace(username + ":", "").strip()

                    user_posts.append(text)

            return user_posts

        except FileNotFoundError:

            return []

def get_all_posts():

            try:
                file = open("posts.txt", "r", encoding="utf-8")

                posts = file.readlines()

                file.close()

                all_posts = []

                for post in posts:

                    post = post.strip()

                    if ":" in post:
                        username, text = post.split(":", 1)

                        all_posts.append((username, text.strip()))

                return all_posts

            except FileNotFoundError:

                return []

def delete_user_post(username, post_number):

                user_posts = get_user_posts(username)

                if post_number < 1 or post_number > len(user_posts):
                    return False

                deleted_post = user_posts[post_number - 1]

                try:

                    file = open("posts.txt", "r", encoding="utf-8")

                    posts = file.readlines()

                    file.close()

                    file = open("posts.txt", "w", encoding="utf-8")

                    deleted = False

                    for post in posts:

                        if not deleted and post.strip() == username + ": " + deleted_post:

                            deleted = True

                        else:

                            file.write(post)

                    file.close()

                    return True

                except FileNotFoundError:

                    return False

def search_user(username):

                    try:

                        file = open("users.txt", "r", encoding="utf-8")

                        users = file.readlines()

                        file.close()

                        for user in users:

                            user = user.strip()

                            parts = user.split(",")

                            name = parts[0]
                            email = parts[1]

                            if name.lower() == username.lower():
                                return (name, email)

                        return None

                    except FileNotFoundError:

                        return None

def edit_user_post(username, post_number, new_text):

                        with open("posts.txt", "r", encoding="utf-8") as file:

                            posts = file.readlines()

                        with open("posts.txt", "w", encoding="utf-8") as file:

                            current_post = 0

                            for post in posts:

                                author, text = post.strip().split(",", 1)

                                if author == username:

                                    current_post += 1

                                    if current_post == post_number:

                                        file.write(f"{author},{new_text}\n")

                                    else:

                                        file.write(post)

                                else:

                                    file.write(post)

                        return True

def add_comment(post_author, post_text, username, comment):

    with open("comments.txt", "a", encoding="utf-8") as file:

        file.write(f"{post_author}|{post_text}|{username}|{comment}\n")

def get_comments(post_author, post_text):

    comments = []

    try:

        with open("comments.txt", "r", encoding="utf-8") as file:

            for line in file:

                author, text, username, comment = line.strip().split("|", 3)

                if author == post_author and text == post_text:
                    comments.append((username, comment))

    except FileNotFoundError:

        pass

    return comments

def add_like(post_author, post_text, username):

    with open("likes.txt", "a", encoding="utf-8") as file:

        file.write(f"{post_author}|{post_text}|{username}\n")

def get_likes(post_author, post_text):

            count = 0

            with open("likes.txt", "r", encoding="utf-8") as file:

                for line in file:

                    author, text, username = line.strip().split("|", 2)

                    if author == post_author and text == post_text:
                        count += 1

            return count

def has_liked(post_author, post_text, username):

    try:

        with open("likes.txt", "r", encoding="utf-8") as file:

            for line in file:

                author, text, user = line.strip().split("|", 2)

                if (
                    author == post_author
                    and text == post_text
                    and user == username
                ):

                    return True

    except FileNotFoundError:

        return False

    return False
def remove_like(post_author, post_text, username):

    try:

        with open("likes.txt", "r", encoding="utf-8") as file:
            likes = file.readlines()

        with open("likes.txt", "w", encoding="utf-8") as file:

            for line in likes:

                author, text, user = line.strip().split("|", 2)

                if not (
                    author == post_author
                    and text == post_text
                    and user == username
                ):
                    file.write(line)

    except FileNotFoundError:

        return


def is_following(follower, following):

        try:

            with open("follows.txt", "r", encoding="utf-8") as file:

                for line in file:

                    user1, user2 = line.strip().split("|", 1)

                    if user1 == follower and user2 == following:
                        return True

        except FileNotFoundError:

            return False

        return False

def get_followers_count(username):

        count = 0

        try:

            with open("follows.txt", "r", encoding="utf-8") as file:

                for line in file:

                    follower, following = line.strip().split("|", 1)

                    if following == username:
                        count += 1

        except FileNotFoundError:

            pass

        return count

def follow_user(follower, following):

        with open("follows.txt", "a", encoding="utf-8") as file:
         file.write(f"{follower}|{following}\n")

def unfollow_user(follower, following):

    try:

        with open("follows.txt", "r", encoding="utf-8") as file:
            follows = file.readlines()

        with open("follows.txt", "w", encoding="utf-8") as file:

            for line in follows:

                user1, user2 = line.strip().split("|", 1)

                if not (user1 == follower and user2 == following):
                    file.write(line)

    except FileNotFoundError:
        pass

def send_message(sender, receiver, message):

        with open("messages.txt", "a", encoding="utf-8") as file:
            file.write(f"{sender}|{receiver}|{message}\n")

def get_messages(user1, user2):

        messages = []

        try:

            with open("messages.txt", "r", encoding="utf-8") as file:

                for line in file:

                    sender, receiver, message = line.strip().split("|", 2)

                    if (
                            sender == user1 and receiver == user2
                    ) or (
                            sender == user2 and receiver == user1
                    ):
                        messages.append((sender, message))

        except FileNotFoundError:

            pass

        return messages

def create_post(username, text):

    with open("posts.txt", "a", encoding="utf-8") as file:
        file.write(f"{username}: {text}\n")