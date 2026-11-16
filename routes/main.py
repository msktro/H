"""メイン画面（トップ、お知らせ、お問い合わせ、利用履歴）のルーティング。"""

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

main_bp = Blueprint("main", __name__)

@main_bp.get("/")
@login_required
# ホーム、お知らせ、お問い合わせ
def index():
    if current_user.user_type == "admin":
        return redirect(url_for("admin_dashboard"))
    popular = []
    if current_user.user_type == "traveler":
        popular_rows = (db.session.query(TravelStory, func.count(TravelStoryLike.id).label("like_count"))
                        .outerjoin(TravelStoryLike, TravelStoryLike.story_id == TravelStory.id)
                        .filter(TravelStory.is_public.is_(True))
                        .group_by(TravelStory.id)
                        .order_by(func.count(TravelStoryLike.id).desc(),
                                  TravelStory.view_count.desc(),
                                  TravelStory.created_at.desc())
                        .limit(3).all())
        for story, like_count in popular_rows:
            story.popular_like_count = int(like_count or 0)
            popular.append(story)
    return page("menu", popular=popular)

@main_bp.get("/notices")
@login_required
def notices():
    latest_notice_id = max((notice["id"] for notice in APP_NOTICES), default=0)
    read_marker = db.session.get(AppNoticeRead, current_user.id)
    if read_marker is None:
        read_marker = AppNoticeRead(user_id=current_user.id, latest_notice_id=latest_notice_id)
        db.session.add(read_marker)
    else:
        read_marker.latest_notice_id = latest_notice_id

    audience_notices = (OperatorNotice.query
                        .filter(OperatorNotice.is_active.is_(True),
                                OperatorNotice.audience.in_(["all", current_user.user_type]))
                        .order_by(OperatorNotice.created_at.desc()).all())
    read_notice_ids = {row.notice_id for row in OperatorNoticeRead.query.filter_by(user_id=current_user.id).all()}
    for notice in audience_notices:
        if notice.id not in read_notice_ids:
            db.session.add(OperatorNoticeRead(notice_id=notice.id, user_id=current_user.id))
    db.session.commit()

    sorted_notices = []
    for notice in APP_NOTICES:
        item = dict(notice)
        item["_sort_at"] = datetime.strptime(notice["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        sorted_notices.append(item)
    for notice in audience_notices:
        created_at = notice.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        sorted_notices.append({
            "id": f"operator-{notice.id}",
            "date": created_at.strftime("%Y-%m-%d"),
            "category": notice.category,
            "title": notice.title,
            "details": [notice.body],
            "audience": notice.audience,
            "audience_label": {"all": "全員向け", "traveler": "旅行者向け", "business": "事業者向け"}.get(notice.audience, ""),
            "_sort_at": created_at,
        })
    sorted_notices.sort(key=lambda item: item["_sort_at"], reverse=True)
    for item in sorted_notices:
        item.pop("_sort_at", None)
    comment_notifications = (unread_journey_comment_notifications(current_user.id)
                             if current_user.user_type == "traveler" else [])
    return page("notices", notices=sorted_notices,
                comment_notifications=comment_notifications)

@main_bp.route("/contact", methods=["GET", "POST"])
def contact():
    contact_categories = ["サービスについて", "不具合の報告", "機能の要望", "その他"]
    values = {
        "name": current_user.username if current_user.is_authenticated else "",
        "email": current_user.email if current_user.is_authenticated else "",
        "category": contact_categories[0], "subject": "", "message": "",
    }
    if request.method == "POST":
        # 隠し欄に値が入った送信は自動投稿とみなし、保存せず成功画面へ戻します。
        if request.form.get("website", "").strip():
            flash("お問い合わせを受け付けました。", "success")
            return redirect(url_for("contact"))
        # 送信元IPはハッシュでだけ記録し、1時間に5件までに制限します。
        if not _allow_rate_limited_action("contact", request.remote_addr or "unknown", 5, 3600):
            flash("送信が続いています。しばらく時間を置いてからお試しください。", "error")
            return page("contact", contact_categories=contact_categories, values=values), 429
        values.update({key: request.form.get(key, "").strip() for key in ("name", "email", "category", "subject", "message")})
        valid_email = re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", values["email"])
        has_header_break = any(character in values["name"] + values["subject"] for character in "\r\n")
        if (not 2 <= len(values["name"]) <= 80
                or not valid_email
                or values["category"] not in contact_categories
                or not 1 <= len(values["subject"]) <= 160
                or has_header_break
                or not 10 <= len(values["message"]) <= 5000):
            flash("入力内容を確認してください。メールアドレス、件名、お問い合わせ本文を確認してください。", "error")
            return page("contact", contact_categories=contact_categories, values=values), 400
        inquiry = ContactInquiry(**values)
        db.session.add(inquiry)
        db.session.commit()
        # 受付をDBへ確実に保存してから、担当者通知と利用者への受付メールを送ります。
        notified = _send_contact_notification(inquiry)
        receipt_sent = _send_contact_receipt(inquiry)
        notice = f"お問い合わせを受け付けました（受付番号: {inquiry.id}）。内容はアプリ内に保存しました。"
        notice += "確認メールを送信しました。" if receipt_sent else "確認メールは送信できませんでした。"
        notice += "担当者にも通知しました。" if notified else "担当者へのメール通知は未設定です。"
        flash(notice, "success")
        return redirect(url_for("contact"))
    return page("contact", contact_categories=contact_categories, values=values)


@main_bp.route("/report-account", methods=["GET", "POST"])
@login_required
def report_account():
    """ログイン利用者が旅行者・事業者アカウントを運営へ通報します。"""
    if current_user.user_type not in ("traveler", "business"):
        abort(403)
    report_categories = ["不適切な投稿", "迷惑行為", "なりすまし・虚偽情報", "その他"]
    targets = (User.query.filter(User.user_type.in_(("traveler", "business")), User.id != current_user.id)
               .order_by(User.user_type.asc(), User.username.asc()).all())
    selected_target_id = request.args.get("target_user_id", type=int) if request.method == "GET" else request.form.get("target_user_id", type=int)
    selected_target = db.session.get(User, selected_target_id) if selected_target_id else None
    if selected_target and (selected_target.id == current_user.id or selected_target.user_type not in ("traveler", "business")):
        selected_target = None
        selected_target_id = None
    return_to = request.args.get("return_to", "") if request.method == "GET" else request.form.get("return_to", "")
    parsed_return = urlparse(return_to)
    if not return_to.startswith("/") or return_to.startswith("//") or "\\" in return_to or parsed_return.netloc:
        return_to = ""
    context_label = (request.args.get("context", "") if request.method == "GET" else request.form.get("context", ""))[:80]
    selected_category = request.form.get("category", report_categories[0]) if request.method == "POST" else report_categories[0]
    details_value = request.form.get("details", "") if request.method == "POST" else ""
    if selected_target:
        targets = [selected_target]
    if request.method == "POST":
        target_id = request.form.get("target_user_id", type=int)
        category = request.form.get("category", "").strip()
        details = request.form.get("details", "").strip()
        target = db.session.get(User, target_id) if target_id else None
        if not _allow_rate_limited_action("account-report", str(current_user.id), 5, 3600):
            flash("通報の送信回数が上限に達しました。時間を置いてからお試しください。", "error")
        elif not target or target.id == current_user.id or target.user_type not in ("traveler", "business"):
            flash("通報するアカウントを選択してください。", "error")
        elif category not in report_categories or not 10 <= len(details) <= 2000:
            flash("通報理由と詳細（10〜2,000文字）を確認してください。", "error")
        else:
            db.session.add(AccountReport(reporter_id=current_user.id, target_user_id=target.id,
                                         category=category, details=details))
            db.session.commit()
            flash("通報を運営へ送信しました。確認までお待ちください。", "success")
            return redirect(return_to or url_for("report_account"))
    return page("report_account", targets=targets, report_categories=report_categories,
                selected_target=selected_target, selected_target_id=selected_target_id,
                return_to=return_to, context_label=context_label,
                selected_category=selected_category, details_value=details_value)

@main_bp.get("/history")
@login_required
def viewing_history():
    _traveler_only()
    tab = request.args.get("tab", "all")
    if tab not in {"all", "journeys", "reviews"}:
        tab = "all"
    rows = ViewHistory.query.filter_by(user_id=current_user.id).order_by(ViewHistory.viewed_at.desc()).limit(200).all()
    all_items = []
    for row in rows:
        if row.target_type == "journey":
            story = db.session.get(TravelStory, row.target_id)
            if not story or (not story.is_public and story.user_id != current_user.id):
                continue
            all_items.append({"type": "旅行記", "target_type": row.target_type, "target_id": row.target_id,
                              "title": story.plan.title, "subtitle": f"{story.plan.destination} · {story.plan.days}日",
                              "url": url_for("journey_detail", story_id=story.id), "viewed_at": row.viewed_at})
        elif row.target_type == "review":
            listing = db.session.get(BusinessListing, row.target_id)
            if not listing or not listing.is_published:
                continue
            all_items.append({"type": "口コミ", "target_type": row.target_type, "target_id": row.target_id,
                              "title": listing.name, "subtitle": f"{listing.prefecture} · {listing.category}",
                              "url": url_for("listing_reviews", item_id=listing.id), "viewed_at": row.viewed_at})
    history_items = [item for item in all_items
                     if tab == "all" or (tab == "journeys" and item["target_type"] == "journey")
                     or (tab == "reviews" and item["target_type"] == "review")]
    return page("history", history_items=history_items, history_tab=tab,
                history_has_journeys=any(item["target_type"] == "journey" for item in all_items),
                history_has_reviews=any(item["target_type"] == "review" for item in all_items))

@main_bp.post("/history/delete/<target_type>/<int:target_id>")
@login_required
def delete_viewing_history_item(target_type, target_id):
    _traveler_only()
    if target_type not in {"journey", "review"}:
        abort(404)
    item = ViewHistory.query.filter_by(user_id=current_user.id, target_type=target_type, target_id=target_id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("閲覧履歴を削除しました。", "success")
    tab = request.form.get("tab", "all")
    if tab not in {"all", "journeys", "reviews"}:
        tab = "all"
    return redirect(url_for("viewing_history", tab=tab))

@main_bp.post("/history/clear/<target_type>")
@login_required
def clear_viewing_history_category(target_type):
    _traveler_only()
    if target_type not in {"journey", "review"}:
        abort(404)
    deleted = ViewHistory.query.filter_by(user_id=current_user.id, target_type=target_type).delete(synchronize_session=False)
    db.session.commit()
    flash("旅行記の履歴を削除しました。" if target_type == "journey" else "口コミの履歴を削除しました。", "success")
    tab = request.form.get("tab", target_type + "s")
    if tab not in {"all", "journeys", "reviews"}:
        tab = "all"
    return redirect(url_for("viewing_history", tab=tab))

@main_bp.post("/history/clear")
@login_required
def clear_viewing_history():
    _traveler_only()
    ViewHistory.query.filter_by(user_id=current_user.id).delete(synchronize_session=False)
    db.session.commit()
    flash("閲覧履歴を削除しました。", "success")
    return redirect(url_for("viewing_history"))

