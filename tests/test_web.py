import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web"))

from app import create_app, db  # noqa: E402


@pytest.fixture
def app(tmp_path):
    # TEST_DATABASE_URL=postgresql://... — прогнать тесты на PostgreSQL, как на сервере
    url = os.environ.get("TEST_DATABASE_URL") or "sqlite:///" + str(tmp_path / "test.db")
    app = create_app({"SQLALCHEMY_DATABASE_URI": url})
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def csrf_of(client):
    page = client.get("/login").get_data(as_text=True)
    return re.search(r'name="csrf" content="([0-9a-f]+)"', page).group(1)


def register(client, username, email=None, password="secret123"):
    token = csrf_of(client)
    return client.post("/register", data={
        "username": username, "email": email or f"{username}@mail.ru",
        "password": password, "csrf": token,
    })


def post(client, url, **data):
    return client.post(url, data={**data, "csrf": csrf_of(client)}, follow_redirects=True)


def test_register_login_and_password_is_hashed(app):
    client = app.test_client()
    assert register(client, "artem").status_code == 302

    from app import User
    with app.app_context():
        user = User.query.filter_by(username="artem").first()
        assert user.password_hash != "secret123"

    post(client, "/logout")
    response = post(client, "/login", login="artem@mail.ru", password="secret123")
    assert "Лента" in response.get_data(as_text=True)

    post(client, "/logout")
    response = post(client, "/login", login="artem", password="wrong")
    assert "Неверный логин или пароль" in response.get_data(as_text=True)


def test_post_without_csrf_is_rejected(app):
    client = app.test_client()
    register(client, "artem")
    assert client.post("/post/new", data={"text": "привет"}).status_code == 400


def test_duplicate_username_and_email(app):
    client = app.test_client()
    register(client, "artem")
    post(client, "/logout")
    assert "уже занято" in register(client, "ARTEM", "other@mail.ru").get_data(as_text=True)
    assert "уже зарегистрирована" in register(client, "bob", "artem@mail.ru").get_data(as_text=True)


def test_posts_likes_comments_edit_delete(app):
    client = app.test_client()
    register(client, "artem")
    post(client, "/post/new", text="Привет, NOWA!")
    post(client, "/post/new", text="Привет, NOWA!")  # одинаковый текст — это разные посты

    page = client.get("/feed").get_data(as_text=True)
    assert page.count("Привет, NOWA!") == 2
    assert "Ты всё посмотрел" in page

    post(client, "/post/1/like")
    from app import Like, Post
    with app.app_context():
        assert Like.query.filter_by(post_id=1).count() == 1
        assert Like.query.filter_by(post_id=2).count() == 0
    post(client, "/post/1/like")
    with app.app_context():
        assert Like.query.count() == 0

    page = post(client, "/post/1/comment", text="Первый!").get_data(as_text=True)
    assert "Первый!" in page

    post(client, "/post/1/edit", text="Новый текст")
    assert "Новый текст" in client.get("/post/1").get_data(as_text=True)

    post(client, "/post/1/delete")
    with app.app_context():
        assert db.session.get(Post, 1) is None
    assert client.get("/post/1").status_code == 404


def test_cannot_edit_someone_elses_post(app):
    author, other = app.test_client(), app.test_client()
    register(author, "artem")
    post(author, "/post/new", text="мой пост")
    register(other, "bob")
    assert other.post("/post/1/delete", data={"csrf": csrf_of(other)}).status_code == 403


def test_like_requires_login(app):
    client = app.test_client()
    register(client, "artem")
    post(client, "/post/new", text="пост")
    anon = app.test_client()
    response = anon.post("/post/1/like", data={"csrf": csrf_of(anon)})
    assert response.status_code == 302 and "/login" in response.location


