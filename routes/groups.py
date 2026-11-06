"""グループ旅行機能（チャット、アルバム、メモ、割り勘、予算、プラン共有）のルーティング。"""

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

groups_bp = Blueprint("groups", __name__)

@groups_bp.get("/groups/invite/<invite_code>")
# グループ: 招待、参加、メンバー、共有情報
def group_invite(invite_code):
    code = invite_code.strip().upper()
    group = TripGroup.query.filter_by(invite_code=code).first()
    if not group:
        flash("招待コードが見つかりません。", "error")
        return redirect(url_for("auth", mode="login") if not current_user.is_authenticated else url_for("index"))
    session["pending_group_invite"] = code
    if not current_user.is_authenticated:
        flash("ログインまたは新規登録すると、このグループに参加できます。", "info")
        return redirect(url_for("auth", mode="login"))
    return redirect(complete_pending_group_invite(current_user) or url_for("index"))

@groups_bp.get("/groups")
@login_required
def groups():
    _traveler_only()
    memberships = TripGroupMember.query.filter_by(user_id=current_user.id).all()
    return page("groups", groups=[membership.group for membership in memberships],
                group_unread_counts=unread_group_message_counts(current_user.id))

@groups_bp.get("/api/group-notifications")
@login_required
def group_notifications():
    if current_user.user_type != "traveler":
        return jsonify(error="旅行者アカウントが必要です。"), 403
    after_id = max(0, request.args.get("after", default=0, type=int) or 0)
    messages = (GroupMessage.query
                .join(TripGroupMember, TripGroupMember.group_id == GroupMessage.group_id)
                .filter(
                    TripGroupMember.user_id == current_user.id,
                    GroupMessage.id > after_id,
                    GroupMessage.user_id != current_user.id,
                    GroupMessage.is_deleted.is_(False),
                )
                .order_by(GroupMessage.id.asc()).limit(50).all())
    global_cursor = db.session.query(func.max(GroupMessage.id)).scalar() or after_id
    next_cursor = messages[-1].id if len(messages) == 50 else max(after_id, global_cursor)
    unread_counts = unread_group_message_counts(current_user.id)
    comment_notifications = unread_journey_comment_notifications(current_user.id)
    return jsonify(
        cursor=next_cursor,
        unread_total=sum(unread_counts.values()),
        unread_counts={str(group_id): count for group_id, count in unread_counts.items()},
        unread_journey_comment_count=sum(item["count"] for item in comment_notifications),
        unread_journey_comment_counts={str(item["story"].id): item["count"] for item in comment_notifications},
        messages=[{
            "id": message.id,
            "group_id": message.group_id,
            "group_name": message.group.name,
            "username": message.user.username,
            "content": message.content,
        } for message in messages],
    )

@groups_bp.post("/groups/create")
@login_required
def create_group():
    _traveler_only()
    name = request.form.get("name", "").strip()[:80]
    if not name:
        flash("グループ名を入力してください。", "error")
        return redirect(url_for("groups"))
    code = secrets.token_urlsafe(9).replace("-", "").replace("_", "").upper()
    while TripGroup.query.filter_by(invite_code=code).first():
        code = secrets.token_urlsafe(9).replace("-", "").replace("_", "").upper()
    group = TripGroup(name=name, invite_code=code, owner_id=current_user.id)
    db.session.add(group)
    # flushでグループIDを先に採番し、作成者を最初のメンバーとして登録します。
    db.session.flush()
    db.session.add(TripGroupMember(group_id=group.id, user_id=current_user.id))
    db.session.commit()
    flash("グループを作成しました。招待コードを仲間に共有してください。", "success")
    return redirect(url_for("group_detail", group_id=group.id))

@groups_bp.get("/groups/<int:group_id>/delete")
@login_required
def confirm_delete_group(group_id):
    _traveler_only()
    group = db.session.get(TripGroup, group_id)
    if not group:
        abort(404)
    if group.owner_id != current_user.id:
        abort(403)
    return page("group_delete_confirm", group=group)

