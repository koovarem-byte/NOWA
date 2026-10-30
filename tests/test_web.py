import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web"))

from app import create_app, db  # noqa: E402


@pytest.fixture
def app(tmp_path):
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(tmp_path / "test.db")})
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
    assert 'class="badge"' not in bob.get("/messages").get_data(as_text=True)

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
