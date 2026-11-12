"""認証・アカウント管理（ログイン、登録、パスワード再設定、プロフィール、アバター）のルーティング。"""



import hashlib

import json

import os

import re

import secrets

import shutil

from datetime import date, datetime, timedelta, timezone

from pathlib import Path

from urllib.parse import urljoin, urlparse



import requests

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for

from flask_login import current_user, login_required, login_user, logout_user

from sqlalchemy import and_, func, or_

from werkzeug.security import check_password_hash, generate_password_hash



from constants import *

from extensions import db

from helpers import *

from models import *

from services.ai import AIServiceError, generate_text

from services.prompts import change_prompts, plan_prompts, translation_prompts



auth_bp = Blueprint("auth", __name__)



@auth_bp.route("/auth/<mode>", methods=["GET", "POST"])

def auth(mode):

    if mode not in ("login", "register"):

        abort(404)

    if current_user.is_authenticated:

        return redirect(url_for("index"))

    if request.method == "POST":

        # メールアドレスの前後の空白を除き、小文字にそろえて検索します。

        email = request.form.get("email", "").strip().lower()

        password = request.form.get("password", "")

        if mode == "login":

            user = User.query.filter_by(email=email).first()

            # パスワードは平文比較せず、登録時に保存したハッシュと照合します。

            if user and check_password_hash(user.password_hash, password):

                if user.is_suspended:
                    flash("このアカウントは運営により利用停止中です。心当たりがない場合はお問い合わせください。", "error")
                    return page("auth", mode=mode)
                login_user(user)

                if user.user_type == "admin":

                    return redirect(url_for("admin_dashboard"))

                if _is_birthday_today(user.profile):

                    flash("お誕生日おめでとうございます！素敵な1年になりますように。🎂", "birthday")

                return redirect(complete_pending_group_invite(user) or url_for("index"))

            flash("メールアドレスまたはパスワードが違います。", "error")

        else:

            name = request.form.get("username", "").strip()

            role = request.form.get("user_type", "traveler")

            if len(name) < 2 or len(name) > 50:

                flash("ユーザー名は2〜50文字で入力してください。", "error")

            elif "@" not in email:

                flash("有効なメールアドレスを入力してください。", "error")

            elif len(password) < 8:

                flash("パスワードは8文字以上で入力してください。", "error")

            elif password != request.form.get("password_confirm", ""):

                flash("パスワードが一致しません。", "error")

            elif role not in ("traveler", "business"):

                flash("アカウント種別を選択してください。", "error")

            elif User.query.filter_by(email=email).first():

                flash("このメールアドレスは登録済みです。", "error")

            else:

                # DBにはパスワードそのものではなく、照合用ハッシュを保存します。

                user = User(username=name, email=email, password_hash=generate_password_hash(password), user_type=role)

                if role == "traveler":

                    user.profile = TravelerProfile()

                else:

                    user.business_detail = BusinessDetail()

                db.session.add(user)

                db.session.commit()

                login_user(user)

                return redirect(complete_pending_group_invite(user) or url_for("index"))

    return page("auth", mode=mode)



@auth_bp.get("/admin")
@login_required
def admin_dashboard():
    """運営機能への入口と利用状況を表示します。"""
    if current_user.user_type != "admin":
        abort(403)
    stats = {
        "traveler_count": User.query.filter_by(user_type="traveler").count(),
        "business_count": User.query.filter_by(user_type="business").count(),
        "operator_count": User.query.filter_by(user_type="admin").count(),
        "active_notice_count": OperatorNotice.query.filter_by(is_active=True).count(),
    }
    return page("admin_dashboard", stats=stats)


@auth_bp.route("/admin/accounts", methods=["GET", "POST"])
@login_required
def admin_accounts():
    """運営者だけが、追加の運営アカウントを発行できます。"""
    if current_user.user_type != "admin":
        abort(403)
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")
        if not 2 <= len(username) <= 50:
            flash("運営者名は2〜50文字で入力してください。", "error")
        elif "@" not in email or len(email) > 255:
            flash("有効なメールアドレスを入力してください。", "error")
        elif len(password) < 12:
            flash("パスワードは12文字以上で入力してください。", "error")
        elif password != password_confirm:
            flash("パスワードが一致しません。", "error")
        elif User.query.filter_by(email=email).first():
            flash("このメールアドレスはすでに登録されています。", "error")
        else:
            operator = User(username=username, email=email,
                            password_hash=generate_password_hash(password), user_type="admin")
            db.session.add(operator)
            db.session.commit()
            flash(f"運営アカウント「{username}」を作成しました。", "success")
            return redirect(url_for("admin_accounts"))
    operators = User.query.filter_by(user_type="admin").order_by(User.created_at.asc()).all()
    return page("admin_accounts", operators=operators)