def test_following_feed_and_circle_visibility(app):
    artem, bob, eve = app.test_client(), app.test_client(), app.test_client()
    register(artem, "artem")
    register(bob, "bob")
    register(eve, "eve")

    post(artem, "/post/new", text="для всех")
    post(artem, "/post/new", text="секрет для круга", visibility="circle")
    post(artem, "/u/bob/circle")

    # bob не подписан — во вкладке «Подписки» пусто, во «Все» видны посты
    assert "для всех" not in bob.get("/feed").get_data(as_text=True)
    post(bob, "/u/artem/follow")
    page = bob.get("/feed").get_data(as_text=True)
    assert "для всех" in page and "секрет для круга" in page

    # eve не в круге — закрытый пост не видит нигде
    assert "секрет для круга" not in eve.get("/feed?tab=all").get_data(as_text=True)
    assert "секрет для круга" not in eve.get("/u/artem").get_data(as_text=True)
    assert "секрет для круга" not in eve.get("/search?q=секрет").get_data(as_text=True)
    assert eve.get("/post/2").status_code == 404


def test_messages_and_unread(app):
    artem, bob = app.test_client(), app.test_client()
    register(artem, "artem")
    register(bob, "bob")

    post(artem, "/messages/bob", text="Привет, Боб")
    page = bob.get("/messages").get_data(as_text=True)
    assert "Привет, Боб" in page and 'class="badge">1<' in page

    assert "Привет, Боб" in bob.get("/messages/artem").get_data(as_text=True)
    assert 'class="badge">1<' not in bob.get("/messages").get_data(as_text=True)

    response = artem.get("/api/messages/bob?after=0")
    assert response.get_json()[0]["text"] == "Привет, Боб"
    assert artem.get("/api/messages/bob?after=1").get_json() == []


def test_login_redirect_is_not_open(app):
    client = app.test_client()
    register(client, "artem")
    post(client, "/logout")
    response = client.post("/login?next=//evil.com", data={
        "login": "artem", "password": "secret123", "csrf": csrf_of(client),
    })
    assert response.location.endswith("/feed")


def test_pwa_files(app):
    client = app.test_client()
    assert client.get("/sw.js").status_code == 200
    assert client.get("/static/manifest.webmanifest").status_code == 200
    assert client.get("/offline").status_code == 200


def test_import_old_data(app, tmp_path, monkeypatch):
    import import_old_data

    (tmp_path / "users.txt").write_text("Artemiy,a@mail.ru,pass1234\n", encoding="utf-8")
    (tmp_path / "posts.txt").write_text("Artemiy: Всем привет\nыы: Привет мир\n", encoding="utf-8")
    (tmp_path / "likes.txt").write_text("ыы|Привет мир|Artemiy\nыы|Привет мир|None\n", encoding="utf-8")
    (tmp_path / "comments.txt").write_text("ыы|Привет мир|Artemiy|круто\n", encoding="utf-8")
    (tmp_path / "follows.txt").write_text("Artemiy|ыы\n", encoding="utf-8")
    (tmp_path / "messages.txt").write_text("Artemiy|ыы|Привет родной\n", encoding="utf-8")
    monkeypatch.setattr(import_old_data, "ROOT", str(tmp_path))

    with app.app_context():
        first = import_old_data.import_all(use_supabase=False)
        second = import_old_data.import_all(use_supabase=False)

    assert first == {"users": 2, "posts": 2, "likes": 1, "comments": 1, "follows": 1, "messages": 1}
    assert all(value == 0 for value in second.values())

    client = app.test_client()
    page = post(client, "/login", login="a@mail.ru", password="pass1234").get_data(as_text=True)
    assert "Всем привет" in page


def png_bytes(size=(1600, 900), color=(10, 132, 255)):
    from io import BytesIO
    from PIL import Image
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    buffer.seek(0)
    return buffer


def upload(client, url, **data):
    return client.post(url, data={**data, "csrf": csrf_of(client)},
                       content_type="multipart/form-data", follow_redirects=True)


