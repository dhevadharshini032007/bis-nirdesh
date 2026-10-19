import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import jwt
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
DB_PATH = PROJECT_ROOT / "data" / "users.db"
load_dotenv(ENV_PATH, override=True, encoding="utf-8-sig")


def _jwt_secret():
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError(f"JWT_SECRET is missing or empty; checked {ENV_PATH}")
    return secret


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_db():
    with _connect() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                user_type TEXT NOT NULL CHECK (user_type IN ('msme', 'manufacturer', 'consumer', 'student')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )


def _public_user(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "user_type": row["user_type"],
        "created_at": row["created_at"],
    }


def create_user(name, email, password, user_type):
    normalized_email = email.strip().lower()
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    try:
        with _connect() as connection:
            cursor = connection.execute(
                "INSERT INTO users (name, email, password_hash, user_type) VALUES (?, ?, ?, ?)",
                (name.strip(), normalized_email, password_hash, user_type),
            )
            row = connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError as error:
        if "email" in str(error).lower() or "unique" in str(error).lower():
            raise ValueError("An account with this email already exists.") from None
        raise
    user = _public_user(row)
    return user, create_token(user)


def authenticate_user(email, password):
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
    try:
        password_matches = row is not None and bcrypt.checkpw(
            password.encode("utf-8"),
            row["password_hash"].encode("utf-8"),
        )
    except ValueError:
        password_matches = False
    if not password_matches:
        return None
    user = _public_user(row)
    return user, create_token(user)


def create_token(user):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user["id"]),
            "user_type": user["user_type"],
            "iat": now,
            "exp": now + timedelta(days=7),
        },
        _jwt_secret(),
        algorithm="HS256",
    )


def user_from_token(token):
    payload = jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    user_id = payload.get("sub")
    if not user_id:
        raise jwt.InvalidTokenError("Token subject is missing")
    with _connect() as connection:
        row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise jwt.InvalidTokenError("User no longer exists")
    return _public_user(row)