@auth_bp.get("/admin/moderation")
@login_required
def admin_moderation():
    """旅行者・事業者アカウントの利用停止を管理します。"""
    if current_user.user_type != "admin":
        abort(403)
    active_role = request.args.get("type", "traveler").strip()
    if active_role not in ("traveler", "business"):
        active_role = "traveler"
    search = request.args.get("q", "").strip()[:120]
    status = request.args.get("status", "all").strip()
    if status not in ("all", "active", "suspended"):
        status = "all"
    account_query = User.query.filter_by(user_type=active_role)
    if search:
        needle = f"%{search}%"
        account_query = account_query.filter(or_(User.username.ilike(needle), User.email.ilike(needle)))
    if status == "active":
        account_query = account_query.filter_by(is_suspended=False)
    elif status == "suspended":
        account_query = account_query.filter_by(is_suspended=True)
    account_page_number = request.args.get("page", 1, type=int) or 1
    account_page = account_query.order_by(User.username.asc(), User.id.asc()).paginate(
        page=max(1, account_page_number), per_page=20, error_out=False)
    return page("admin_moderation", accounts=account_page.items, account_page=account_page,
                active_role=active_role, search=search, status=status)


@auth_bp.post("/admin/accounts/<int:user_id>/suspend")
@login_required
def suspend_account(user_id):
    if current_user.user_type != "admin":
        abort(403)
    account = db.session.get(User, user_id)
    if not account or account.user_type not in ("traveler", "business"):
        abort(404)
    reason = request.form.get("reason", "").strip()
    if len(reason) < 3 or len(reason) > 500:
        flash("停止理由を3〜500文字で入力してください。", "error")
    elif account.is_suspended:
        flash("このアカウントはすでに利用停止中です。", "info")
    else:
        account.is_suspended = True
        account.suspension_reason = reason
        account.suspended_at = datetime.now(timezone.utc)
        account.suspended_by_id = current_user.id
        db.session.add(AccountModerationLog(target_user_id=account.id, operator_id=current_user.id,
                                            action="suspend", reason=reason))
        db.session.commit()
        flash(f"「{account.username}」のアカウントを利用停止にしました。", "success")
    return redirect(url_for("admin_moderation", type=request.form.get("type", "traveler"), q=request.form.get("q", ""), status=request.form.get("status", "all"), page=request.form.get("page", 1)))


@auth_bp.post("/admin/accounts/<int:user_id>/restore")
@login_required
def restore_account(user_id):
    if current_user.user_type != "admin":
        abort(403)
    account = db.session.get(User, user_id)
    if not account or account.user_type not in ("traveler", "business"):
        abort(404)
    was_suspended = account.is_suspended
    if was_suspended:
        db.session.add(AccountModerationLog(target_user_id=account.id, operator_id=current_user.id,
                                            action="restore", reason=account.suspension_reason or "停止解除"))
    account.is_suspended = False
    account.suspension_reason = None
    account.suspended_at = None
    account.suspended_by_id = None
    db.session.commit()
    flash(f"「{account.username}」の利用停止を解除しました。", "success")
    return redirect(url_for("admin_moderation", type=request.form.get("type", "traveler"), q=request.form.get("q", ""), status=request.form.get("status", "all"), page=request.form.get("page", 1)))


@auth_bp.get("/admin/moderation/history")
@login_required
def admin_moderation_history():
    if current_user.user_type != "admin":
        abort(403)
    number = max(1, request.args.get("page", 1, type=int) or 1)
    history = AccountModerationLog.query.order_by(AccountModerationLog.created_at.desc(),
                                                   AccountModerationLog.id.desc()).paginate(
                                                       page=number, per_page=25, error_out=False)
    return page("admin_moderation_history", history=history)


@auth_bp.get("/admin/reports")
@login_required
def admin_reports():
    if current_user.user_type != "admin":
        abort(403)
    status = request.args.get("status", "open")
    if status not in ("open", "resolved", "all"):
        status = "open"
    query = AccountReport.query
    if status != "all":
        query = query.filter_by(status=status)
    number = max(1, request.args.get("page", 1, type=int) or 1)
    reports = query.order_by(AccountReport.created_at.desc(), AccountReport.id.desc()).paginate(
        page=number, per_page=20, error_out=False)
    return page("admin_reports", reports=reports, report_status=status)


