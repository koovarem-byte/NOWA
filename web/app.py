"""NOWA — веб-версия соцсети.

Запуск локально:   python web/app.py
Запуск на сервере: gunicorn --chdir web app:app   (или через Dockerfile в корне)

База данных берётся из переменной DATABASE_URL (PostgreSQL на хостинге),
а если её нет — используется файл web/instance/nowa.db (SQLite).
"""

import io
import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (
    Flask, Response, abort, flash, g, jsonify, redirect, render_template,
    request, session, url_for, send_from_directory,
)
from flask_sqlalchemy import SQLAlchemy
from PIL import Image as PILImage, ImageOps, UnidentifiedImageError
from sqlalchemy import and_, inspect, or_, text
from werkzeug.exceptions import NotFound
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

db = SQLAlchemy()

FEED_PAGE_SIZE = 30
MAX_POST_LENGTH = 2000
MAX_COMMENT_LENGTH = 1000
MAX_MESSAGE_LENGTH = 4000
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
POST_IMAGE_SIZE = 1280
AVATAR_SIZE = 256

# Таймеры исчезающих сообщений: секунды -> подпись
CHAT_TIMERS = {
    0: "выкл",
    60 * 60: "1 час",
    60 * 60 * 24: "1 день",
    60 * 60 * 24 * 7: "7 дней",
}

# Маяки: «я свободен сейчас — кто со мной?»
BEACON_ACTIVITIES = {
    "coffee": ("☕", "Кофе"),
    "walk": ("🚶", "Гулять"),
    "food": ("🍕", "Поесть"),
    "movie": ("🎬", "Кино"),
    "games": ("🎮", "Поиграть"),
    "sport": ("⚽", "Спорт"),
    "study": ("📚", "Учиться"),
    "other": ("✨", "Своё"),
}
BEACON_DURATIONS = {1: "1 час", 3: "3 часа", 6: "6 часов"}
MAX_BEACON_NOTIFY = 200

# День для «Вопроса дня» считаем по Москве — там основная аудитория
DAY_OFFSET = timedelta(hours=3)

DAILY_QUESTIONS = [
    "Что тебя сегодня порадовало?",
    "Какую песню ты слушаешь на повторе?",
    "Куда бы ты поехал(а) прямо сейчас, если бы можно было без денег и сборов?",
    "Чему ты научился(ась) за последний месяц?",
    "Какой фильм или сериал посоветуешь друзьям?",
    "Что бы ты сделал(а), если бы завтра не надо было никуда идти?",
    "Какая еда — твоё лучшее утешение?",
    "Кто из друзей тебя недавно выручил?",
    "Самое странное, что ты видел(а) на этой неделе?",
    "Какая привычка тебе реально помогает?",
    "О чём ты мечтаешь, но пока никому не говорил(а)?",
    "Если бы у тебя был свой канал, о чём бы он был?",
    "Лучший совет, который тебе давали?",
    "Где в твоём городе лучше всего гулять?",
    "Какой навык ты бы прокачал(а) за один день, если бы мог(ла)?",
    "Что тебя бесит больше всего в соцсетях?",
    "Какая книга или видео изменили твоё мнение о чём-то?",
    "Какой момент этого года ты бы пережил(а) ещё раз?",
    "Что ты ешь на завтрак?",
    "С кем из известных людей ты бы сходил(а) на кофе?",
    "Какое приложение на телефоне ты бы удалил(а) первым?",
    "Чего ты ждёшь от этих выходных?",
    "Какая игра — твоя любимая за всё время?",
    "Что самое смешное случилось с тобой в школе или универе?",
    "Если бы можно было выучить любой язык за ночь — какой?",
    "Твоё идеальное воскресенье — какое оно?",
    "О чём ты передумал(а) за последний год?",
    "Чем ты гордишься, но редко рассказываешь?",
    "Какой звук или запах напоминает тебе детство?",
    "Что ты сделаешь сегодня, чтобы день был хорошим?",
    "Какую суперсилу выбрал(а) бы на один день?",
    "Какой твой любимый способ отдохнуть от телефона?",
    "Куда ты хочешь сходить с друзьями в ближайший месяц?",
    "Какой вопрос ты бы задал(а) всем в NOWA?",
]

PILImage.MAX_IMAGE_PIXELS = 40_000_000


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------- МОДЕЛИ ----------------

class Image(db.Model):
    """Картинки храним прямо в базе: так их не потеряешь при переезде
    или перезапуске сервера, и не нужно настраивать отдельное хранилище."""
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    data = db.Column(db.LargeBinary, nullable=False)
    mime = db.Column(db.String(30), nullable=False)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=now)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.String(300), default="")
    avatar_id = db.Column(db.Integer, db.ForeignKey("image.id", use_alter=True, name="fk_user_avatar"))
    invite_code = db.Column(db.String(16), unique=True)
    invited_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=now)

    def get_invite_code(self):
        if not self.invite_code:
            self.invite_code = secrets.token_urlsafe(6)
            db.session.commit()
        return self.invite_code

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False, default="")
    image_id = db.Column(db.Integer, db.ForeignKey("image.id"))
    # "all" — видят все, "circle" — только близкий круг автора
    visibility = db.Column(db.String(10), default="all", nullable=False)
    created_at = db.Column(db.DateTime, default=now)
    # Когда пост появляется в ленте. Для отложенных постов — в будущем.
    published_at = db.Column(db.DateTime, default=now, index=True)
    edited_at = db.Column(db.DateTime)

    author = db.relationship("User")
    image = db.relationship("Image")
    likes = db.relationship("Like", cascade="all, delete-orphan")
    comments = db.relationship(
        "Comment", cascade="all, delete-orphan", order_by="Comment.created_at"
    )

    @property
    def is_scheduled(self):
        return self.published_at > now()


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
    # Если задано — сообщение удаляется в это время
    expires_at = db.Column(db.DateTime, index=True)

    sender = db.relationship("User", foreign_keys=[sender_id])


