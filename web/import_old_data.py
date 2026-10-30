"""Перенос старых данных NOWA в новую базу.

Берёт пользователей из Supabase (если до него есть доступ) и из users.txt,
а посты, лайки, комментарии, подписки и сообщения — из .txt файлов в корне проекта.
Пароли при переносе хешируются. Повторный запуск ничего не дублирует.

Запуск:  python web/import_old_data.py            (txt + Supabase)
         python web/import_old_data.py --no-supabase
"""

import json
import os
import secrets
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import (  # noqa: E402
    Comment, Follow, Like, Message, Post, User, create_app, db, find_user,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://opwejgtbqeciehauajno.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_NAUC6kmAEiV1tZgssV6bdQ_IWWRtLUs")


def read_lines(name):
    path = os.path.join(ROOT, name)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as file:
        return [line.rstrip("\n") for line in file if line.strip()]


def clean_username(name):
    name = "".join(ch for ch in name.strip() if ch.isalnum() or ch in "_.")[:32]
    # Новые правила требуют минимум 3 символа — дополняем короткие имена
    while 0 < len(name) < 3:
        name += "_"
    return name


def get_or_create_user(name, email=None, password=None, stats=None):
    """Находит пользователя по имени или создаёт. Без пароля войти в аккаунт нельзя,
    пока владелец не зарегистрируется заново с этим именем (такие аккаунты помечаются)."""
    username = clean_username(name)
    if not username or username.lower() == "none":
        return None

    user = find_user(username)
    if user:
        if password and user.email.endswith("@imported.nowa"):
            # Нашлись настоящие данные для ранее созданного «пустого» аккаунта
            if email and not User.query.filter_by(email=email).first():
                user.email = email
            user.set_password(password)
        return user

    if email and User.query.filter_by(email=email).first():
        email = None
    user = User(username=username, email=email or f"{username.lower()}@imported.nowa")
    user.set_password(password or secrets.token_urlsafe(24))
    db.session.add(user)
    db.session.flush()
    if stats is not None:
        stats["users"] += 1
    return user


def fetch_supabase_users():
    request = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/users?select=*",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def import_all(use_supabase=True):
    stats = {key: 0 for key in ("users", "posts", "likes", "comments", "follows", "messages")}

    if use_supabase:
        try:
            rows = fetch_supabase_users()
            for row in rows:
                get_or_create_user(
                    row.get("username", ""),
                    (row.get("email") or "").strip().lower() or None,
                    row.get("password"),
                    stats,
                )
            print(f"Supabase: получено {len(rows)} пользователей")
        except Exception as error:
            print(f"Supabase недоступен ({error}) — пропускаю, переношу только .txt")

    for line in read_lines("users.txt"):
        parts = line.split(",")
        if len(parts) >= 3:
            email = parts[1].strip().lower()
            get_or_create_user(parts[0], email if "@" in email else None, parts[2].strip(), stats)

    # Сопоставление «автор + текст» → пост, потому что в старых файлах у постов нет id
    posts = {}
    for line in read_lines("posts.txt"):
        if ":" not in line:
            continue
        name, text = line.split(":", 1)
        author = get_or_create_user(name, stats=stats)
        text = text.strip()
        if author is None or not text:
            continue
        post = Post.query.filter_by(author_id=author.id, text=text).first()
        if post is None:
            post = Post(author_id=author.id, text=text)
            db.session.add(post)
            db.session.flush()
            stats["posts"] += 1
        posts[(name.strip(), text)] = post

    def find_post(author_name, text):
        key = (author_name.strip(), text.strip())
        if key not in posts:
            # Пост лайкнули/прокомментировали, но в posts.txt его уже нет — восстанавливаем
            author = get_or_create_user(author_name, stats=stats)
            if author is None or not key[1]:
                return None
            post = Post.query.filter_by(author_id=author.id, text=key[1]).first()
            if post is None:
                post = Post(author_id=author.id, text=key[1])
                db.session.add(post)
                db.session.flush()
                stats["posts"] += 1
            posts[key] = post
        return posts[key]

    for line in read_lines("likes.txt"):
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        post = find_post(parts[0], parts[1])
        user = get_or_create_user(parts[2], stats=stats)
        if post and user and not db.session.get(Like, (user.id, post.id)):
            db.session.add(Like(user_id=user.id, post_id=post.id))
            db.session.flush()
            stats["likes"] += 1

    for line in read_lines("comments.txt"):
        parts = line.split("|", 3)
        if len(parts) != 4:
            continue
        post = find_post(parts[0], parts[1])
        user = get_or_create_user(parts[2], stats=stats)
        text = parts[3].strip()
        if post and user and text and not Comment.query.filter_by(
            post_id=post.id, author_id=user.id, text=text
        ).first():
            db.session.add(Comment(post_id=post.id, author_id=user.id, text=text))
            stats["comments"] += 1

    for line in read_lines("follows.txt"):
        parts = line.split("|", 1)
        if len(parts) != 2:
            continue
        follower = get_or_create_user(parts[0], stats=stats)
        followed = get_or_create_user(parts[1], stats=stats)
        if (
            follower and followed and follower.id != followed.id
            and not db.session.get(Follow, (follower.id, followed.id))
        ):
            db.session.add(Follow(follower_id=follower.id, followed_id=followed.id))
            db.session.flush()
            stats["follows"] += 1

    for line in read_lines("messages.txt"):
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        sender = get_or_create_user(parts[0], stats=stats)
        receiver = get_or_create_user(parts[1], stats=stats)
        text = parts[2].strip()
        if sender and receiver and text and not Message.query.filter_by(
            sender_id=sender.id, receiver_id=receiver.id, text=text
        ).first():
            db.session.add(Message(sender_id=sender.id, receiver_id=receiver.id, text=text))
            stats["messages"] += 1

    db.session.commit()
    return stats


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        result = import_all(use_supabase="--no-supabase" not in sys.argv)
    print("Перенесено:", ", ".join(f"{key}: {value}" for key, value in result.items()))