@auth_bp.post("/admin/reports/<int:report_id>/update")
@login_required
def update_account_report(report_id):
    if current_user.user_type != "admin":
        abort(403)
    report = db.session.get(AccountReport, report_id)
    if not report:
        abort(404)
    next_status = request.form.get("status", "").strip()
    note = request.form.get("admin_note", "").strip()
    if next_status not in ("open", "resolved") or len(note) > 1000:
        flash("通報の対応状況またはメモを確認してください。", "error")
    else:
        report.status = next_status
        report.admin_note = note or None
        report.handled_by_id = current_user.id if next_status == "resolved" else None
        report.handled_at = datetime.now(timezone.utc) if next_status == "resolved" else None
        db.session.commit()
        flash("通報の対応状況を更新しました。", "success")
    return redirect(url_for("admin_reports", status=request.form.get("filter_status", "open")))


@auth_bp.post("/admin/accounts/<int:user_id>/warnings")
@login_required
def send_account_warning(user_id):
    if current_user.user_type != "admin":
        abort(403)
    account = db.session.get(User, user_id)
    message = request.form.get("message", "").strip()
    if not account or account.user_type not in ("traveler", "business"):
        abort(404)
    if not 5 <= len(message) <= 1000:
        flash("警告メッセージは5〜1,000文字で入力してください。", "error")
    else:
        db.session.add(AccountWarning(target_user_id=account.id, operator_id=current_user.id,
                                      message=message))
        db.session.commit()
        flash(f"「{account.username}」へ警告メッセージを送りました。", "success")
    return redirect(url_for("admin_moderation", type=request.form.get("type", "traveler"),
                            q=request.form.get("q", ""), status=request.form.get("status", "all"),
                            page=request.form.get("page", 1)))


@auth_bp.post("/warnings/<int:warning_id>/acknowledge")
@login_required
def acknowledge_account_warning(warning_id):
    if current_user.user_type not in ("traveler", "business"):
        abort(403)
    warning = db.session.get(AccountWarning, warning_id)
    if not warning or warning.target_user_id != current_user.id:
        abort(404)
    if warning.acknowledged_at is None:
        warning.acknowledged_at = datetime.now(timezone.utc)
        db.session.commit()
    return redirect(url_for("index"))


@auth_bp.route("/admin/notices", methods=["GET", "POST"])
@login_required
def admin_notices():
    """運営者だけが対象者を選んでお知らせを配信・管理できます。"""
    if current_user.user_type != "admin":
        abort(403)
    if request.method == "POST":
        audience = request.form.get("audience", "").strip()
        category = request.form.get("category", "").strip()
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        if audience not in ("all", "traveler", "business"):
            flash("配信先を選択してください。", "error")
        elif category not in ("サービス情報", "メンテナンス", "重要なお知らせ", "その他"):
            flash("お知らせの種類を選択してください。", "error")
        elif not title or len(title) > 120:
            flash("タイトルを1〜120文字で入力してください。", "error")
        elif not body or len(body) > 3000:
            flash("本文を1〜3,000文字で入力してください。", "error")
        else:
            db.session.add(OperatorNotice(audience=audience, category=category, title=title,
                                          body=body, author_id=current_user.id))
            db.session.commit()
            flash("お知らせを配信しました。対象アカウントのお知らせ画面に表示されます。", "success")
            return redirect(url_for("admin_notices"))
    operator_notices = OperatorNotice.query.order_by(OperatorNotice.created_at.desc()).limit(50).all()
    return page("admin_notices", operator_notices=operator_notices)


@auth_bp.route("/admin/notices/<int:notice_id>/edit", methods=["GET", "POST"])
@login_required
def edit_operator_notice(notice_id):
    if current_user.user_type != "admin":
        abort(403)
    notice = db.session.get(OperatorNotice, notice_id)
    if not notice or not notice.is_active:
        abort(404)
    values = {"audience": notice.audience, "category": notice.category,
              "title": notice.title, "body": notice.body}
    if request.method == "POST":
        values = {key: request.form.get(key, "").strip()
                  for key in ("audience", "category", "title", "body")}
        valid = True
        if values["audience"] not in ("all", "traveler", "business"):
            flash("配信先を選択してください。", "error"); valid = False
        elif values["category"] not in ("サービス情報", "メンテナンス", "重要なお知らせ", "その他"):
            flash("お知らせの種類を選択してください。", "error"); valid = False
        elif not values["title"] or len(values["title"]) > 120:
            flash("タイトルを1〜120文字で入力してください。", "error"); valid = False
        elif not values["body"] or len(values["body"]) > 3000:
            flash("本文を1〜3,000文字で入力してください。", "error"); valid = False
        if valid:
            notice.audience = values["audience"]
            notice.category = values["category"]
            notice.title = values["title"]
            notice.body = values["body"]
            OperatorNoticeRead.query.filter_by(notice_id=notice.id).delete(synchronize_session=False)
            db.session.commit()
            flash("お知らせを更新しました。対象者には未読として再表示されます。", "success")
            return redirect(url_for("admin_notices"))
    return page("admin_notice_edit", notice=notice, values=values)


