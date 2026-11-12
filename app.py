"""Tabidea Webアプリケーション。



アプリケーションファクトリ、拡張機能の初期化、データベースの起動時マイグレーション、

および各機能別Blueprint（routes/）の登録を行います。

"""



import os

from pathlib import Path

import click
from werkzeug.security import generate_password_hash



from dotenv import load_dotenv



load_dotenv()



from flask import Flask, current_app, flash, redirect, request, session, url_for

from flask_login import LoginManager, current_user

from flask_wtf.csrf import CSRFProtect

from markupsafe import Markup, escape

from sqlalchemy import func, inspect, text



from constants import APP_NOTICES

from extensions import db

from helpers import pending_group_rejoin_counts, unread_group_message_counts, unread_journey_comment_notifications

from models import AccountWarning, AppNoticeRead, GroupMessage, OperatorNotice, OperatorNoticeRead, TripGroup, TripGroupRejoinRequest, User

from routes import register_blueprints



login_manager = LoginManager()

csrf = CSRFProtect()





def create_app():

    """Tabideaアプリケーションを構築し、各機能を初期化・登録します。"""

    app = Flask(__name__, instance_relative_config=True)

    app.config.update(

        SECRET_KEY=os.getenv("SECRET_KEY", "replace-this-secret-before-sharing"),

        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///tabidea.db"),

        SQLALCHEMY_TRACK_MODIFICATIONS=False,

        WTF_CSRF_TIME_LIMIT=None,

        MAX_CONTENT_LENGTH=27 * 1024 * 1024,

        GEOAPIFY_API_KEY=os.getenv("GEOAPIFY_API_KEY", "").strip(),

        PASSWORD_RESET_DEV_MODE=os.getenv("PASSWORD_RESET_DEV_MODE", os.getenv("FLASK_DEBUG", "0")).strip().lower() in ("1", "true", "yes"),

        MAIL_SERVER=os.getenv("MAIL_SERVER", "").strip(),

        MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),

        MAIL_USERNAME=os.getenv("MAIL_USERNAME", "").strip(),

        MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", ""),

        MAIL_DEFAULT_SENDER=os.getenv("MAIL_DEFAULT_SENDER", "").strip(),

        MAIL_USE_TLS=os.getenv("MAIL_USE_TLS", "1").strip().lower() in ("1", "true", "yes"),

        MAIL_USE_SSL=os.getenv("MAIL_USE_SSL", "0").strip().lower() in ("1", "true", "yes"),

        CONTACT_EMAIL=os.getenv("CONTACT_EMAIL", "").strip(),

        PUBLIC_BASE_URL=os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/"),

    )

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    login_manager.init_app(app)

    login_manager.login_view = "login_page"

    login_manager.login_message = "ログインしてください。"



    @login_manager.unauthorized_handler

    def unauthorized():

        login_msg = login_manager.login_message or "ログインしてください。"

        flashes = session.get("_flashes", [])

        if not any(msg == login_msg for _, msg in flashes):

            flash(login_msg, category=login_manager.login_message_category)

        return redirect(url_for("auth", mode="login", next=request.url))



    csrf.init_app(app)



    @app.after_request

    def secure_password_reset_response(response):

        # URLに再設定トークンが含まれる画面は、キャッシュと参照元への漏えいを防ぎます。

        if request.endpoint in ("password_reset", "auth.password_reset"):

            response.headers["Cache-Control"] = "no-store"

            response.headers["Referrer-Policy"] = "no-referrer"

        return response



    @app.template_filter("avatar_html")

    def avatar_html(user, css_class="avatar"):

        if not user:

            return Markup(escape("👤"))

        if user.avatar_image:

            image_url = url_for("user_avatar", user_id=user.id, v=user.updated_at.timestamp() if user.updated_at else 0)

            return Markup('<img class="%s avatar-image" src="%s" alt="" loading="lazy">') % (escape(css_class), escape(image_url))

        return Markup('<span class="%s">%s</span>') % (escape(css_class), escape(user.avatar or "👤"))



    @app.template_filter("group_icon_html")

    def group_icon_html(group, css_class="group-card-icon"):

        if not group:

            return Markup(escape("🧳"))

        if group.icon_image:

            image_url = url_for("group_icon_image", group_id=group.id, v=group.icon_image)

            return Markup('<img class="%s group-icon-image" src="%s" alt="" loading="lazy">') % (escape(css_class), escape(image_url))

        return Markup('<span class="%s">%s</span>') % (escape(css_class), escape(group.icon or "🧳"))



    @login_manager.user_loader

    def load_user(user_id):

        user = db.session.get(User, int(user_id))
        return user if user and not user.is_suspended else None



    with app.app_context():

        db.create_all()

        operator_notice_columns = {column["name"] for column in inspect(db.engine).get_columns("operator_notices")}
        if "is_active" not in operator_notice_columns:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE operator_notices ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE"))
        plan_columns = {column["name"] for column in inspect(db.engine).get_columns("travel_plans")}

        with db.engine.begin() as connection:

            if "start_date" not in plan_columns:

                connection.execute(text("ALTER TABLE travel_plans ADD COLUMN start_date DATE"))

            if "end_date" not in plan_columns:

                connection.execute(text("ALTER TABLE travel_plans ADD COLUMN end_date DATE"))

        user_columns = {column["name"] for column in inspect(db.engine).get_columns("user_auth")}

        if "avatar" not in user_columns:

            with db.engine.begin() as connection:

                connection.execute(text("ALTER TABLE user_auth ADD COLUMN avatar VARCHAR(16) NOT NULL DEFAULT '👤'"))

        if "avatar_image" not in user_columns:

            with db.engine.begin() as connection:

                connection.execute(text("ALTER TABLE user_auth ADD COLUMN avatar_image VARCHAR(255)"))

        if "is_suspended" not in user_columns:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE user_auth ADD COLUMN is_suspended BOOLEAN NOT NULL DEFAULT FALSE"))
        if "suspension_reason" not in user_columns:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE user_auth ADD COLUMN suspension_reason TEXT"))
        if "suspended_at" not in user_columns:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE user_auth ADD COLUMN suspended_at DATETIME"))
        if "suspended_by_id" not in user_columns:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE user_auth ADD COLUMN suspended_by_id INTEGER"))

        group_columns = {column["name"] for column in inspect(db.engine).get_columns("trip_groups")}

        if "icon" not in group_columns:

            with db.engine.begin() as connection:

                connection.execute(text("ALTER TABLE trip_groups ADD COLUMN icon VARCHAR(16) NOT NULL DEFAULT '🧳'"))

        if "icon_image" not in group_columns:

            with db.engine.begin() as connection:

                connection.execute(text("ALTER TABLE trip_groups ADD COLUMN icon_image VARCHAR(255)"))

        listing_columns = {column["name"] for column in inspect(db.engine).get_columns("business_listings")}

        listing_migrations = {

            "representative_name": "VARCHAR(100) NOT NULL DEFAULT ''",

            "phone": "VARCHAR(20) NOT NULL DEFAULT ''",

            "phone_verified": "BOOLEAN NOT NULL DEFAULT 0",

            "phone_verification_hash": "VARCHAR(256) NOT NULL DEFAULT ''",

            "phone_verification_expires_at": "DATETIME",

            "phone_verification_sent_at": "DATETIME",

            "phone_verification_attempts": "INTEGER NOT NULL DEFAULT 0",

            "access": "TEXT NOT NULL DEFAULT ''",

            "opening_hours": "VARCHAR(300) NOT NULL DEFAULT ''",

        }

        with db.engine.begin() as connection:

            for column_name, column_type in listing_migrations.items():

                if column_name not in listing_columns:

                    connection.execute(text(f"ALTER TABLE business_listings ADD COLUMN {column_name} {column_type}"))

        story_columns = {column["name"] for column in inspect(db.engine).get_columns("travel_stories")}

        if "view_count" not in story_columns:

            with db.engine.begin() as connection:

                connection.execute(text("ALTER TABLE travel_stories ADD COLUMN view_count INTEGER NOT NULL DEFAULT 0"))

        if "comments_viewed_at" not in story_columns:

            with db.engine.begin() as connection:

                connection.execute(text("ALTER TABLE travel_stories ADD COLUMN comments_viewed_at DATETIME"))

        comment_columns = {column["name"] for column in inspect(db.engine).get_columns("travel_story_comments")}

        if "parent_id" not in comment_columns:

            with db.engine.begin() as connection:

                connection.execute(text("ALTER TABLE travel_story_comments ADD COLUMN parent_id INTEGER REFERENCES travel_story_comments(id) ON DELETE CASCADE"))

        message_columns = {column["name"] for column in inspect(db.engine).get_columns("group_messages")}

        if "is_deleted" not in message_columns:

            with db.engine.begin() as connection:

                connection.execute(text("ALTER TABLE group_messages ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0"))



    @app.context_processor

    def inject_group_notification_counts():

        latest_notice_id = max((notice["id"] for notice in APP_NOTICES), default=0)

        notice_read = (db.session.get(AppNoticeRead, current_user.id)

                       if current_user.is_authenticated else None)

        has_unread_release_notices = latest_notice_id > (notice_read.latest_notice_id if notice_read else 0)

        operator_unread = False
        if current_user.is_authenticated:
            visible_operator_notices = OperatorNotice.query.filter(
                OperatorNotice.is_active.is_(True),
                OperatorNotice.audience.in_(["all", current_user.user_type])
            ).all()
            read_operator_notice_ids = {
                row.notice_id for row in OperatorNoticeRead.query.filter_by(user_id=current_user.id).all()
            }
            operator_unread = any(notice.id not in read_operator_notice_ids for notice in visible_operator_notices)
        has_unread_notices = has_unread_release_notices or operator_unread

        comment_notifications = []
        account_warnings = []

        if current_user.is_authenticated and current_user.user_type in ("traveler", "business"):
            account_warnings = (AccountWarning.query.filter_by(target_user_id=current_user.id, acknowledged_at=None)
                               .order_by(AccountWarning.created_at.asc()).all())

        if current_user.is_authenticated and current_user.user_type == "traveler":

            counts = unread_group_message_counts(current_user.id)

            rejoin_counts = pending_group_rejoin_counts(current_user.id)

            cursor = db.session.query(func.max(GroupMessage.id)).scalar() or 0

            rejoin_cursor = (db.session.query(func.max(TripGroupRejoinRequest.id))
                             .join(TripGroup, TripGroup.id == TripGroupRejoinRequest.group_id)
                             .filter(TripGroup.owner_id == current_user.id).scalar() or 0)

            comment_notifications = unread_journey_comment_notifications(current_user.id)

            return {"group_notification_counts": counts,
                    "group_rejoin_request_counts": rejoin_counts,

                    "group_notification_count": sum(counts.values()) + sum(rejoin_counts.values()),

                    "group_notification_cursor": cursor,
                    "group_rejoin_request_cursor": rejoin_cursor,

                    "unread_journey_comment_count": sum(item["count"] for item in comment_notifications),

                    "account_warnings": account_warnings,

                    "has_unread_release_notices": has_unread_release_notices,

                    "has_unread_operator_notices": operator_unread,

                    "has_unread_notices": has_unread_notices or bool(comment_notifications)}

        return {"group_notification_counts": {}, "group_notification_count": 0,
                "group_rejoin_request_counts": {},

                "group_notification_cursor": 0,
                "group_rejoin_request_cursor": 0,

                "unread_journey_comment_count": 0,

                "account_warnings": account_warnings,

                "has_unread_release_notices": has_unread_release_notices,

                "has_unread_operator_notices": operator_unread,

                "has_unread_notices": has_unread_notices}



    # 機能別Blueprintの登録

    register_blueprints(app)



    # 既存テンプレート・コードとの完全な後方互換性のためのurl_forフォールバック

    @app.url_build_error_handlers.append

    def build_error_handler(error, endpoint, values):

        for bp_obj in app.blueprints.values():

            candidate = f"{bp_obj.name}.{endpoint}"

            if candidate in app.view_functions:

                return url_for(candidate, **values)

        return None



    # view_functionsの短縮名エイリアス登録

    for ep, view_func in list(app.view_functions.items()):

        if "." in ep:

            short = ep.split(".", 1)[1]

            if short not in app.view_functions:

                app.view_functions[short] = view_func



    return app





app = create_app()


@app.cli.command("create-initial-admin")
def create_initial_admin():
    """Create the first operator account interactively; only works before one exists."""
    with app.app_context():
        if User.query.filter_by(user_type="admin").first():
            raise click.ClickException("運営アカウントはすでに存在します。追加作成は運営画面から行ってください。")
        username = click.prompt("運営者名").strip()
        email = click.prompt("メールアドレス").strip().lower()
        if not 2 <= len(username) <= 50:
            raise click.ClickException("運営者名は2〜50文字で入力してください。")
        if "@" not in email or User.query.filter_by(email=email).first():
            raise click.ClickException("メールアドレスが無効か、すでに登録されています。")
        password = click.prompt("初期パスワード（12文字以上）", hide_input=True, confirmation_prompt=True)
        if len(password) < 12:
            raise click.ClickException("パスワードは12文字以上にしてください。")
        db.session.add(User(username=username.strip()[:50], email=email,
                            password_hash=generate_password_hash(password), user_type="admin"))
        db.session.commit()
        click.echo("初回の運営アカウントを作成しました。ログイン後、運営画面から追加できます。")


if __name__ == "__main__":

    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")

