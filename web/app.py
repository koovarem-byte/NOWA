"""NOWA — веб-версия соцсети.

Запуск локально:   python web/app.py
Запуск на сервере: gunicorn --chdir web app:app

База данных берётся из переменной DATABASE_URL (PostgreSQL на хостинге),
а если её нет — используется файл web/instance/nowa.db (SQLite).
"""

import os
import secrets
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Flask, abort, flash, g, jsonify, redirect, render_template,
    request, session, url_for, send_from_directory,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import and_, or_
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

db = SQLAlchemy()

FEED_PAGE_SIZE = 30
MAX_POST_LENGTH = 2000
MAX_COMMENT_LENGTH = 1000
MAX_MESSAGE_LENGTH = 4000


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------- МОДЕЛИ ----------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.String(300), default="")
    created_at = db.Column(db.DateTime, default=now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    # "all" — видят все, "circle" — только близкий круг автора
    visibility = db.Column(db.String(10), default="all", nullable=False)
    created_at = db.Column(db.DateTime, default=now, index=True)
    edited_at = db.Column(db.DateTime)

    author = db.relationship("User")
    likes = db.relationship("Like", cascade="all, delete-orphan")
    comments = db.relationship(
        "Comment", cascade="all, delete-orphan", order_by="Comment.created_at"
    )


class Like(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), primary_key=True)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=now)

    author = db.relationship("User")


class Follow(db.Model):
    follower_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    followed_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)


class CircleMember(db.Model):
    """Близкий круг: owner видит member своим «близким»."""
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=now)
    is_read = db.Column(db.Boolean, default=False, nullable=False)

    sender = db.relationship("User", foreign_keys=[sender_id])


# ---------------- ЛОГИКА ----------------

def is_following(follower, followed):
    return db.session.get(Follow, (follower.id, followed.id)) is not None


def in_circle(owner, member):
    return db.session.get(CircleMember, (owner.id, member.id)) is not None


def visible_posts_query(viewer):
    """Посты, которые viewer имеет право видеть."""
    query = Post.query
    if viewer is None:
        return query.filter(Post.visibility == "all")

    circles = db.session.query(CircleMember.owner_id).filter(
        CircleMember.member_id == viewer.id
    )
    return query.filter(
        or_(
            Post.visibility == "all",
            Post.author_id == viewer.id,
            Post.author_id.in_(circles),
        )
    )


def can_see(viewer, post):
    if post.visibility == "all":
        return True
    if viewer is None:
        return False
    return post.author_id == viewer.id or in_circle(post.author, viewer)


def find_user(username):
    return User.query.filter(db.func.lower(User.username) == username.lower()).first()


def dialogs_for(user):
    """Список диалогов: собеседник, последнее сообщение, число непрочитанных."""
    messages = (
        Message.query
        .filter(or_(Message.sender_id == user.id, Message.receiver_id == user.id))
        .order_by(Message.created_at.desc(), Message.id.desc())
        .all()
    )
    dialogs = {}
    for message in messages:
        other_id = message.receiver_id if message.sender_id == user.id else message.sender_id
        if other_id not in dialogs:
            dialogs[other_id] = {
                "user": db.session.get(User, other_id),
                "last": message,
                "unread": 0,
            }
        if message.receiver_id == user.id and not message.is_read:
            dialogs[other_id]["unread"] += 1
    return list(dialogs.values())


def unread_count(user):
    return Message.query.filter_by(receiver_id=user.id, is_read=False).count()


# ---------------- ПРИЛОЖЕНИЕ ----------------

def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


def create_app(config=None):
    app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))

    database_url = os.environ.get("DATABASE_URL", "")
    # Некоторые хостинги отдают адрес как postgres://, SQLAlchemy ждёт postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    if not database_url:
        os.makedirs(app.instance_path, exist_ok=True)
        database_url = "sqlite:///" + os.path.join(app.instance_path, "nowa.db")

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or load_dev_secret(app.instance_path),
        SQLALCHEMY_DATABASE_URI=database_url,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30,
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    with app.app_context():
        db.create_all()

    register_routes(app)
    return app


def load_dev_secret(instance_path):
    """Секрет для локальной разработки, чтобы сессии не слетали при перезапуске."""
    os.makedirs(instance_path, exist_ok=True)
    path = os.path.join(instance_path, "secret_key")
    if not os.path.exists(path):
        with open(path, "w") as file:
            file.write(secrets.token_hex(32))
    with open(path) as file:
        return file.read().strip()