@auth_bp.post("/admin/notices/<int:notice_id>/withdraw")
@login_required
def withdraw_operator_notice(notice_id):
    if current_user.user_type != "admin":
        abort(403)
    notice = db.session.get(OperatorNotice, notice_id)
    if not notice:
        abort(404)
    if notice.is_active:
        notice.is_active = False
        db.session.commit()
        flash("お知らせの配信を取り消しました。対象者のお知らせ一覧から非表示になりました。", "success")
    else:
        flash("このお知らせはすでに取り消されています。", "info")
    return redirect(url_for("admin_notices"))


@auth_bp.get("/login")

def login_page():

    next_url = request.args.get("next")

    return redirect(url_for("auth", mode="login", next=next_url) if next_url else url_for("auth", mode="login"))



@auth_bp.route("/password-reset", methods=["GET", "POST"])

def password_reset_request():

    mail_sender = current_app.config["MAIL_DEFAULT_SENDER"] or current_app.config["MAIL_USERNAME"]

    mail_configured = bool(current_app.config["MAIL_SERVER"] and mail_sender)

    dev_mode = current_app.config["PASSWORD_RESET_DEV_MODE"]

    if current_user.is_authenticated:

        return redirect(url_for("index"))

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()

        # 同じメールアドレスへの再発行は1時間に3回までに抑えます。メールは保存せずHMAC値だけ残します。

        allowed = _allow_rate_limited_action("password-reset", email or "empty", 3, 3600)

        user = User.query.filter_by(email=email).first() if email else None

        if user and allowed:

            raw_token = secrets.token_urlsafe(32)

            now = datetime.now(timezone.utc)

            # 新しいリンクを発行したら以前の未使用リンクを無効にします。

            PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).update(

                {PasswordResetToken.used_at: now}, synchronize_session=False

            )

            reset_token = PasswordResetToken(

                user_id=user.id,

                token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),

                created_at=now,

                expires_at=now + timedelta(minutes=30),

            )

            db.session.add(reset_token)

            db.session.commit()

            reset_path = url_for("password_reset", token=raw_token)

            public_base = current_app.config["PUBLIC_BASE_URL"]

            if public_base:

                parsed_base = urlparse(public_base)

                if parsed_base.scheme in {"https", "http"} and parsed_base.netloc and (dev_mode or parsed_base.scheme == "https"):

                    reset_url = urljoin(public_base.rstrip("/") + "/", reset_path.lstrip("/"))

                else:

                    reset_url = ""

            elif dev_mode:

                # 開発環境だけ現在のローカルURLを使います。本番では固定URLを.envに設定します。

                reset_url = url_for("password_reset", token=raw_token, _external=True)

            else:

                reset_url = ""

            if reset_url:

                _send_password_reset_link(user.email, reset_url)

            else:

                current_app.logger.error("Password reset email skipped: set HTTPS PUBLIC_BASE_URL.")

        flash("登録済みのメールアドレスの場合、パスワード再設定用リンクを送信しました。画面の案内をご確認ください。", "success")

        return redirect(url_for("password_reset_request"))

    return render_template("password_reset_request.html", dev_mode=dev_mode, mail_configured=mail_configured)



@auth_bp.route("/password-reset/<token>", methods=["GET", "POST"])

def password_reset(token):

    if current_user.is_authenticated:

        return redirect(url_for("index"))

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    reset_token = PasswordResetToken.query.filter_by(token_hash=token_hash, used_at=None).first()

    now = datetime.now(timezone.utc)

    expires_at = reset_token.expires_at if reset_token else None

    if expires_at and expires_at.tzinfo is None:

        expires_at = expires_at.replace(tzinfo=timezone.utc)

    token_valid = bool(reset_token and expires_at and now < expires_at)

    if not token_valid:

        return render_template("password_reset.html", token_valid=False, expired=bool(expires_at and now >= expires_at))



    user = db.session.get(User, reset_token.user_id)

    if not user:

        return render_template("password_reset.html", token_valid=False, expired=False)

    if request.method == "POST":

        password = request.form.get("password", "")

        password_confirm = request.form.get("password_confirm", "")

        if len(password) < 8:

            flash("パスワードは8文字以上で入力してください。", "error")

        elif password != password_confirm:

            flash("パスワードが一致しません。", "error")

        else:

            user.password_hash = generate_password_hash(password)

            reset_token.used_at = now

            db.session.commit()

            # 変更完了を登録メールへ通知します。メール失敗で再設定自体は取り消しません。

            _send_password_changed_notice(user.email)

            flash("パスワードを再設定しました。新しいパスワードでログインしてください。", "success")

            return redirect(url_for("auth", mode="login"))

    return render_template("password_reset.html", token_valid=True, expired=False, token=token)