@groups_bp.post("/groups/<int:group_id>/delete")
@login_required
def delete_group(group_id):
    _traveler_only()
    group = db.session.get(TripGroup, group_id)
    if not group:
        abort(404)
    if group.owner_id != current_user.id:
        abort(403)

    confirmed_name = request.form.get("confirm_group_name", "").strip()
    if confirmed_name != group.name:
        flash("入力したグループ名が一致しません。削除は行われていません。", "error")
        return redirect(url_for("confirm_delete_group", group_id=group.id))

    group_name = group.name
    group_id = group.id

    # Keep travelers' plans, but remove their link to the deleted group.
    TravelPlan.query.filter_by(group_id=group_id).update(
        {TravelPlan.group_id: None}, synchronize_session=False
    )
    for expense in GroupExpense.query.filter_by(group_id=group_id).all():
        db.session.delete(expense)
    GroupBudget.query.filter_by(group_id=group_id).delete(synchronize_session=False)

    # TripGroup relationships cascade to members, messages, notes, and photos.
    db.session.delete(group)
    db.session.commit()

    shutil.rmtree(Path(current_app.instance_path) / "group_icons" / str(group_id), ignore_errors=True)
    shutil.rmtree(Path(current_app.instance_path) / "group_album" / str(group_id), ignore_errors=True)
    flash(f"「{group_name}」を削除しました。", "success")
    return redirect(url_for("groups"))

@groups_bp.post("/groups/join")
@login_required
def join_group():
    _traveler_only()
    code = request.form.get("invite_code", "").strip().upper()
    group = TripGroup.query.filter_by(invite_code=code).first()
    if not group:
        flash("招待コードが見つかりません。", "error")
        return redirect(url_for("groups"))
    membership = TripGroupMember.query.filter_by(group_id=group.id, user_id=current_user.id).first()
    if membership:
        flash("すでにこのグループに参加しています。", "info")
    else:
        db.session.add(TripGroupMember(group_id=group.id, user_id=current_user.id))
        db.session.commit()
        flash("グループに参加しました。", "success")
    return redirect(url_for("group_detail", group_id=group.id))

@groups_bp.get("/groups/<int:group_id>")
@login_required
def group_detail(group_id):
    _traveler_only()
    group = _member_group(group_id)
    own_plans = TravelPlan.query.filter_by(user_id=current_user.id).order_by(TravelPlan.updated_at.desc()).all()
    shareable_plans = [plan for plan in own_plans if plan.group_id is None]
    shared_plans = TravelPlan.query.filter_by(group_id=group.id).order_by(TravelPlan.updated_at.desc()).all()
    expenses = GroupExpense.query.filter_by(group_id=group.id).order_by(GroupExpense.spent_on.desc(), GroupExpense.id.desc()).all()
    travel_notes = sorted(GroupTravelNote.query.filter_by(group_id=group.id).all(), key=lambda note: (not note.starts_at, note.starts_at, note.id))
    group_budget = GroupBudget.query.filter_by(group_id=group.id).first()
    spent_total = sum(expense.amount for expense in expenses)
    budget_amount = group_budget.amount if group_budget else 0
    budget_percent = min(100, int(spent_total * 100 / budget_amount)) if budget_amount else 0
    album_photos = GroupAlbumPhoto.query.filter_by(group_id=group.id).order_by(GroupAlbumPhoto.created_at.desc(), GroupAlbumPhoto.id.desc()).limit(100).all()
    chat_messages = GroupMessage.query.filter_by(group_id=group.id, is_deleted=False).order_by(GroupMessage.id.desc()).limit(100).all()
    chat_messages.reverse()
    settlements = _calculate_settlements(group.members, expenses)
    return page("group_detail", group=group, shareable_plans=shareable_plans, shared_plans=shared_plans,
                expenses=expenses, settlements=settlements, today=date.today(), group_budget=group_budget,
                spent_total=spent_total, budget_percent=budget_percent,
                own_expense_count=sum(expense.created_by_id == current_user.id for expense in expenses),
                travel_notes=travel_notes,
                chat_messages=[_serialize_group_message(message, current_user.id) for message in chat_messages],
                album_photos=album_photos,
                group_members=sorted(group.members, key=lambda m: m.user.username.lower()))

