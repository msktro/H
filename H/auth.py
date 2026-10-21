"""User accounts backed by a small local SQLite database."""

import sqlite3
from functools import wraps
from pathlib import Path

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint("auth", __name__)


def database_path():
    return Path(current_app.instance_path) / "travel_planner.sqlite3"


def connect_database():
    connection = sqlite3.connect(database_path())
    connection.row_factory = sqlite3.Row
    return connection


def init_db(instance_path):
    Path(instance_path).mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(Path(instance_path) / "travel_planner.sqlite3") as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped_view


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    values = {"display_name": "", "email": ""}
    error = ""
    if request.method == "POST":
        values = {
            "display_name": request.form.get("display_name", "").strip(),
            "email": request.form.get("email", "").strip().lower(),
        }
        password = request.form.get("password", "")
        if not values["display_name"] or len(values["display_name"]) > 80:
            error = "表示名を1〜80文字で入力してください。"
        elif "@" not in values["email"] or len(values["email"]) > 254:
            error = "有効なメールアドレスを入力してください。"
        elif len(password) < 8:
            error = "パスワードは8文字以上で入力してください。"
        else:
            try:
                with connect_database() as connection:
                    cursor = connection.execute(
                        "INSERT INTO users (display_name, email, password_hash) VALUES (?, ?, ?)",
                        (values["display_name"], values["email"], generate_password_hash(password)),
                    )
                    user_id = cursor.lastrowid
                session.clear()
                session.permanent = True
                session["user_id"] = user_id
                session["user_name"] = values["display_name"]
                return redirect(url_for("index"))
            except sqlite3.IntegrityError:
                error = "このメールアドレスはすでに登録されています。ログインしてください。"
    return render_template("auth_register.html", values=values, error=error)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    email = ""
    error = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with connect_database() as connection:
            user = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            error = "メールアドレスまたはパスワードが違います。"
        else:
            session.clear()
            session.permanent = True
            session["user_id"] = user["id"]
            session["user_name"] = user["display_name"]
            return redirect(url_for("index"))
    return render_template("auth_login.html", email=email, error=error)


@auth_bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