class ChatTimer(db.Model):
    """Таймер исчезающих сообщений для диалога. user_a_id всегда меньше user_b_id."""
    user_a_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    user_b_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    seconds = db.Column(db.Integer, nullable=False, default=0)


class Beacon(db.Model):
    """Маяк: «я свободен — кто со мной?». Гаснет в expires_at вместе со своим чатом."""
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    activity = db.Column(db.String(20), nullable=False, default="other")
    title = db.Column(db.String(80), nullable=False, default="")
    place = db.Column(db.String(120), nullable=False, default="")
    # "friends" — взаимные подписки, "circle" — только близкий круг
    audience = db.Column(db.String(10), nullable=False, default="friends")
    starts_at = db.Column(db.DateTime, nullable=False, default=now)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    # Секрет для ссылки: кто получил ссылку, тот может посмотреть маяк и присоединиться
    token = db.Column(db.String(16), unique=True, nullable=False,
                      default=lambda: secrets.token_urlsafe(9))
    created_at = db.Column(db.DateTime, default=now)

    author = db.relationship("User")
    members = db.relationship(
        "BeaconMember", cascade="all, delete-orphan", order_by="BeaconMember.joined_at"
    )
    messages = db.relationship(
        "BeaconMessage", cascade="all, delete-orphan", order_by="BeaconMessage.id"
    )

    @property
    def emoji(self):
        return BEACON_ACTIVITIES.get(self.activity, BEACON_ACTIVITIES["other"])[0]

    @property
    def label(self):
        if self.title:
            return self.title
        return BEACON_ACTIVITIES.get(self.activity, BEACON_ACTIVITIES["other"])[1]

    @property
    def started(self):
        return self.starts_at <= now()

    def has_member(self, user):
        return user is not None and any(m.user_id == user.id for m in self.members)


