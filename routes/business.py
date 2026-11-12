"""地域事業者機能（施設・店舗の登録・編集、写真管理、電話番号認証、公開管理）のルーティング。"""

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

business_bp = Blueprint("business", __name__)


@business_bp.app_context_processor
def inject_business_photo_credits():
    credit_path = Path(current_app.static_folder) / "business_place_photos" / "attributions.json"
    try:
        credits = json.loads(credit_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        credits = {}
    return {"business_photo_credits": credits}

@business_bp.route("/business", methods=["GET", "POST"])
@login_required
def business():
    _business_only()
    if request.method == "POST":
        data = {k: request.form.get(k, "").strip() for k in ("name", "category", "prefecture", "address", "price_range", "website_url", "description", "representative_name", "access", "opening_hours")}
        data["phone"] = _normalize_business_phone(request.form.get("phone", ""))
        if not data["name"] or data["category"] not in CATEGORIES or data["prefecture"] not in PREFECTURES or not data["description"] or not data["representative_name"] or len(data["representative_name"]) > 100 or not data["phone"] or len(data["access"]) > 2000 or len(data["opening_hours"]) > 300:
            flash("施設名、カテゴリ、都道府県、代表者名、電話番号、紹介文を確認してください。電話番号は国内番号または国番号付きで入力してください。", "error")
        else:
            try:
                prepared_photos = _prepare_business_photos(request.files.getlist("photos"))
            except ValueError as exc:
                flash(str(exc), "error")
            else:
                listing = BusinessListing(user_id=current_user.id, **data)
                db.session.add(listing)
                db.session.flush()
                _store_business_photos(listing, prepared_photos)
                db.session.commit()
                flash("掲載情報と写真を保存しました。初期状態は非公開です。", "success")
                return redirect(url_for("business"))
    items = BusinessListing.query.filter_by(user_id=current_user.id).order_by(BusinessListing.updated_at.desc()).all()
    return page("business", listings=items)

@business_bp.route("/business/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_listing(item_id):
    _business_only()
    item = _owned_listing(item_id)
    if request.method == "POST":
        data = {k: request.form.get(k, "").strip() for k in ("name", "category", "prefecture", "address", "price_range", "website_url", "description", "representative_name", "access", "opening_hours")}
        data["phone"] = _normalize_business_phone(request.form.get("phone", ""))
        if not data["name"] or data["category"] not in CATEGORIES or data["prefecture"] not in PREFECTURES or not data["description"] or not data["representative_name"] or len(data["representative_name"]) > 100 or not data["phone"] or len(data["access"]) > 2000 or len(data["opening_hours"]) > 300:
            flash("施設名、カテゴリ、都道府県、代表者名、電話番号、紹介文を確認してください。電話番号は国内番号または国番号付きで入力してください。", "error")
        else:
            try:
                prepared_photos = _prepare_business_photos(request.files.getlist("photos"))
                if len(item.photos) + len(prepared_photos) > BUSINESS_MAX_PHOTOS:
                    raise ValueError(f"写真は1施設あたり{BUSINESS_MAX_PHOTOS}枚まで登録できます。")
            except ValueError as exc:
                flash(str(exc), "error")
            else:
                phone_changed = item.phone != data["phone"]
                for key, value in data.items():
                    setattr(item, key, value)
                # 電話番号が変わったら、以前の認証結果を引き継がないようにします。
                if phone_changed:
                    item.phone_verified = False
                    item.is_published = False
                    item.phone_verification_hash = ""
                    item.phone_verification_expires_at = None
                    item.phone_verification_sent_at = None
                    item.phone_verification_attempts = 0
                _store_business_photos(item, prepared_photos)
                db.session.commit()
                flash("掲載情報を更新しました。", "success")
                return redirect(url_for("edit_listing", item_id=item.id))
    return render_template("business_edit.html", page="business", item=item, categories=CATEGORIES, prefectures=PREFECTURES, max_photos=BUSINESS_MAX_PHOTOS)

@business_bp.post("/business/<int:item_id>/phone-verification/send")
@login_required
def send_business_phone_code(item_id):
    _business_only()
    item = _owned_listing(item_id)
    if not item.phone:
        flash("先に電話番号を登録して保存してください。", "error")
        return redirect(url_for("edit_listing", item_id=item.id))
    now = datetime.now(timezone.utc)
    code = f"{secrets.randbelow(1_000_000):06d}"
    item.phone_verification_hash = generate_password_hash(code)
    item.phone_verification_expires_at = now + timedelta(minutes=10)
    item.phone_verification_sent_at = now
    item.phone_verification_attempts = 0
    db.session.commit()
    flash(f"デモ用認証コードは {code} です（実際のSMSは送信されません）。10分以内に入力してください。", "info")
    return redirect(url_for("edit_listing", item_id=item.id))

@business_bp.post("/business/<int:item_id>/phone-verification/verify")
@login_required
def verify_business_phone(item_id):
    _business_only()
    item = _owned_listing(item_id)
    code = request.form.get("verification_code", "").strip()
    expires_at = item.phone_verification_expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if not item.phone_verification_hash or not expires_at or datetime.now(timezone.utc) >= expires_at:
        flash("認証コードがありません、または有効期限が切れています。再送してください。", "error")
    elif item.phone_verification_attempts >= 5:
        item.phone_verification_hash = ""
        item.phone_verification_expires_at = None
        db.session.commit()
        flash("認証に5回失敗したため、コードを無効にしました。再送してください。", "error")
    elif not re.fullmatch(r"\d{6}", code) or not check_password_hash(item.phone_verification_hash, code):
        item.phone_verification_attempts += 1
        db.session.commit()
        flash("認証コードが違います。コードを確認してください。", "error")
    else:
        item.phone_verified = True
        item.phone_verification_hash = ""
        item.phone_verification_expires_at = None
        item.phone_verification_attempts = 0
        db.session.commit()
        flash("電話番号を認証しました。", "success")
    return redirect(url_for("edit_listing", item_id=item.id))

@business_bp.get("/business/<int:item_id>/photos/<int:photo_id>")
@login_required
def business_listing_photo(item_id, photo_id):
    listing = BusinessListing.query.filter_by(id=item_id).first_or_404()
    photo = BusinessListingPhoto.query.filter_by(id=photo_id, listing_id=listing.id).first_or_404()
    if not listing.is_published and listing.user_id != current_user.id:
        abort(404)
    if photo.filename.startswith("place_"):
        credits = inject_business_photo_credits()["business_photo_credits"]
        if photo.filename not in credits:
            abort(404)
        photo_path = Path(current_app.static_folder) / "business_place_photos"
        filename = photo.filename
    # Demo listing photos ship with the application under static/. Resolve them
    # there instead of instance/ so AWS deployments can serve them after deploy.
    elif photo.filename.startswith("demo_"):
        match = re.fullmatch(
            r"demo_(lodging_[1-3]|food_[1-3]|experience_[1-3]|transport_[1-3]|other_[1-3])(?:_\d+)?\.jpg",
            photo.filename,
        )
        if not match:
            abort(404)
        photo_path = Path(current_app.static_folder) / "demo_business_photos"
        filename = f"{match.group(1)}.jpg"
    else:
        photo_path = Path(current_app.instance_path) / "business_photos" / str(listing.id)
        filename = photo.filename
    response = send_from_directory(
        photo_path,
        filename,
        as_attachment=False,
        conditional=True,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "public, max-age=86400" if photo.filename.startswith("demo_") else "private, max-age=3600"
    return response

@business_bp.post("/business/<int:item_id>/photos/<int:photo_id>/delete")
@login_required
def delete_business_listing_photo(item_id, photo_id):
    _business_only()
    listing = _owned_listing(item_id)
    photo = BusinessListingPhoto.query.filter_by(id=photo_id, listing_id=listing.id).first_or_404()
    photo_path = Path(current_app.instance_path) / "business_photos" / str(listing.id) / photo.filename
    db.session.delete(photo)
    db.session.commit()
    photo_path.unlink(missing_ok=True)
    flash("写真を削除しました。", "success")
    return redirect(url_for("edit_listing", item_id=listing.id))

@business_bp.post("/business/<int:item_id>/toggle")
@login_required
def toggle_listing(item_id):
    item = _owned_listing(item_id)
    if not item.is_published and not item.phone_verified:
        flash("掲載を公開するには、先に電話番号認証を完了してください。", "error")
        return redirect(url_for("edit_listing", item_id=item.id))
    item.is_published = not item.is_published
    db.session.commit()
    return redirect(url_for("business"))

@business_bp.post("/business/<int:item_id>/delete")
@login_required
def delete_listing(item_id):
    listing = _owned_listing(item_id)
    photo_dir = Path(current_app.instance_path) / "business_photos" / str(listing.id)
    for photo in listing.photos:
        (photo_dir / photo.filename).unlink(missing_ok=True)
    db.session.delete(listing)
    db.session.commit()
    if photo_dir.exists():
        try:
            photo_dir.rmdir()
        except OSError:
            pass
    return redirect(url_for("business"))