@groups_bp.post("/groups/<int:group_id>/icon")
@login_required
def update_group_icon(group_id):
    _traveler_only()
    group = _member_group(group_id)
    if group.owner_id != current_user.id:
        abort(403)
    icon = request.form.get("icon", "")
    uploaded_icon = request.files.get("icon_image")
    try:
        prepared_icon = _prepare_avatar_image(uploaded_icon) if uploaded_icon and uploaded_icon.filename else None
    except ValueError as error:
        flash(str(error), "error")
    else:
        if not prepared_icon and icon not in AVATARS:
            flash("絵文字を選ぶか、画像を指定してください。", "error")
        else:
            old_icon_path = None
            if prepared_icon:
                image_file, extension = prepared_icon
                icon_dir = Path(current_app.instance_path) / "group_icons" / str(group.id)
                icon_dir.mkdir(parents=True, exist_ok=True)
                filename = f"{secrets.token_hex(16)}{extension}"
                image_file.save(icon_dir / filename)
                if group.icon_image:
                    old_icon_path = icon_dir / group.icon_image
                group.icon_image = filename
            else:
                group.icon = icon
                if group.icon_image:
                    old_icon_path = Path(current_app.instance_path) / "group_icons" / str(group.id) / group.icon_image
                    group.icon_image = None
            db.session.commit()
            if old_icon_path:
                old_icon_path.unlink(missing_ok=True)
            flash("グループアイコンを更新しました。", "success")
    return redirect(url_for("group_detail", group_id=group.id, _anchor="overview"))

@groups_bp.get("/groups/<int:group_id>/icon-image")
@login_required
def group_icon_image(group_id):
    group = _member_group(group_id)
    if not group.icon_image:
        abort(404)
    response = send_from_directory(Path(current_app.instance_path) / "group_icons" / str(group.id), group.icon_image, as_attachment=False, conditional=True)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, max-age=3600"
    return response