class BeaconMember(db.Model):
    beacon_id = db.Column(db.Integer, db.ForeignKey("beacon.id"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    joined_at = db.Column(db.DateTime, default=now)

    user = db.relationship("User")


class BeaconMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    beacon_id = db.Column(db.Integer, db.ForeignKey("beacon.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=now)

    user = db.relationship("User")


class Answer(db.Model):
    """Ответ на «Вопрос дня». Один ответ в день."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    day = db.Column(db.Date, nullable=False, index=True)
    text = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=now)

    user = db.relationship("User")

    __table_args__ = (db.UniqueConstraint("user_id", "day"),)


class Block(db.Model):
    """blocker больше не видит blocked и наоборот; писать и звать друг друга нельзя."""
    blocker_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    blocked_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    created_at = db.Column(db.DateTime, default=now)


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id", ondelete="SET NULL"))
    beacon_id = db.Column(db.Integer, db.ForeignKey("beacon.id", ondelete="SET NULL"))
    reason = db.Column(db.String(30), nullable=False)
    comment = db.Column(db.String(500), nullable=False, default="")
    created_at = db.Column(db.DateTime, default=now)
    resolved = db.Column(db.Boolean, default=False, nullable=False)

    reporter = db.relationship("User", foreign_keys=[reporter_id])
    target = db.relationship("User", foreign_keys=[target_user_id])
    post = db.relationship("Post", backref=db.backref("reports", passive_deletes=True))
    beacon = db.relationship("Beacon", backref=db.backref("reports", passive_deletes=True))


REPORT_REASONS = {
    "spam": "Спам или реклама",
    "abuse": "Оскорбления или травля",
    "danger": "Угрозы или опасная встреча",
    "nsfw": "Неприемлемый контент",
    "fake": "Выдаёт себя за другого",
    "other": "Другое",
}


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    # "like", "comment", "follow", "beacon", "beacon_join", "invite"
    kind = db.Column(db.String(20), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id", ondelete="CASCADE"))
    beacon_id = db.Column(db.Integer, db.ForeignKey("beacon.id", ondelete="CASCADE"))
    created_at = db.Column(db.DateTime, default=now)
    is_read = db.Column(db.Boolean, default=False, nullable=False)

    actor = db.relationship("User", foreign_keys=[actor_id])
    post = db.relationship("Post", backref=db.backref("notifications", cascade="all, delete-orphan"))
    beacon = db.relationship("Beacon", backref=db.backref("notifications", cascade="all, delete-orphan"))


def upgrade_schema():
    """create_all не добавляет новые колонки в старые таблицы — дописываем их сами."""
    columns = {
        "user": [("avatar_id", "INTEGER"), ("invite_code", "VARCHAR(16)"), ("invited_by_id", "INTEGER")],
        "notification": [("beacon_id", "INTEGER")],
        "post": [("image_id", "INTEGER"), ("published_at", "TIMESTAMP")],
        "message": [("expires_at", "TIMESTAMP")],
    }
    inspector = inspect(db.engine)
    with db.engine.begin() as connection:
        for table, new_columns in columns.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, sql_type in new_columns:
                if name not in existing:
                    connection.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {name} {sql_type}'))
        connection.execute(text("UPDATE post SET published_at = created_at WHERE published_at IS NULL"))


# ---------------- ЛОГИКА ----------------

def is_following(follower, followed):
    return db.session.get(Follow, (follower.id, followed.id)) is not None


def in_circle(owner, member):
    return db.session.get(CircleMember, (owner.id, member.id)) is not None


def blocked_ids(user):
    """Все, с кем у user блокировка в любую сторону."""
    if user is None:
        return []
    rows = Block.query.filter(or_(Block.blocker_id == user.id, Block.blocked_id == user.id))
    return [row.blocked_id if row.blocker_id == user.id else row.blocker_id for row in rows]


def is_blocked_between(a_id, b_id):
    return Block.query.filter(or_(
        and_(Block.blocker_id == a_id, Block.blocked_id == b_id),
        and_(Block.blocker_id == b_id, Block.blocked_id == a_id),
    )).first() is not None


def visible_posts_query(viewer):
    """Посты, которые viewer имеет право видеть. Свои отложенные посты автор видит сразу."""
    published = Post.published_at <= now()
    if viewer is None:
        return Post.query.filter(Post.visibility == "all", published)

    circles = db.session.query(CircleMember.owner_id).filter(
        CircleMember.member_id == viewer.id
    )
    return Post.query.filter(
        Post.author_id.not_in(blocked_ids(viewer)),
        or_(
            Post.author_id == viewer.id,
            and_(
                published,
                or_(Post.visibility == "all", Post.author_id.in_(circles)),
            ),
        )
    )


def newest_first(query):
    return query.order_by(Post.published_at.desc(), Post.id.desc())


def can_see(viewer, post):
    if viewer is not None and post.author_id == viewer.id:
        return True
    if viewer is not None and is_blocked_between(viewer.id, post.author_id):
        return False
    if post.is_scheduled:
        return False
    if post.visibility == "all":
        return True
    return viewer is not None and in_circle(post.author, viewer)


def find_user(username):
    return User.query.filter(db.func.lower(User.username) == username.lower()).first()


def save_image(file, owner, size, square=False):
    """Сжимает картинку и сохраняет в базу. Возвращает Image или None, если файл не картинка."""
    try:
        picture = PILImage.open(file.stream)
        picture = ImageOps.exif_transpose(picture)
        picture = picture.convert("RGB")
    except (UnidentifiedImageError, OSError, PILImage.DecompressionBombError):
        return None

    if square:
        picture = ImageOps.fit(picture, (size, size), PILImage.LANCZOS)
    else:
        picture.thumbnail((size, size), PILImage.LANCZOS)

    # WebP весит в 2–3 раза меньше JPEG — экономим трафик пользователей
    buffer = io.BytesIO()
    picture.save(buffer, "WEBP", quality=80, method=4)

    image = Image(
        owner_id=owner.id, data=buffer.getvalue(), mime="image/webp",
        width=picture.width, height=picture.height,
    )
    db.session.add(image)
    db.session.flush()
    return image


def notify(user_id, kind, post_id=None, beacon_id=None, actor=None):
    actor = actor or g.user
    if user_id == actor.id or is_blocked_between(user_id, actor.id):
        return
    db.session.add(Notification(
        user_id=user_id, actor_id=actor.id, kind=kind, post_id=post_id, beacon_id=beacon_id,
    ))


def unnotify(user_id, kind, post_id=None):
    Notification.query.filter_by(
        user_id=user_id, actor_id=g.user.id, kind=kind, post_id=post_id
    ).delete()


def make_friends(a, b):
    """Взаимная подписка — так новичок, пришедший по приглашению, сразу не один."""
    if is_blocked_between(a.id, b.id):
        return
    for follower, followed in ((a, b), (b, a)):
        if follower.id != followed.id and not db.session.get(Follow, (follower.id, followed.id)):
            db.session.add(Follow(follower_id=follower.id, followed_id=followed.id))


def block_user(blocker, blocked):
    """Блокировка рвёт все связи: подписки, близкий круг, участие в маяках друг друга."""
    db.session.add(Block(blocker_id=blocker.id, blocked_id=blocked.id))
    for a, b in ((blocker, blocked), (blocked, blocker)):
        Follow.query.filter_by(follower_id=a.id, followed_id=b.id).delete()
        CircleMember.query.filter_by(owner_id=a.id, member_id=b.id).delete()
        their_beacons = db.session.query(Beacon.id).filter(Beacon.author_id == a.id)
        BeaconMember.query.filter(
            BeaconMember.user_id == b.id, BeaconMember.beacon_id.in_(their_beacons)
        ).delete(synchronize_session=False)
        Notification.query.filter_by(user_id=a.id, actor_id=b.id).delete()


def mutual_friend_ids(user):
    """id тех, с кем user подписан взаимно."""
    following = db.session.query(Follow.followed_id).filter(Follow.follower_id == user.id)
    return db.session.query(Follow.follower_id).filter(
        Follow.followed_id == user.id, Follow.follower_id.in_(following)
    )


# ---------- Маяки ----------

def purge_expired_beacons():
    for beacon in Beacon.query.filter(Beacon.expires_at <= now()).all():
        db.session.delete(beacon)
    db.session.commit()


def beacons_for(user):
    """Активные маяки, которые user видит в полосе «Сейчас»."""
    joined = db.session.query(BeaconMember.beacon_id).filter(BeaconMember.user_id == user.id)
    circles = db.session.query(CircleMember.owner_id).filter(CircleMember.member_id == user.id)
    return (
        Beacon.query.filter(
            Beacon.expires_at > now(),
            Beacon.author_id.not_in(blocked_ids(user)),
            or_(
                Beacon.author_id == user.id,
                Beacon.id.in_(joined),
                and_(Beacon.audience == "friends", Beacon.author_id.in_(mutual_friend_ids(user))),
                and_(Beacon.audience == "circle", Beacon.author_id.in_(circles)),
            ),
        )
        .order_by(Beacon.starts_at, Beacon.id)
        .all()
    )


def beacon_audience_ids(beacon):
    if beacon.audience == "circle":
        rows = db.session.query(CircleMember.member_id).filter(
            CircleMember.owner_id == beacon.author_id
        )
    else:
        rows = mutual_friend_ids(beacon.author)
    return [row[0] for row in rows.limit(MAX_BEACON_NOTIFY)]


def join_beacon(user, beacon):
    if beacon.author_id == user.id or beacon.has_member(user):
        return
    if is_blocked_between(user.id, beacon.author_id):
        return
    db.session.add(BeaconMember(beacon_id=beacon.id, user_id=user.id))
    notify(beacon.author_id, "beacon_join", beacon_id=beacon.id, actor=user)


# ---------- Вопрос дня ----------

def today():
    return (now() + DAY_OFFSET).date()


def question_for(day):
    return DAILY_QUESTIONS[day.toordinal() % len(DAILY_QUESTIONS)]


def answered_today(user):
    return Answer.query.filter_by(user_id=user.id, day=today()).first()


def answer_streak(user):
    """Сколько дней подряд user отвечает (серия не сгорает, пока не прошёл сегодняшний день)."""
    days = [
        row.day for row in
        Answer.query.filter_by(user_id=user.id).order_by(Answer.day.desc()).limit(400)
    ]
    expected = today()
    if days and days[0] != expected:
        expected -= timedelta(days=1)
    streak = 0
    for day in days:
        if day != expected:
            break
        streak += 1
        expected -= timedelta(days=1)
    return streak


def chat_timer(user, other):
    a, b = sorted((user.id, other.id))
    timer = db.session.get(ChatTimer, (a, b))
    return timer.seconds if timer else 0


def purge_expired_messages():
    Message.query.filter(Message.expires_at <= now()).delete()
    db.session.commit()


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


def unseen_notifications(user):
    return Notification.query.filter_by(user_id=user.id, is_read=False).count()


def parse_local_datetime(value, offset_minutes):
    """Переводит время из браузера пользователя (его часовой пояс) в UTC."""
    try:
        local = datetime.fromisoformat(value)
        offset = int(offset_minutes or 0)
    except ValueError:
        return None
    return local + timedelta(minutes=offset)


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
    # На хостинге приложение стоит за прокси — доверяем его заголовкам про https и IP
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

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
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("NOWA_HTTPS") == "1",
        PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30,
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    with app.app_context():
        db.create_all()
        upgrade_schema()
        # gunicorn --preload создаёт приложение до запуска процессов —
        # закрываем соединения, чтобы процессы не делили одно подключение к базе
        db.engine.dispose()

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

        if request.method == "POST":
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
            "unseen": unseen_notifications(g.user) if g.user else 0,
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

    @app.template_filter("iso")
    def iso(value):
        # Время в базе в UTC, браузер переведёт в местное
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")

    # ---------- PWA И СЛУЖЕБНОЕ ----------

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

    @app.route("/img/<int:image_id>")
    def image(image_id):
        picture = db.session.get(Image, image_id) or abort(404)
        # Картинка закрытого или отложенного поста доступна только тем, кто видит пост
        post = Post.query.filter_by(image_id=picture.id).first()
        if post and not can_see(g.user, post):
            abort(404)
        response = Response(picture.data, mimetype=picture.mime)
        cache = "private" if post and post.visibility == "circle" else "public"
        response.headers["Cache-Control"] = f"{cache}, max-age=31536000, immutable"
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
            db.session.flush()

            inviter = db.session.get(User, session.get("inviter_id") or 0)
            if inviter:
                user.invited_by_id = inviter.id
                make_friends(user, inviter)
                notify(inviter.id, "invite", actor=user)
            db.session.commit()

            flash(f"Добро пожаловать в NOWA, {username}!", "ok")
            return sign_in(user, url_for("feed", tab="all"))

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

            next_url = request.args.get("next", "")
            # Разрешаем только относительные ссылки, чтобы не было редиректа на чужой сайт
            if not next_url.startswith("/") or next_url.startswith("//"):
                next_url = url_for("feed")
            return sign_in(user, next_url)

        return render_template("login.html")

    def sign_in(user, next_url):
        """Входим в аккаунт и доделываем то, ради чего человек пришёл по ссылке."""
        pending_token = session.get("pending_beacon")
        session.clear()
        session.permanent = True
        session["user_id"] = user.id

        beacon = Beacon.query.filter_by(token=pending_token).first() if pending_token else None
        if beacon and beacon.expires_at > now():
            join_beacon(user, beacon)
            make_friends(user, beacon.author)
            db.session.commit()
            flash(f"Ты в деле! {beacon.author.username} уже знает.", "ok")
            return redirect(url_for("beacon_page", token=beacon.token))
        return redirect(next_url)

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return redirect(url_for("index"))

    # ---------- ЛЕНТА И ПОСТЫ ----------

    def after_cursor(query, before_id):
        """Пагинация: посты, которые в ленте идут после поста before_id."""
        anchor = db.session.get(Post, before_id) if before_id else None
        if anchor is None:
            return query
        return query.filter(
            or_(
                Post.published_at < anchor.published_at,
                and_(Post.published_at == anchor.published_at, Post.id < anchor.id),
            )
        )

    @app.route("/feed")
    @login_required
    def feed():
        tab = request.args.get("tab", "following")

        query = visible_posts_query(g.user)
        if tab == "following":
            followed = db.session.query(Follow.followed_id).filter(
                Follow.follower_id == g.user.id
            )
            query = query.filter(
                or_(Post.author_id.in_(followed), Post.author_id == g.user.id)
            )
        query = after_cursor(query, request.args.get("before", type=int))

        posts = newest_first(query).limit(FEED_PAGE_SIZE + 1).all()
        has_more = len(posts) > FEED_PAGE_SIZE
        posts = posts[:FEED_PAGE_SIZE]

        purge_expired_beacons()
        return render_template(
            "feed.html", posts=posts, tab=tab, has_more=has_more,
            liked=liked_ids(posts), beacons=beacons_for(g.user),
            question=question_for(today()), answered=answered_today(g.user),
            following_count=Follow.query.filter_by(follower_id=g.user.id).count(),
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
        back = request.referrer or url_for("feed")
        text_value = request.form.get("text", "").strip()
        visibility = "circle" if request.form.get("visibility") == "circle" else "all"
        photo = request.files.get("image")

        if len(text_value) > MAX_POST_LENGTH:
            flash(f"Пост слишком длинный (максимум {MAX_POST_LENGTH} символов).", "error")
            return redirect(back)

        published_at = now()
        if request.form.get("publish_at"):
            published_at = parse_local_datetime(
                request.form["publish_at"], request.form.get("tz_offset")
            )
            if published_at is None or not (now() < published_at < now() + timedelta(days=365)):
                flash("Время публикации должно быть в будущем, но не дальше чем через год.", "error")
                return redirect(back)

        image = None
        if photo and photo.filename:
            image = save_image(photo, g.user, POST_IMAGE_SIZE)
            if image is None:
                flash("Не получилось открыть фото. Подойдут JPG, PNG, WebP или GIF.", "error")
                return redirect(back)

        if not text_value and image is None:
            flash("Напиши что-нибудь или прикрепи фото.", "error")
            return redirect(back)

        db.session.add(Post(
            author_id=g.user.id, text=text_value, image=image,
            visibility=visibility, published_at=published_at,
        ))
        db.session.commit()
        if published_at > now():
            flash("Пост запланирован. До публикации его видишь только ты.", "ok")
        else:
            flash("Пост опубликован!", "ok")
        return redirect(back)

    def get_visible_post(post_id):
        post = db.session.get(Post, post_id)
        if post is None or not can_see(g.user, post):
            abort(404)
        return post

    @app.route("/post/<int:post_id>")
    def view_post(post_id):
        post = get_visible_post(post_id)
        return render_template(
            "post.html", post=post, liked=liked_ids([post]), reasons=REPORT_REASONS,
        )

    @app.route("/post/<int:post_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_post(post_id):
        post = get_visible_post(post_id)
        if post.author_id != g.user.id:
            abort(403)

        if request.method == "POST":
            text_value = request.form.get("text", "").strip()
            if len(text_value) > MAX_POST_LENGTH or (not text_value and post.image is None):
                flash("Текст поста пустой или слишком длинный.", "error")
                return render_template("edit_post.html", post=post)
            post.text = text_value
            post.visibility = "circle" if request.form.get("visibility") == "circle" else "all"
            if request.form.get("publish_now") and post.is_scheduled:
                post.published_at = now()
            else:
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
        image = post.image
        db.session.delete(post)
        if image:
            db.session.delete(image)
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
            unnotify(post.author_id, "like", post.id)
        else:
            db.session.add(Like(user_id=g.user.id, post_id=post.id))
            notify(post.author_id, "like", post.id)
        db.session.commit()

        if request.headers.get("Accept") == "application/json":
            return jsonify(liked=like is None, count=Like.query.filter_by(post_id=post.id).count())
        return redirect(request.referrer or url_for("view_post", post_id=post.id))

    @app.route("/post/<int:post_id>/comment", methods=["POST"])
    @login_required
    def comment_post(post_id):
        post = get_visible_post(post_id)
        text_value = request.form.get("text", "").strip()
        if not text_value or len(text_value) > MAX_COMMENT_LENGTH:
            flash("Комментарий пустой или слишком длинный.", "error")
        else:
            db.session.add(Comment(post_id=post.id, author_id=g.user.id, text=text_value))
            notify(post.author_id, "comment", post.id)
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
        i_blocked = g.user is not None and db.session.get(Block, (g.user.id, user.id)) is not None
        if g.user is not None and not i_blocked and is_blocked_between(g.user.id, user.id):
            abort(404)
        posts = [] if i_blocked else newest_first(
            visible_posts_query(g.user).filter(Post.author_id == user.id)
        ).all()
        stats = {
            "posts": Post.query.filter(
                Post.author_id == user.id, Post.published_at <= now()
            ).count(),
            "followers": Follow.query.filter_by(followed_id=user.id).count(),
            "following": Follow.query.filter_by(follower_id=user.id).count(),
        }
        return render_template(
            "profile.html", user=user, posts=posts, stats=stats, liked=liked_ids(posts),
            i_blocked=i_blocked, reasons=REPORT_REASONS,
        )

    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        if request.method == "POST":
            g.user.bio = request.form.get("bio", "").strip()[:300]

            photo = request.files.get("avatar")
            if photo and photo.filename:
                image = save_image(photo, g.user, AVATAR_SIZE, square=True)
                if image is None:
                    flash("Не получилось открыть фото. Подойдут JPG, PNG, WebP или GIF.", "error")
                    return redirect(url_for("settings"))
                old = db.session.get(Image, g.user.avatar_id) if g.user.avatar_id else None
                g.user.avatar_id = image.id
                if old:
                    db.session.delete(old)
            elif request.form.get("remove_avatar") and g.user.avatar_id:
                old = db.session.get(Image, g.user.avatar_id)
                g.user.avatar_id = None
                db.session.delete(old)

            db.session.commit()
            flash("Профиль сохранён.", "ok")
            return redirect(url_for("profile", username=g.user.username))
        circle = (
            User.query.join(CircleMember, CircleMember.member_id == User.id)
            .filter(CircleMember.owner_id == g.user.id)
            .order_by(User.username)
            .all()
        )
        invited = User.query.filter_by(invited_by_id=g.user.id).count()
        return render_template("settings.html", circle=circle, invited=invited)

    @app.route("/u/<username>/follow", methods=["POST"])
    @login_required
    def follow(username):
        user = find_user(username) or abort(404)
        if is_blocked_between(g.user.id, user.id):
            abort(403)
        if user.id != g.user.id:
            existing = db.session.get(Follow, (g.user.id, user.id))
            if existing:
                db.session.delete(existing)
                unnotify(user.id, "follow")
            else:
                db.session.add(Follow(follower_id=g.user.id, followed_id=user.id))
                notify(user.id, "follow")
            db.session.commit()
        return redirect(request.referrer or url_for("profile", username=user.username))

    @app.route("/u/<username>/circle", methods=["POST"])
    @login_required
    def toggle_circle(username):
        user = find_user(username) or abort(404)
        if is_blocked_between(g.user.id, user.id):
            abort(403)
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

    # ---------- БЕЗОПАСНОСТЬ ----------

    @app.route("/u/<username>/block", methods=["POST"])
    @login_required
    def toggle_block(username):
        user = find_user(username) or abort(404)
        if user.id == g.user.id:
            abort(400, "Себя заблокировать нельзя.")
        existing = db.session.get(Block, (g.user.id, user.id))
        if existing:
            db.session.delete(existing)
            flash(f"{user.username} разблокирован(а).", "ok")
        else:
            block_user(g.user, user)
            flash(f"{user.username} заблокирован(а): вы больше не видите друг друга и не можете писать.", "ok")
        db.session.commit()
        return redirect(url_for("profile", username=user.username))

    @app.route("/report", methods=["POST"])
    @login_required
    def report():
        reason = request.form.get("reason", "other")
        if reason not in REPORT_REASONS:
            reason = "other"
        post_obj = beacon = None
        if request.form.get("post_id"):
            post_obj = get_visible_post(request.form.get("post_id", type=int))
            target = post_obj.author
        elif request.form.get("beacon_token"):
            beacon = get_beacon(request.form["beacon_token"])
            target = beacon.author
        else:
            target = find_user(request.form.get("username", "")) or abort(404)
        if target.id == g.user.id:
            abort(400, "На себя пожаловаться нельзя.")

        db.session.add(Report(
            reporter_id=g.user.id, target_user_id=target.id, reason=reason,
            post_id=post_obj.id if post_obj else None, beacon_id=beacon.id if beacon else None,
            comment=request.form.get("comment", "").strip()[:500],
        ))
        if request.form.get("also_block") and not db.session.get(Block, (g.user.id, target.id)):
            block_user(g.user, target)
        db.session.commit()
        flash("Спасибо! Жалоба отправлена модераторам.", "ok")
        if request.form.get("also_block"):
            return redirect(url_for("feed"))
        return redirect(request.referrer or url_for("feed"))

    def is_admin(user):
        admins = {
            name.strip().lower()
            for name in os.environ.get("NOWA_ADMINS", "").split(",") if name.strip()
        }
        return user is not None and user.username.lower() in admins

    @app.route("/admin/reports", methods=["GET", "POST"])
    @login_required
    def admin_reports():
        if not is_admin(g.user):
            abort(404)
        if request.method == "POST":
            item = db.session.get(Report, request.form.get("report_id", type=int)) or abort(404)
            action = request.form.get("action")
            if action == "delete_post" and item.post:
                db.session.delete(item.post)
            elif action == "delete_beacon" and item.beacon:
                db.session.delete(item.beacon)
            item.resolved = True
            db.session.commit()
            return redirect(url_for("admin_reports"))
        items = Report.query.filter_by(resolved=False).order_by(Report.id).limit(200).all()
        return render_template("admin_reports.html", items=items, reasons=REPORT_REASONS)

    # ---------- УВЕДОМЛЕНИЯ ----------

    @app.route("/notifications")
    @login_required
    def notifications():
        items = (
            Notification.query.filter_by(user_id=g.user.id)
            .order_by(Notification.id.desc()).limit(100).all()
        )
        fresh = {item.id for item in items if not item.is_read}
        Notification.query.filter_by(user_id=g.user.id, is_read=False).update({"is_read": True})
        db.session.commit()
        return render_template("notifications.html", items=items, fresh=fresh)

    @app.route("/api/counters")
    @login_required
    def counters():
        return jsonify(messages=unread_count(g.user), notifications=unseen_notifications(g.user))

    # ---------- ПОИСК ----------

    @app.route("/search")
    @login_required
    def search():
        q = request.args.get("q", "").strip()
        users, posts = [], []
        if q:
            pattern = f"%{q}%"
            users = (
                User.query.filter(
                    User.username.ilike(pattern), User.id.not_in(blocked_ids(g.user))
                )
                .order_by(User.username).limit(20).all()
            )
            posts = newest_first(
                visible_posts_query(g.user).filter(Post.text.ilike(pattern))
            ).limit(30).all()
        return render_template(
            "search.html", q=q, users=users, posts=posts, liked=liked_ids(posts)
        )

    # ---------- МАЯКИ ----------

    def get_beacon(token):
        beacon = Beacon.query.filter_by(token=token).first()
        if beacon is None or beacon.expires_at <= now():
            abort(404, "Этот маяк уже погас.")
        return beacon

    def beacon_message_json(message):
        return {
            "id": message.id,
            "mine": message.user_id == g.user.id,
            "author": message.user.username,
            "text": message.text,
            "time": iso(message.created_at),
        }

    @app.route("/beacons/new", methods=["GET", "POST"])
    @login_required
    def new_beacon():
        if request.method == "POST":
            activity = request.form.get("activity", "other")
            if activity not in BEACON_ACTIVITIES:
                activity = "other"
            title = request.form.get("title", "").strip()[:80]
            place = request.form.get("place", "").strip()[:120]
            audience = "circle" if request.form.get("audience") == "circle" else "friends"
            hours = request.form.get("hours", 3, type=int)
            if hours not in BEACON_DURATIONS:
                hours = 3

            starts_at = now()
            when = request.form.get("when", "now")
            if when in ("30", "60", "120"):
                starts_at = now() + timedelta(minutes=int(when))
            elif when == "at" and request.form.get("at"):
                # Время из поля <input type="time"> — по часам пользователя, сегодня или завтра
                try:
                    hour, minute = map(int, request.form["at"].split(":"))
                    offset = timedelta(minutes=request.form.get("tz_offset", 0, type=int))
                    local_now = now() - offset
                    local_start = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if local_start < local_now - timedelta(minutes=5):
                        local_start += timedelta(days=1)
                    starts_at = local_start + offset
                except ValueError:
                    flash("Не поняли время. Выбери ещё раз.", "error")
                    return redirect(url_for("new_beacon"))

            beacon = Beacon(
                author_id=g.user.id, activity=activity, title=title, place=place,
                audience=audience, starts_at=starts_at,
                expires_at=max(starts_at, now()) + timedelta(hours=hours),
            )
            db.session.add(beacon)
            db.session.flush()
            for user_id in beacon_audience_ids(beacon):
                notify(user_id, "beacon", beacon_id=beacon.id)
            db.session.commit()
            flash("Маяк зажжён! Друзья его видят. Можешь отправить ссылку кому угодно.", "ok")
            return redirect(url_for("beacon_page", token=beacon.token))

        return render_template(
            "new_beacon.html", activities=BEACON_ACTIVITIES, durations=BEACON_DURATIONS,
        )

    @app.route("/b/<token>")
    def beacon_page(token):
        purge_expired_beacons()
        beacon = get_beacon(token)
        if g.user is not None and is_blocked_between(g.user.id, beacon.author_id):
            abort(404, "Этот маяк уже погас.")
        # Ссылка — это приглашение: открыть маяк может любой, у кого она есть.
        # Но место встречи и чат видят только участники.
        inside = g.user is not None and (
            beacon.author_id == g.user.id or beacon.has_member(g.user)
        )
        return render_template(
            "beacon.html", beacon=beacon, inside=inside, reasons=REPORT_REASONS,
        )

    @app.route("/b/<token>/join", methods=["POST"])
    def join_beacon_route(token):
        beacon = get_beacon(token)
        if g.user is None:
            session["pending_beacon"] = beacon.token
            flash(f"Зарегистрируйся за 20 секунд — и сразу попадёшь в маяк {beacon.author.username}.", "ok")
            return redirect(url_for("register"))

        if is_blocked_between(g.user.id, beacon.author_id):
            abort(404, "Этот маяк уже погас.")
        member = db.session.get(BeaconMember, (beacon.id, g.user.id))
        if member:
            db.session.delete(member)
            Notification.query.filter_by(
                user_id=beacon.author_id, actor_id=g.user.id, kind="beacon_join", beacon_id=beacon.id,
            ).delete()
            flash("Ты больше не идёшь.", "ok")
        elif beacon.author_id != g.user.id:
            join_beacon(g.user, beacon)
            flash(f"Ты в деле! {beacon.author.username} уже знает.", "ok")
        db.session.commit()
        return redirect(request.referrer or url_for("beacon_page", token=beacon.token))

    @app.route("/b/<token>/cancel", methods=["POST"])
    @login_required
    def cancel_beacon(token):
        beacon = get_beacon(token)
        if beacon.author_id != g.user.id:
            abort(403)
        db.session.delete(beacon)
        db.session.commit()
        flash("Маяк погашен.", "ok")
        return redirect(url_for("feed"))

    @app.route("/b/<token>/chat", methods=["POST"])
    @login_required
    def beacon_chat(token):
        beacon = get_beacon(token)
        if not (beacon.author_id == g.user.id or beacon.has_member(g.user)):
            abort(403)
        text_value = request.form.get("text", "").strip()
        wants_json = request.headers.get("Accept") == "application/json"
        if not text_value or len(text_value) > MAX_MESSAGE_LENGTH:
            if wants_json:
                return jsonify(error="Пустое или слишком длинное сообщение"), 400
            return redirect(url_for("beacon_page", token=beacon.token))
        message = BeaconMessage(beacon_id=beacon.id, user_id=g.user.id, text=text_value)
        db.session.add(message)
        db.session.commit()
        if wants_json:
            return jsonify(beacon_message_json(message))
        return redirect(url_for("beacon_page", token=beacon.token) + "#chat")

    @app.route("/api/b/<token>/chat")
    @login_required
    def beacon_chat_updates(token):
        beacon = get_beacon(token)
        if not (beacon.author_id == g.user.id or beacon.has_member(g.user)):
            abort(403)
        after = request.args.get("after", 0, type=int)
        messages = [m for m in beacon.messages if m.id > after]
        return jsonify([beacon_message_json(m) for m in messages])

    # ---------- ПРИГЛАШЕНИЯ ----------

    @app.route("/i/<code>")
    def invite(code):
        inviter = User.query.filter_by(invite_code=code).first() or abort(404)
        if g.user:
            return redirect(url_for("profile", username=inviter.username))
        session["inviter_id"] = inviter.id
        return render_template("invite.html", inviter=inviter)

    # ---------- ВОПРОС ДНЯ ----------

    @app.route("/question", methods=["GET", "POST"])
    @login_required
    def daily_question():
        day = today()
        mine = answered_today(g.user)

        if request.method == "POST" and mine is None:
            text_value = request.form.get("text", "").strip()
            if not text_value or len(text_value) > 500:
                flash("Ответ пустой или длиннее 500 символов.", "error")
            else:
                db.session.add(Answer(user_id=g.user.id, day=day, text=text_value))
                db.session.commit()
            return redirect(url_for("daily_question"))

        answers = []
        if mine:
            following = db.session.query(Follow.followed_id).filter(
                Follow.follower_id == g.user.id
            )
            answers = (
                Answer.query.filter(
                    Answer.day == day, Answer.user_id.in_(following),
                    Answer.user_id.not_in(blocked_ids(g.user)),
                )
                .order_by(Answer.created_at.desc()).all()
            )
        return render_template(
            "question.html", question=question_for(day), mine=mine, answers=answers,
            total=Answer.query.filter_by(day=day).count(), streak=answer_streak(g.user),
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
            "time": iso(message.created_at),
            "expires": iso(message.expires_at) if message.expires_at else None,
        }

    @app.route("/messages")
    @login_required
    def messages():
        purge_expired_messages()
        return render_template("messages.html", dialogs=dialogs_for(g.user))

    @app.route("/messages/<username>", methods=["GET", "POST"])
    @login_required
    def chat(username):
        other = find_user(username) or abort(404)
        if other.id == g.user.id:
            return redirect(url_for("messages"))

        blocked = is_blocked_between(g.user.id, other.id)
        if request.method == "POST":
            if blocked:
                abort(403)
            text_value = request.form.get("text", "").strip()
            if text_value and len(text_value) <= MAX_MESSAGE_LENGTH:
                timer = chat_timer(g.user, other)
                message = Message(
                    sender_id=g.user.id, receiver_id=other.id, text=text_value,
                    expires_at=now() + timedelta(seconds=timer) if timer else None,
                )
                db.session.add(message)
                db.session.commit()
                if request.headers.get("Accept") == "application/json":
                    return jsonify(message_json(message))
            elif request.headers.get("Accept") == "application/json":
                return jsonify(error="Пустое или слишком длинное сообщение"), 400
            return redirect(url_for("chat", username=other.username))

        purge_expired_messages()
        history = chat_query(g.user, other).order_by(Message.id).all()
        mark_read(g.user, other)
        return render_template(
            "chat.html", other=other, history=history, blocked=blocked,
            timer=chat_timer(g.user, other), timers=CHAT_TIMERS,
        )

    @app.route("/messages/<username>/timer", methods=["POST"])
    @login_required
    def set_chat_timer(username):
        other = find_user(username) or abort(404)
        seconds = request.form.get("seconds", 0, type=int)
        if seconds not in CHAT_TIMERS or other.id == g.user.id:
            abort(400, "Такого таймера нет.")
        if is_blocked_between(g.user.id, other.id):
            abort(403)

        a, b = sorted((g.user.id, other.id))
        timer = db.session.get(ChatTimer, (a, b))
        if timer is None:
            timer = ChatTimer(user_a_id=a, user_b_id=b)
            db.session.add(timer)
        timer.seconds = seconds

        # Сообщение в чате, чтобы собеседник тоже увидел, что таймер поменялся
        label = "выключены" if seconds == 0 else f"исчезают через {CHAT_TIMERS[seconds]}"
        db.session.add(Message(
            sender_id=g.user.id, receiver_id=other.id,
            text=f"🕒 Сообщения в этом чате теперь {label}",
            expires_at=now() + timedelta(seconds=seconds) if seconds else None,
        ))
        db.session.commit()
        return redirect(url_for("chat", username=other.username))

    @app.route("/api/messages/<username>")
    @login_required
    def new_messages(username):
        other = find_user(username) or abort(404)
        after = request.args.get("after", 0, type=int)
        purge_expired_messages()
        history = chat_query(g.user, other).filter(Message.id > after).order_by(Message.id).all()
        if history:
            mark_read(g.user, other)
        return jsonify([message_json(m) for m in history])

    @app.errorhandler(404)
    def not_found(error):
        # Свой текст ошибки (например, «маяк погас») показываем, стандартный английский — нет
        text_value = error.description
        if not text_value or text_value == NotFound.description:
            text_value = "Такой страницы нет."
        return render_template("error.html", code=404, text=text_value), 404

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("error.html", code=403, text="Сюда нельзя."), 403

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("error.html", code=400, text=error.description), 400

    @app.errorhandler(413)
    def too_large(error):
        flash("Файл слишком большой — максимум 10 МБ.", "error")
        return redirect(request.referrer or url_for("feed"))


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