def test_post_with_photo_is_compressed_and_served(app):
    client = app.test_client()
    register(client, "artem")
    upload(client, "/post/new", text="", image=(png_bytes(), "cat.png"))

    from app import Image, Post
    with app.app_context():
        saved = db.session.get(Post, 1)
        assert saved.image.mime == "image/webp"
        assert max(saved.image.width, saved.image.height) == 1280
        image_id = saved.image_id

    response = client.get(f"/img/{image_id}")
    assert response.status_code == 200 and response.mimetype == "image/webp"
    assert f"/img/{image_id}" in client.get("/feed").get_data(as_text=True)

    # В экономном режиме фото не грузится сразу — только кнопка
    client.set_cookie("lite", "1")
    page = client.get("/feed").get_data(as_text=True)
    assert "Показать фото" in page and f'<img class="photo" src="/img/{image_id}"' not in page

    post(client, "/post/1/delete")
    with app.app_context():
        assert db.session.get(Image, image_id) is None


def test_not_an_image_is_rejected(app):
    from io import BytesIO
    client = app.test_client()
    register(client, "artem")
    page = upload(client, "/post/new", text="", image=(BytesIO(b"not an image"), "x.png"))
    assert "Не получилось открыть фото" in page.get_data(as_text=True)


def test_circle_photo_is_private(app):
    artem, eve = app.test_client(), app.test_client()
    register(artem, "artem")
    register(eve, "eve")
    upload(artem, "/post/new", text="", visibility="circle", image=(png_bytes(), "p.png"))
    assert artem.get("/img/1").status_code == 200
    assert eve.get("/img/1").status_code == 404


def test_avatar_upload_and_remove(app):
    client = app.test_client()
    register(client, "artem")
    upload(client, "/settings", bio="Привет", avatar=(png_bytes((800, 500)), "me.png"))

    from app import Image, User
    with app.app_context():
        user = User.query.filter_by(username="artem").first()
        avatar = db.session.get(Image, user.avatar_id)
        assert (avatar.width, avatar.height) == (256, 256)

    assert 'img class="avatar big"' in client.get("/u/artem").get_data(as_text=True)

    upload(client, "/settings", bio="Привет", remove_avatar="1")
    with app.app_context():
        assert User.query.filter_by(username="artem").first().avatar_id is None
        assert Image.query.count() == 0