def register_routes(app):

    @app.before_request
    def load_user_and_check_csrf():
        user_id = session.get("user_id")
        g.user = db.session.get(User, user_id) if user_id else None
        g.lite = request.cookies.get("lite") == "1"

        if request.method == "POST" and not app.config.get("TESTING_NO_CSRF"):
            token = request.form.get("csrf") or request.headers.get("X-CSRF-Token")
            if not token or token != session.get("csrf"):
                abort(400, "Неверный CSRF-токен. Обнови страницу.")

    @app.context_processor
    def inject_globals():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        return {
            "me": g.user,
            "csrf": session["csrf"],
            "lite": g.lite,
            "unread": unread_count(g.user) if g.user else 0,
            "is_following": is_following,
            "in_circle": in_circle,
        }

    @app.template_filter("ago")
    def ago(value):
        seconds = int((now() - value).total_seconds())
        if seconds < 60:
            return "только что"
        if seconds < 3600:
            return f"{seconds // 60} мин назад"
        if seconds < 86400:
            return f"{seconds // 3600} ч назад"
        if seconds < 86400 * 7:
            return f"{seconds // 86400} дн назад"
        return value.strftime("%d.%m.%Y")

    # ---------- PWA ----------

    @app.route("/sw.js")
    def service_worker():
        # Service worker должен лежать в корне, чтобы управлять всем сайтом
        response = send_from_directory(app.static_folder, "sw.js")
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.route("/offline")
    def offline():
        return render_template("offline.html")

    @app.route("/health")
    def health():
        return {"ok": True}

    @app.route("/lite", methods=["POST"])
    def toggle_lite():
        response = redirect(request.referrer or url_for("feed"))
        response.set_cookie(
            "lite", "0" if g.lite else "1", max_age=60 * 60 * 24 * 365, samesite="Lax"
        )
        return response

    # ---------- ВХОД И РЕГИСТРАЦИЯ ----------

    @app.route("/")
    def index():
        if g.user:
            return redirect(url_for("feed"))
        return render_template("index.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            error = None
            if not (3 <= len(username) <= 32) or not all(
                ch.isalnum() or ch in "_." for ch in username
            ):
                error = "Имя: от 3 до 32 символов, только буквы, цифры, _ и ."
            elif "@" not in email or "." not in email.split("@")[-1]:
                error = "Введите настоящую почту."
            elif len(password) < 6:
                error = "Пароль должен быть не короче 6 символов."
            elif find_user(username):
                error = "Это имя уже занято."
            elif User.query.filter_by(email=email).first():
                error = "Такая почта уже зарегистрирована."

            if error:
                flash(error, "error")
                return render_template("register.html", username=username, email=email)

            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            session.clear()
            session.permanent = True
            session["user_id"] = user.id
            flash(f"Добро пожаловать в NOWA, {username}!", "ok")
            return redirect(url_for("feed", tab="all"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            login_value = request.form.get("login", "").strip()
            password = request.form.get("password", "")

            user = User.query.filter_by(email=login_value.lower()).first() or find_user(login_value)
            if user is None or not user.check_password(password):
                flash("Неверный логин или пароль.", "error")
                return render_template("login.html", login=login_value)

            session.clear()
            session.permanent = True
            session["user_id"] = user.id

            next_url = request.args.get("next", "")
            # Разрешаем только относительные ссылки, чтобы не было редиректа на чужой сайт
            if not next_url.startswith("/") or next_url.startswith("//"):
                next_url = url_for("feed")
            return redirect(next_url)

        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return redirect(url_for("index"))

    # ---------- ЛЕНТА И ПОСТЫ ----------

    @app.route("/feed")
    @login_required
    def feed():
        tab = request.args.get("tab", "following")
        before = request.args.get("before", type=int)

        query = visible_posts_query(g.user)
        if tab == "following":
            followed = db.session.query(Follow.followed_id).filter(
                Follow.follower_id == g.user.id
            )
            query = query.filter(
                or_(Post.author_id.in_(followed), Post.author_id == g.user.id)
            )
        if before:
            query = query.filter(Post.id < before)

        posts = query.order_by(Post.id.desc()).limit(FEED_PAGE_SIZE + 1).all()
        has_more = len(posts) > FEED_PAGE_SIZE
        posts = posts[:FEED_PAGE_SIZE]

        return render_template(
            "feed.html", posts=posts, tab=tab, has_more=has_more,
            liked=liked_ids(posts),
        )

    def liked_ids(posts):
        if g.user is None or not posts:
            return set()
        rows = Like.query.filter(
            Like.user_id == g.user.id, Like.post_id.in_([p.id for p in posts])
        )
        return {row.post_id for row in rows}

    @app.route("/post/new", methods=["POST"])
    @login_required
    def new_post():
        text = request.form.get("text", "").strip()
        visibility = "circle" if request.form.get("visibility") == "circle" else "all"

        if not text:
            flash("Пост не может быть пустым.", "error")
        elif len(text) > MAX_POST_LENGTH:
            flash(f"Пост слишком длинный (максимум {MAX_POST_LENGTH} символов).", "error")
        else:
            db.session.add(Post(author_id=g.user.id, text=text, visibility=visibility))
            db.session.commit()
            flash("Пост опубликован!", "ok")
        return redirect(request.referrer or url_for("feed"))

    def get_visible_post(post_id):
        post = db.session.get(Post, post_id)
        if post is None or not can_see(g.user, post):
            abort(404)
        return post

    @app.route("/post/<int:post_id>")
    def view_post(post_id):
        post = get_visible_post(post_id)
        return render_template("post.html", post=post, liked=liked_ids([post]))

    @app.route("/post/<int:post_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_post(post_id):
        post = get_visible_post(post_id)
        if post.author_id != g.user.id:
            abort(403)

        if request.method == "POST":
            text = request.form.get("text", "").strip()
            if not text or len(text) > MAX_POST_LENGTH:
                flash("Текст поста пустой или слишком длинный.", "error")
                return render_template("edit_post.html", post=post)
            post.text = text
            post.visibility = "circle" if request.form.get("visibility") == "circle" else "all"
            post.edited_at = now()
            db.session.commit()
            flash("Пост изменён.", "ok")
            return redirect(url_for("view_post", post_id=post.id))

        return render_template("edit_post.html", post=post)

    @app.route("/post/<int:post_id>/delete", methods=["POST"])
    @login_required
    def delete_post(post_id):
        post = get_visible_post(post_id)
        if post.author_id != g.user.id:
            abort(403)
        db.session.delete(post)
        db.session.commit()
        flash("Пост удалён.", "ok")
        return redirect(url_for("profile", username=g.user.username))

    @app.route("/post/<int:post_id>/like", methods=["POST"])
    @login_required
    def like_post(post_id):
        post = get_visible_post(post_id)
        like = db.session.get(Like, (g.user.id, post.id))
        if like:
            db.session.delete(like)
        else:
            db.session.add(Like(user_id=g.user.id, post_id=post.id))
        db.session.commit()

        if request.headers.get("Accept") == "application/json":
            return jsonify(liked=like is None, count=Like.query.filter_by(post_id=post.id).count())
        return redirect(request.referrer or url_for("view_post", post_id=post.id))

    @app.route("/post/<int:post_id>/comment", methods=["POST"])
    @login_required
    def comment_post(post_id):
        post = get_visible_post(post_id)
        text = request.form.get("text", "").strip()
        if not text or len(text) > MAX_COMMENT_LENGTH:
            flash("Комментарий пустой или слишком длинный.", "error")
        else:
            db.session.add(Comment(post_id=post.id, author_id=g.user.id, text=text))
            db.session.commit()
        return redirect(url_for("view_post", post_id=post.id) + "#comments")

    @app.route("/comment/<int:comment_id>/delete", methods=["POST"])
    @login_required
    def delete_comment(comment_id):
        comment = db.session.get(Comment, comment_id) or abort(404)
        post = db.session.get(Post, comment.post_id)
        # Удалить может автор комментария или автор поста
        if g.user.id not in (comment.author_id, post.author_id):
            abort(403)
        db.session.delete(comment)
        db.session.commit()
        return redirect(url_for("view_post", post_id=post.id) + "#comments")

    # ---------- ПРОФИЛИ ----------

    @app.route("/u/<username>")
    def profile(username):
        user = find_user(username) or abort(404)
        posts = (
            visible_posts_query(g.user)
            .filter(Post.author_id == user.id)
            .order_by(Post.id.desc())
            .all()
        )
        stats = {
            "posts": Post.query.filter_by(author_id=user.id).count(),
            "followers": Follow.query.filter_by(followed_id=user.id).count(),
            "following": Follow.query.filter_by(follower_id=user.id).count(),
        }
        return render_template(
            "profile.html", user=user, posts=posts, stats=stats, liked=liked_ids(posts)
        )

    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        if request.method == "POST":
            g.user.bio = request.form.get("bio", "").strip()[:300]
            db.session.commit()
            flash("Профиль сохранён.", "ok")
            return redirect(url_for("profile", username=g.user.username))
        circle = (
            User.query.join(CircleMember, CircleMember.member_id == User.id)
            .filter(CircleMember.owner_id == g.user.id)
            .order_by(User.username)
            .all()
        )
        return render_template("settings.html", circle=circle)

    @app.route("/u/<username>/follow", methods=["POST"])
    @login_required
    def follow(username):
        user = find_user(username) or abort(404)
        if user.id != g.user.id:
            existing = db.session.get(Follow, (g.user.id, user.id))
            if existing:
                db.session.delete(existing)
            else:
                db.session.add(Follow(follower_id=g.user.id, followed_id=user.id))
            db.session.commit()
        return redirect(request.referrer or url_for("profile", username=user.username))

    @app.route("/u/<username>/circle", methods=["POST"])
    @login_required
    def toggle_circle(username):
        user = find_user(username) or abort(404)
        if user.id != g.user.id:
            existing = db.session.get(CircleMember, (g.user.id, user.id))
            if existing:
                db.session.delete(existing)
                flash(f"{user.username} больше не в близком круге.", "ok")
            else:
                db.session.add(CircleMember(owner_id=g.user.id, member_id=user.id))
                flash(f"{user.username} теперь в близком круге.", "ok")
            db.session.commit()
        return redirect(request.referrer or url_for("profile", username=user.username))

    # ---------- ПОИСК ----------

    @app.route("/search")
    @login_required
    def search():
        q = request.args.get("q", "").strip()
        users, posts = [], []
        if q:
            pattern = f"%{q}%"
            users = (
                User.query.filter(User.username.ilike(pattern))
                .order_by(User.username).limit(20).all()
            )
            posts = (
                visible_posts_query(g.user).filter(Post.text.ilike(pattern))
                .order_by(Post.id.desc()).limit(30).all()
            )
        return render_template(
            "search.html", q=q, users=users, posts=posts, liked=liked_ids(posts)
        )

    # ---------- СООБЩЕНИЯ ----------

    def chat_query(user, other):
        return Message.query.filter(
            or_(
                and_(Message.sender_id == user.id, Message.receiver_id == other.id),
                and_(Message.sender_id == other.id, Message.receiver_id == user.id),
            )
        )

    def mark_read(user, other):
        Message.query.filter_by(
            sender_id=other.id, receiver_id=user.id, is_read=False
        ).update({"is_read": True})
        db.session.commit()

    def message_json(message):
        return {
            "id": message.id,
            "mine": message.sender_id == g.user.id,
            "text": message.text,
            "time": message.created_at.strftime("%H:%M"),
        }

    @app.route("/messages")
    @login_required
    def messages():
        return render_template("messages.html", dialogs=dialogs_for(g.user))

    @app.route("/messages/<username>", methods=["GET", "POST"])
    @login_required
    def chat(username):
        other = find_user(username) or abort(404)
        if other.id == g.user.id:
            return redirect(url_for("messages"))

        if request.method == "POST":
            text = request.form.get("text", "").strip()
            if text and len(text) <= MAX_MESSAGE_LENGTH:
                message = Message(sender_id=g.user.id, receiver_id=other.id, text=text)
                db.session.add(message)
                db.session.commit()
                if request.headers.get("Accept") == "application/json":
                    return jsonify(message_json(message))
            elif request.headers.get("Accept") == "application/json":
                return jsonify(error="Пустое или слишком длинное сообщение"), 400
            return redirect(url_for("chat", username=other.username))

        history = chat_query(g.user, other).order_by(Message.id).all()
        mark_read(g.user, other)
        return render_template("chat.html", other=other, history=history)

    @app.route("/api/messages/<username>")
    @login_required
    def new_messages(username):
        other = find_user(username) or abort(404)
        after = request.args.get("after", 0, type=int)
        history = chat_query(g.user, other).filter(Message.id > after).order_by(Message.id).all()
        if history:
            mark_read(g.user, other)
        return jsonify([message_json(m) for m in history])

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", code=404, text="Такой страницы нет."), 404

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("error.html", code=403, text="Сюда нельзя."), 403

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("error.html", code=400, text=error.description), 400


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