@auth_bp.post("/logout")

@login_required

def logout():

    logout_user()

    return redirect(url_for("auth", mode="login"))



@auth_bp.route("/account", methods=["GET", "POST"])

@login_required

def account():

    return redirect(url_for("profile"))



@auth_bp.get("/users/<int:user_id>/avatar")

@login_required

def user_avatar(user_id):

    user = db.session.get(User, user_id)

    if not user or not user.avatar_image:

        abort(404)

    response = send_from_directory(Path(current_app.instance_path) / "avatars", user.avatar_image, as_attachment=False, conditional=True)

    response.headers["X-Content-Type-Options"] = "nosniff"

    response.headers["Cache-Control"] = "private, max-age=3600"

    return response



@auth_bp.route("/profile", methods=["GET", "POST"])

@login_required

def profile():

    p = current_user.profile

    if current_user.user_type == "traveler" and p is None:

        p = TravelerProfile()

    profile_username = current_user.username

    selected_avatar = "keep" if current_user.avatar_image else current_user.avatar

    if request.method == "POST":

        profile_username = request.form.get("username", "").strip()

        selected_avatar = request.form.get("avatar", "")

        uploaded_avatar = request.files.get("avatar_image")

        prepared_avatar = None

        error_message = None

        if not 2 <= len(profile_username) <= 50:

            error_message = "名前は2〜50文字で入力してください。"

        elif selected_avatar not in AVATARS and not (selected_avatar == "keep" and current_user.avatar_image) and not (uploaded_avatar and uploaded_avatar.filename):

            error_message = "アイコンを選択してください。"

        else:

            try:

                prepared_avatar = _prepare_avatar_image(uploaded_avatar) if uploaded_avatar and uploaded_avatar.filename else None

            except ValueError as error:

                error_message = str(error)



        if not error_message and current_user.user_type == "traveler":

            p.interest_themes = ",".join(x for x in request.form.getlist("themes") if x in THEMES)

            p.travel_pace = request.form.get("travel_pace", "")[:30]

            p.transportation = request.form.get("transportation", "")[:100]

            p.food_preference = request.form.get("food_preference", "")[:100]

            p.avoid_conditions = request.form.get("avoid_conditions", "")[:2000]

            try:

                raw_budget = request.form.get("budget_per_trip", "").strip()

                budget_per_trip = max(0, int(raw_budget)) if raw_budget else None

                raw_birth_date = request.form.get("birth_date", "").strip()

                birth_date = date.fromisoformat(raw_birth_date) if raw_birth_date else None

                if birth_date and birth_date > date.today():

                    error_message = "生年月日は今日以前の日付を入力してください。"

            except ValueError:

                error_message = "旅行予算または生年月日を確認してください。"



        if error_message:

            flash(error_message, "error")

        else:

            # 画像の保存に成功してからDB情報を更新し、古い画像は保存後に片付けます。

            current_user.username = profile_username

            old_avatar_path = None

            if prepared_avatar:

                avatar_file, extension = prepared_avatar

                avatar_dir = Path(current_app.instance_path) / "avatars"

                avatar_dir.mkdir(parents=True, exist_ok=True)

                filename = f"{secrets.token_hex(16)}{extension}"

                avatar_file.save(avatar_dir / filename)

                if current_user.avatar_image:

                    old_avatar_path = avatar_dir / current_user.avatar_image

                current_user.avatar_image = filename

            elif selected_avatar != "keep":

                current_user.avatar = selected_avatar

                if current_user.avatar_image:

                    old_avatar_path = Path(current_app.instance_path) / "avatars" / current_user.avatar_image

                    current_user.avatar_image = None



            if current_user.user_type == "traveler":

                p.budget_per_trip = budget_per_trip

                p.birth_date = birth_date

                current_user.profile = p

            db.session.commit()

            if old_avatar_path:

                old_avatar_path.unlink(missing_ok=True)

            flash("プロフィールを保存しました。" + ("次のAI生成に反映します。" if current_user.user_type == "traveler" else ""), "success")

            return redirect(url_for("profile"))

    return page("profile", profile=p, profile_username=profile_username, selected_avatar=selected_avatar)