def test_scheduled_post(app):
    from datetime import timedelta
    from app import Post, now

    artem, bob = app.test_client(), app.test_client()
    register(artem, "artem")
    register(bob, "bob")
    post(bob, "/u/artem/follow")

    future = (now() + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
    page = post(artem, "/post/new", text="из будущего", publish_at=future, tz_offset="0")
    assert "запланирован" in page.get_data(as_text=True)

    # Автор видит с пометкой, остальные — нет
    assert "⏰ выйдет" in artem.get("/feed").get_data(as_text=True)
    assert "из будущего" not in bob.get("/feed").get_data(as_text=True)
    assert "из будущего" not in bob.get("/u/artem").get_data(as_text=True)
    assert bob.get("/post/1").status_code == 404

    # Время наступило — пост появился у подписчика
    with app.app_context():
        db.session.get(Post, 1).published_at = now() - timedelta(minutes=1)
        db.session.commit()
    assert "из будущего" in bob.get("/feed").get_data(as_text=True)


def test_scheduled_post_timezone_and_past_time(app):
    from datetime import timedelta
    from app import Post, now

    client = app.test_client()
    register(client, "artem")

    past = (now() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
    page = post(client, "/post/new", text="x", publish_at=past, tz_offset="0")
    assert "должно быть в будущем" in page.get_data(as_text=True)

    # Москва: UTC+3, браузер отдаёт смещение -180 минут
    moscow = (now() + timedelta(hours=3 + 2)).strftime("%Y-%m-%dT%H:%M")
    post(client, "/post/new", text="y", publish_at=moscow, tz_offset="-180")
    with app.app_context():
        delay = db.session.get(Post, 1).published_at - now()
        assert timedelta(hours=1, minutes=58) < delay < timedelta(hours=2, minutes=1)


def test_publish_scheduled_post_now(app):
    from datetime import timedelta
    from app import now

    artem, bob = app.test_client(), app.test_client()
    register(artem, "artem")
    register(bob, "bob")
    future = (now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    post(artem, "/post/new", text="скоро", publish_at=future, tz_offset="0")
    post(artem, "/post/1/edit", text="уже сейчас", publish_now="1")
    assert "уже сейчас" in bob.get("/feed?tab=all").get_data(as_text=True)


def test_disappearing_messages(app):
    from datetime import timedelta
    from app import Message, now

    artem, bob = app.test_client(), app.test_client()
    register(artem, "artem")
    register(bob, "bob")

    post(artem, "/messages/bob", text="обычное")
    post(artem, "/messages/bob/timer", seconds="3600")
    post(artem, "/messages/bob", text="секретное")

    page = bob.get("/messages/artem").get_data(as_text=True)
    assert "секретное" in page and "исчезают через 1 час" in page
    assert 'value="3600" selected' in page

    with app.app_context():
        secret = Message.query.filter_by(text="секретное").first()
        assert timedelta(minutes=59) < secret.expires_at - now() <= timedelta(hours=1)
        assert Message.query.filter_by(text="обычное").first().expires_at is None
        secret.expires_at = now() - timedelta(seconds=1)
        db.session.commit()

    page = bob.get("/messages/artem").get_data(as_text=True)
    assert "секретное" not in page and "обычное" in page

    assert artem.post("/messages/bob/timer", data={
        "seconds": "5", "csrf": csrf_of(artem)}).status_code == 400


def test_notifications(app):
    artem, bob = app.test_client(), app.test_client()
    register(artem, "artem")
    register(bob, "bob")
    post(artem, "/post/new", text="мой пост")
    post(artem, "/post/1/like")  # свой лайк — без уведомления

    post(bob, "/u/artem/follow")
    post(bob, "/post/1/like")
    post(bob, "/post/1/comment", text="класс")

    assert artem.get("/api/counters").get_json() == {"messages": 0, "notifications": 3}
    page = artem.get("/notifications").get_data(as_text=True)
    assert "подписался" in page and "оценил" in page and "прокомментировал" in page
    assert artem.get("/api/counters").get_json()["notifications"] == 0

    # Убрал лайк — уведомление тоже исчезло
    post(bob, "/post/1/like")
    assert "оценил" not in artem.get("/notifications").get_data(as_text=True)


def test_old_database_is_upgraded(tmp_path):
    import sqlite3
    path = tmp_path / "old.db"
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE user (id INTEGER PRIMARY KEY, username VARCHAR(32) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL, password_hash VARCHAR(255) NOT NULL,
            bio VARCHAR(300), created_at DATETIME);
        CREATE TABLE post (id INTEGER PRIMARY KEY, author_id INTEGER NOT NULL, text TEXT NOT NULL,
            visibility VARCHAR(10) NOT NULL, created_at DATETIME, edited_at DATETIME);
        CREATE TABLE message (id INTEGER PRIMARY KEY, sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL, text TEXT NOT NULL, created_at DATETIME,
            is_read BOOLEAN NOT NULL);
        INSERT INTO user VALUES (1, 'artem', 'a@a.ru', 'x', '', '2026-01-01 10:00:00');
        INSERT INTO post VALUES (1, 1, 'старый пост', 'all', '2026-01-01 10:00:00', NULL);
    """)
    connection.close()

    app = create_app({"SQLALCHEMY_DATABASE_URI": f"sqlite:///{path}"})
    with app.app_context():
        from app import Post
        assert str(db.session.get(Post, 1).published_at) == "2026-01-01 10:00:00"
        db.engine.dispose()
