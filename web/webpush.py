"""Отправка Web Push уведомлений без сторонних библиотек (кроме cryptography).

Как это работает:
1. Браузер подписывается на уведомления и отдаёт нам endpoint (адрес у Google/Mozilla/Apple)
   и два ключа: p256dh (публичный ключ браузера) и auth (общий секрет).
2. Мы шифруем текст уведомления этими ключами (RFC 8291, aes128gcm),
   подписываем запрос своим ключом VAPID (RFC 8292) и отправляем на endpoint.
3. Сервис доставляет зашифрованное уведомление на телефон, браузер расшифровывает его.
"""

import base64
import hashlib
import hmac
import json
import os
import struct
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

RECORD_SIZE = 4096

# Сервисы доставки пушей браузеров. Отправляем только туда, чтобы никто не мог
# подсунуть адрес внутреннего сервера и заставить NOWA туда стучаться.
PUSH_HOSTS = (
    "fcm.googleapis.com",            # Chrome, Яндекс Браузер, Edge на Android
    ".push.services.mozilla.com",    # Firefox
    ".notify.windows.com",           # Edge на Windows
    ".push.apple.com",               # Safari и iPhone
)


def is_push_endpoint(endpoint):
    parsed = urlparse(endpoint)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(
        host == allowed.lstrip(".") or (allowed.startswith(".") and host.endswith(allowed))
        for allowed in PUSH_HOSTS
    )


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64url_decode(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hkdf(salt, ikm, info, length):
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    return hmac.new(prk, info + b"\x01", hashlib.sha256).digest()[:length]


def public_bytes(private_key):
    return private_key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )


# ---------------- Ключи VAPID ----------------

def generate_vapid_key():
    """Новый ключ сервера. Хранить в переменной VAPID_PRIVATE_KEY."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    number = private_key.private_numbers().private_value
    return b64url(number.to_bytes(32, "big"))


def load_vapid_key(text):
    number = int.from_bytes(b64url_decode(text), "big")
    return ec.derive_private_key(number, ec.SECP256R1())


def vapid_public_key(private_key):
    """Этот ключ браузер передаёт в pushManager.subscribe(applicationServerKey)."""
    return b64url(public_bytes(private_key))


def vapid_headers(endpoint, private_key, subject):
    origin = urlparse(endpoint)
    claims = {
        "aud": f"{origin.scheme}://{origin.netloc}",
        "exp": int(time.time()) + 12 * 60 * 60,
        "sub": subject,
    }
    header = b64url(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    body = b64url(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{header}.{body}".encode()
    r, s = decode_dss_signature(private_key.sign(signing_input, ec.ECDSA(hashes.SHA256())))
    signature = b64url(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    return {
        "Authorization": f"vapid t={header}.{body}.{signature}, k={vapid_public_key(private_key)}",
    }


# ---------------- Шифрование (RFC 8291) ----------------

def encrypt(payload, p256dh, auth, salt=None, server_key=None):
    """Шифрует payload для браузера с ключами p256dh и auth (обе строки base64url)."""
    ua_public = b64url_decode(p256dh)
    auth_secret = b64url_decode(auth)
    salt = salt or os.urandom(16)
    server_key = server_key or ec.generate_private_key(ec.SECP256R1())
    as_public = public_bytes(server_key)

    ua_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)
    shared = server_key.exchange(ec.ECDH(), ua_key)

    ikm = hkdf(auth_secret, shared, b"WebPush: info\x00" + ua_public + as_public, 32)
    cek = hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)

    # \x02 — признак последней записи (у нас она одна)
    ciphertext = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    header = salt + struct.pack("!IB", RECORD_SIZE, len(as_public)) + as_public
    return header + ciphertext


def decrypt(body, ua_private_key, auth):
    """Обратная операция — как это делает браузер. Нужна для тестов."""
    salt, (record_size, key_length) = body[:16], struct.unpack("!IB", body[16:21])
    as_public = body[21:21 + key_length]
    ciphertext = body[21 + key_length:]

    ua_public = public_bytes(ua_private_key)
    as_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public)
    shared = ua_private_key.exchange(ec.ECDH(), as_key)

    ikm = hkdf(b64url_decode(auth), shared, b"WebPush: info\x00" + ua_public + as_public, 32)
    cek = hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    plain = AESGCM(cek).decrypt(nonce, ciphertext, None)
    return plain.rstrip(b"\x00")[:-1]


# ---------------- Отправка ----------------

def send(subscription, message, private_key, subject, ttl=6 * 60 * 60):
    """Отправляет одно уведомление. Возвращает HTTP-код ответа сервиса.
    404 и 410 значат, что подписка больше не действует и её надо удалить."""
    body = encrypt(
        json.dumps(message, ensure_ascii=False).encode(),
        subscription["p256dh"], subscription["auth"],
    )
    headers = {
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "TTL": str(ttl),
        "Urgency": "high",
        **vapid_headers(subscription["endpoint"], private_key, subject),
    }
    request = urllib.request.Request(subscription["endpoint"], data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except OSError:
        return 0


if __name__ == "__main__":
    print("VAPID_PRIVATE_KEY=" + generate_vapid_key())
