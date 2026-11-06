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
    db.session.commit()
    comment_notifications = (unread_journey_comment_notifications(current_user.id)
                             if current_user.user_type == "traveler" else [])
    return page("notices", notices=APP_NOTICES,
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

@main_bp.get("/history")
@login_required
def viewing_history():
    _traveler_only()
    tab = request.args.get("tab", "all")
    if tab not in {"all", "journeys", "reviews"}:
        tab = "all"
    rows = ViewHistory.query.filter_by(user_id=current_user.id).order_by(ViewHistory.viewed_at.desc()).limit(200).all()
    history_items = []
    for row in rows:
        if tab == "journeys" and row.target_type != "journey":
            continue
        if tab == "reviews" and row.target_type != "review":
            continue
        if row.target_type == "journey":
            story = db.session.get(TravelStory, row.target_id)
            if not story or (not story.is_public and story.user_id != current_user.id):
                continue
            history_items.append({"type": "旅行記", "title": story.plan.title, "subtitle": f"{story.plan.destination} · {story.plan.days}日", "url": url_for("journey_detail", story_id=story.id), "viewed_at": row.viewed_at})
        elif row.target_type == "review":
            listing = db.session.get(BusinessListing, row.target_id)
            if not listing or not listing.is_published:
                continue
            history_items.append({"type": "口コミ", "title": listing.name, "subtitle": f"{listing.prefecture} · {listing.category}", "url": url_for("listing_reviews", item_id=listing.id), "viewed_at": row.viewed_at})
    return page("history", history_items=history_items, history_tab=tab)

@main_bp.post("/history/clear")
@login_required
def clear_viewing_history():
    _traveler_only()
    ViewHistory.query.filter_by(user_id=current_user.id).delete(synchronize_session=False)
    db.session.commit()
    flash("閲覧履歴を削除しました。", "success")
    return redirect(url_for("viewing_history"))