@groups_bp.post("/groups/<int:group_id>/notes")
@login_required
def add_group_travel_note(group_id):
    _traveler_only()
    group = _member_group(group_id)
    category = request.form.get("category", "メモ").strip()
    title = request.form.get("title", "").strip()
    starts_at = request.form.get("starts_at", "").strip()
    location = request.form.get("location", "").strip()
    reservation_url = request.form.get("reservation_url", "").strip()
    details = request.form.get("details", "").strip()
    categories = {"集合", "予約", "移動", "メモ"}
    if category not in categories or not title or len(title) > 120 or len(starts_at) > 16 or len(location) > 200 or len(reservation_url) > 2048 or len(details) > 2000 or not _valid_note_datetime(starts_at):
        flash("旅程メモの入力内容を確認してください。", "error")
        return redirect(url_for("group_detail", group_id=group.id, _anchor="notes"))
    if reservation_url:
        parsed_url = urlparse(reservation_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            flash("予約URLはhttp://またはhttps://から始まるURLを入力してください。", "error")
            return redirect(url_for("group_detail", group_id=group.id, _anchor="notes"))
    note = GroupTravelNote(group_id=group.id, created_by_id=current_user.id, category=category,
                           title=title, starts_at=starts_at, location=location,
                           reservation_url=reservation_url, details=details)
    db.session.add(note)
    db.session.commit()
    flash("旅程・予約メモを追加しました。", "success")
    return redirect(url_for("group_detail", group_id=group.id, _anchor="notes"))

@groups_bp.post("/groups/<int:group_id>/notes/<int:note_id>/edit")
@login_required
def edit_group_travel_note(group_id, note_id):
    _traveler_only()
    group = _member_group(group_id)
    note = GroupTravelNote.query.filter_by(id=note_id, group_id=group.id).first_or_404()
    if note.created_by_id != current_user.id and group.owner_id != current_user.id:
        abort(403)
    category = request.form.get("category", "メモ").strip()
    title = request.form.get("title", "").strip()
    starts_at = request.form.get("starts_at", "").strip()
    location = request.form.get("location", "").strip()
    reservation_url = request.form.get("reservation_url", "").strip()
    details = request.form.get("details", "").strip()
    if category not in {"集合", "予約", "移動", "メモ"} or not title or len(title) > 120 or len(starts_at) > 16 or len(location) > 200 or len(reservation_url) > 2048 or len(details) > 2000 or not _valid_note_datetime(starts_at):
        flash("旅程メモの入力内容を確認してください。", "error")
        return redirect(url_for("group_detail", group_id=group.id, _anchor="notes"))
    if reservation_url:
        parsed_url = urlparse(reservation_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            flash("予約URLはhttp://またはhttps://から始まるURLを入力してください。", "error")
            return redirect(url_for("group_detail", group_id=group.id, _anchor="notes"))
    note.category, note.title, note.starts_at = category, title, starts_at
    note.location, note.reservation_url, note.details = location, reservation_url, details
    db.session.commit()
    flash("旅程・予約メモを更新しました。", "success")
    return redirect(url_for("group_detail", group_id=group.id, _anchor="notes"))

@groups_bp.post("/groups/<int:group_id>/notes/<int:note_id>/delete")
@login_required
def delete_group_travel_note(group_id, note_id):
    _traveler_only()
    group = _member_group(group_id)
    note = GroupTravelNote.query.filter_by(id=note_id, group_id=group.id).first_or_404()
    if note.created_by_id != current_user.id and group.owner_id != current_user.id:
        abort(403)
    db.session.delete(note)
    db.session.commit()
    flash("旅程・予約メモを削除しました。", "success")
    return redirect(url_for("group_detail", group_id=group.id, _anchor="notes"))

@groups_bp.post("/groups/<int:group_id>/album")
@login_required
def upload_group_album_photos(group_id):
    group = _member_group(group_id)
    photos = [photo for photo in request.files.getlist("photos") if photo and photo.filename]
    caption = request.form.get("caption", "").strip()
    if not photos or len(photos) > ALBUM_MAX_FILES_PER_UPLOAD:
        flash("写真を1〜5枚選択してください。", "error")
        return redirect(url_for("group_detail", group_id=group.id, _anchor="album"))
    if len(caption) > 300:
        flash("コメントは300文字以内で入力してください。", "error")
        return redirect(url_for("group_detail", group_id=group.id, _anchor="album"))

    prepared = []
    for photo in photos:
        extension = Path(photo.filename).suffix.lower()
        image_type = ALBUM_IMAGE_TYPES.get(extension)
        if not image_type:
            flash("JPG、PNG、GIF、WebP形式の写真を選んでください。", "error")
            return redirect(url_for("group_detail", group_id=group.id, _anchor="album"))
        photo.stream.seek(0, os.SEEK_END)
        size = photo.stream.tell()
        photo.stream.seek(0)
        header = photo.stream.read(12)
        photo.stream.seek(0)
        valid_signature = (
            (image_type == "jpeg" and header.startswith(b"\xff\xd8\xff"))
            or (image_type == "png" and header.startswith(b"\x89PNG\r\n\x1a\n"))
            or (image_type == "gif" and header[:6] in (b"GIF87a", b"GIF89a"))
            or (image_type == "webp" and header[:4] == b"RIFF" and header[8:12] == b"WEBP")
        )
        if size == 0 or size > ALBUM_MAX_IMAGE_BYTES or not valid_signature:
            flash("写真の形式を確認してください。1枚あたり5MBまでの画像を選んでください。", "error")
            return redirect(url_for("group_detail", group_id=group.id, _anchor="album"))
        prepared.append((photo, extension))

    album_dir = Path(current_app.instance_path) / "group_album" / str(group.id)
    album_dir.mkdir(parents=True, exist_ok=True)
    for photo, extension in prepared:
        filename = f"{secrets.token_hex(16)}{extension}"
        photo.save(album_dir / filename)
        db.session.add(GroupAlbumPhoto(
            group_id=group.id, user_id=current_user.id, filename=filename, caption=caption
        ))
    db.session.commit()
    flash(f"写真を{len(prepared)}枚アルバムに追加しました。", "success")
    return redirect(url_for("group_detail", group_id=group.id, _anchor="album"))

@groups_bp.get("/groups/<int:group_id>/album/<int:photo_id>")
@login_required
def group_album_photo(group_id, photo_id):
    group = _member_group(group_id)
    photo = GroupAlbumPhoto.query.filter_by(id=photo_id, group_id=group.id).first_or_404()
    response = send_from_directory(
        Path(current_app.instance_path) / "group_album" / str(group.id),
        photo.filename,
        as_attachment=False,
        conditional=True,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, max-age=3600"
    return response

@groups_bp.post("/groups/<int:group_id>/album/<int:photo_id>/delete")
@login_required
def delete_group_album_photo(group_id, photo_id):
    group = _member_group(group_id)
    photo = GroupAlbumPhoto.query.filter_by(id=photo_id, group_id=group.id).first_or_404()
    if photo.user_id != current_user.id and group.owner_id != current_user.id:
        abort(403)
    photo_path = Path(current_app.instance_path) / "group_album" / str(group.id) / photo.filename
    db.session.delete(photo)
    db.session.commit()
    photo_path.unlink(missing_ok=True)
    flash("写真をアルバムから削除しました。", "success")
    return redirect(url_for("group_detail", group_id=group.id, _anchor="album"))

@groups_bp.post("/groups/<int:group_id>/messages/read")
@login_required
def mark_group_messages_read(group_id):
    _traveler_only()
    group = _member_group(group_id)
    data = request.get_json(silent=True)
    raw_ids = data.get("message_ids", []) if isinstance(data, dict) else []
    if not isinstance(raw_ids, list) or len(raw_ids) > 100:
        return jsonify(error="既読にするメッセージを確認してください。"), 400
    message_ids = {value for value in raw_ids if isinstance(value, int) and value > 0}
    if not message_ids:
        return jsonify(ok=True)
    messages = GroupMessage.query.filter(
        GroupMessage.group_id == group.id,
        GroupMessage.id.in_(message_ids),
        GroupMessage.user_id != current_user.id,
        GroupMessage.is_deleted.is_(False),
    ).all()
    existing_ids = {row[0] for row in db.session.query(GroupMessageRead.message_id).filter(
        GroupMessageRead.user_id == current_user.id,
        GroupMessageRead.message_id.in_([message.id for message in messages]),
    ).all()} if messages else set()
    newly_read_count = len(messages) - len(existing_ids)
    for message in messages:
        if message.id not in existing_ids:
            db.session.add(GroupMessageRead(message_id=message.id, user_id=current_user.id))
    db.session.commit()
    return jsonify(ok=True, newly_read_count=newly_read_count)

@groups_bp.route("/groups/<int:group_id>/messages", methods=["GET", "POST"])
@login_required
def group_messages(group_id):
    _traveler_only()
    group = _member_group(group_id)
    if request.method == "GET":
        after_id = request.args.get("after", default=0, type=int) or 0
        messages = GroupMessage.query.filter(
            GroupMessage.group_id == group.id,
            GroupMessage.id > max(0, after_id),
            GroupMessage.is_deleted.is_(False),
        ).order_by(GroupMessage.id.asc()).limit(50).all()
        own_messages = GroupMessage.query.filter_by(group_id=group.id, user_id=current_user.id).order_by(GroupMessage.id.desc()).limit(100).all()
        read_status = {str(message.id): len(message.read_receipts) for message in own_messages}
        recent_messages = GroupMessage.query.filter_by(group_id=group.id, is_deleted=False).order_by(GroupMessage.id.desc()).limit(100).all()
        reaction_status = {str(message.id): _serialize_message_reactions(message, current_user.id) for message in recent_messages}
        deleted_messages = GroupMessage.query.filter_by(
            group_id=group.id, is_deleted=True
        ).order_by(GroupMessage.id.desc()).all()
        return jsonify(messages=[_serialize_group_message(message, current_user.id) for message in messages],
                       recent_messages=[_serialize_group_message(message, current_user.id) for message in recent_messages],
                       deleted_messages=[_serialize_group_message(message, current_user.id) for message in deleted_messages],
                       read_status=read_status, reaction_status=reaction_status)

    data = request.get_json(silent=True)
    content = data.get("content", "").strip() if isinstance(data, dict) and isinstance(data.get("content"), str) else ""
    if not content or len(content) > 1000:
        return jsonify(error="メッセージを1〜1,000文字で入力してください。"), 400
    message = GroupMessage(group_id=group.id, user_id=current_user.id, content=content)
    db.session.add(message)
    db.session.commit()
    return jsonify(message=_serialize_group_message(message, current_user.id)), 201

@groups_bp.post("/groups/<int:group_id>/messages/<int:message_id>/unsend")
@login_required
def unsend_group_message(group_id, message_id):
    _traveler_only()
    group = _member_group(group_id)
    message = GroupMessage.query.filter_by(id=message_id, group_id=group.id).first_or_404()
    if message.user_id != current_user.id:
        abort(403)
    if message.is_deleted:
        return jsonify(error="このメッセージはすでに取り消されています。"), 409
    message.content = ""
    message.is_deleted = True
    GroupMessageReaction.query.filter_by(message_id=message.id).delete(synchronize_session=False)
    db.session.commit()
    return jsonify(message=_serialize_group_message(message, current_user.id))

@groups_bp.post("/groups/<int:group_id>/messages/<int:message_id>/edit")
@login_required
def edit_group_message(group_id, message_id):
    _traveler_only()
    group = _member_group(group_id)
    message = GroupMessage.query.filter_by(id=message_id, group_id=group.id).first_or_404()
    if message.user_id != current_user.id:
        abort(403)
    if message.is_deleted:
        return jsonify(error="取り消し済みのメッセージは編集できません。"), 409
    data = request.get_json(silent=True)
    content = data.get("content", "").strip() if isinstance(data, dict) and isinstance(data.get("content"), str) else ""
    if not content or len(content) > 1000:
        return jsonify(error="メッセージは1〜1,000文字で入力してください。"), 400
    message.content = content
    db.session.commit()
    return jsonify(message=_serialize_group_message(message, current_user.id))

@groups_bp.post("/groups/<int:group_id>/messages/<int:message_id>/reactions")
@login_required
def toggle_group_message_reaction(group_id, message_id):
    _traveler_only()
    group = _member_group(group_id)
    message = GroupMessage.query.filter_by(id=message_id, group_id=group.id).first_or_404()
    if message.user_id == current_user.id:
        return jsonify(error="自分のメッセージにはリアクションできません。"), 403
    if message.is_deleted:
        return jsonify(error="取り消し済みのメッセージにはリアクションできません。"), 400
    data = request.get_json(silent=True)
    emoji = data.get("emoji", "") if isinstance(data, dict) else ""
    if emoji not in REACTION_EMOJIS:
        return jsonify(error="リアクションを選択してください。"), 400
    reaction = GroupMessageReaction.query.filter_by(message_id=message.id, user_id=current_user.id).first()
    if reaction and reaction.emoji == emoji:
        db.session.delete(reaction)
    elif reaction:
        reaction.emoji = emoji
    else:
        db.session.add(GroupMessageReaction(message_id=message.id, user_id=current_user.id, emoji=emoji))
    db.session.commit()
    return jsonify(reaction_status=_serialize_message_reactions(message, current_user.id))

@groups_bp.post("/groups/<int:group_id>/expenses")
@login_required
def add_group_expense(group_id):
    _traveler_only()
    group = _member_group(group_id)
    title = request.form.get("title", "").strip()[:120]
    amount = request.form.get("amount", type=int)
    payer_id = request.form.get("paid_by_id", type=int)
    included_ids = sorted({int(value) for value in request.form.getlist("participants") if value.isdigit()})
    valid_ids = {member.user_id for member in group.members}
    spent_on_raw = request.form.get("spent_on", "").strip()
    try:
        spent_on = date.fromisoformat(spent_on_raw) if spent_on_raw else date.today()
    except ValueError:
        spent_on = None
    if not title or not amount or amount < 1 or amount > 100_000_000 or payer_id not in valid_ids or not included_ids or not set(included_ids).issubset(valid_ids) or not spent_on:
        flash("内容、金額、支払った人、精算対象のメンバーを確認してください。", "error")
        return redirect(url_for("group_detail", group_id=group.id, _anchor="expenses"))
    expense = GroupExpense(group_id=group.id, paid_by_id=payer_id, created_by_id=current_user.id,
                           title=title, amount=amount, spent_on=spent_on)
    db.session.add(expense)
    db.session.flush()
    ordered_expenses = GroupExpense.query.filter_by(group_id=group.id).order_by(GroupExpense.spent_on, GroupExpense.id).all()
    expense_index = next(index for index, item in enumerate(ordered_expenses) if item.id == expense.id)
    base, remainder = divmod(amount, len(included_ids))
    remainder_offset = expense_index % len(included_ids)
    for index, user_id in enumerate(included_ids):
        db.session.add(GroupExpenseShare(expense_id=expense.id, user_id=user_id,
                                         amount=base + (1 if (index - remainder_offset) % len(included_ids) < remainder else 0)))
    db.session.commit()
    flash("費用を記録し、割り勘を更新しました。", "success")
    return redirect(url_for("group_detail", group_id=group.id, _anchor="expenses"))

@groups_bp.post("/groups/<int:group_id>/expenses/<int:expense_id>/delete")
@login_required
def delete_group_expense(group_id, expense_id):
    _traveler_only()
    group = _member_group(group_id)
    expense = GroupExpense.query.filter_by(id=expense_id, group_id=group.id).first_or_404()
    if expense.created_by_id != current_user.id:
        abort(403)
    db.session.delete(expense)
    db.session.commit()
    flash("費用を削除しました。", "success")
    return redirect(url_for("group_detail", group_id=group.id, _anchor="expenses"))

@groups_bp.post("/groups/<int:group_id>/expenses/delete-selected")
@login_required
def delete_selected_group_expenses(group_id):
    _traveler_only()
    group = _member_group(group_id)
    expense_ids = {int(value) for value in request.form.getlist("expense_ids") if value.isdigit()}
    if not expense_ids:
        flash("削除する費用にチェックを入れてください。", "error")
        return redirect(url_for("group_detail", group_id=group.id, _anchor="expenses"))
    expenses = GroupExpense.query.filter(
        GroupExpense.group_id == group.id,
        GroupExpense.id.in_(expense_ids),
    ).all()
    if len(expenses) != len(expense_ids):
        abort(404)
    if any(expense.created_by_id != current_user.id for expense in expenses):
        abort(403)
    for expense in expenses:
        db.session.delete(expense)
    db.session.commit()
    flash(f"費用を{len(expenses)}件削除しました。", "success")
    return redirect(url_for("group_detail", group_id=group.id, _anchor="expenses"))

@groups_bp.post("/groups/<int:group_id>/budget")
@login_required
def update_group_budget(group_id):
    _traveler_only()
    group = _member_group(group_id)
    amount = request.form.get("amount", type=int)
    if amount is None or amount < 1 or amount > 100_000_000:
        flash("グループ予算は1円以上、1億円以下で入力してください。", "error")
        return redirect(url_for("group_detail", group_id=group.id, _anchor="expenses"))
    group_budget = GroupBudget.query.filter_by(group_id=group.id).first()
    if group_budget is None:
        group_budget = GroupBudget(group_id=group.id, amount=amount)
        db.session.add(group_budget)
    else:
        group_budget.amount = amount
    db.session.commit()
    flash("グループ予算を保存しました。", "success")
    return redirect(url_for("group_detail", group_id=group.id, _anchor="expenses"))

@groups_bp.post("/groups/<int:group_id>/plans/share")
@login_required
def share_group_plan(group_id):
    _traveler_only()
    group = _member_group(group_id)
    plan_id = request.form.get("plan_id", type=int)
    plan = TravelPlan.query.filter_by(id=plan_id, user_id=current_user.id).first()
    if not plan:
        abort(404)
    if plan.group_id and plan.group_id != group.id:
        flash("このプランはすでに別のグループで共有されています。", "error")
    else:
        plan.group_id = group.id
        db.session.commit()
        flash("旅行プランをグループに共有しました。", "success")
    return redirect(url_for("group_detail", group_id=group.id, _anchor="plans"))

@groups_bp.post("/groups/<int:group_id>/plans/<int:plan_id>/remove")
@login_required
def remove_group_plan(group_id, plan_id):
    _traveler_only()
    group = _member_group(group_id)
    plan = TravelPlan.query.filter_by(id=plan_id, user_id=current_user.id, group_id=group.id).first()
    if not plan:
        abort(404)
    plan.group_id = None
    db.session.commit()
    flash("プランの共有を解除しました。", "success")
    return redirect(url_for("group_detail", group_id=group.id, _anchor="plans"))

