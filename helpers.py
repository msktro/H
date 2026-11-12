"""Tabidea アプリケーション共通のヘルパー関数。"""

import hashlib
import hmac
import os
import re
import secrets
import smtplib
import ssl
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

from flask import abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user
from sqlalchemy import and_, func, or_
from werkzeug.security import check_password_hash

from constants import (
    ALBUM_IMAGE_TYPES,
    AVATAR_MAX_IMAGE_BYTES,
    AVATARS,
    BUSINESS_MAX_IMAGE_BYTES,
    BUSINESS_MAX_PHOTOS,
    CATEGORIES,
    CHAT_STAMPS,
    PREFECTURE_PHOTOS,
    PREFECTURES,
    THEMES,
)
from extensions import db
from models import (
    BusinessListing,
    BusinessListingPhoto,
    FormRateLimitEvent,
    GroupMessage,
    GroupMessageRead,
    GroupMessageReaction,
    Review,
    TravelPlan,
    TravelStory,
    TravelStoryComment,
    TripGroup,
    TripGroupBan,
    TripGroupMember,
    TripGroupRejoinRequest,
    User,
    ViewHistory,
)

__all__ = [
    "_normalize_business_phone",
    "_published_business_candidates",
    "_append_review_popular_spots",
    "_email_fingerprint",
    "_allow_rate_limited_action",
    "_send_email",
    "_smtp_login_and_send",
    "_send_password_reset_link",
    "_send_password_changed_notice",
    "_send_contact_receipt",
    "_record_view_history",
    "_send_contact_notification",
    "_bounded_int",
    "_profile_is_configured",
    "_is_birthday_today",
    "_traveler_only",
    "_business_only",
    "_owned_plan",
    "_visible_plan",
    "_valid_note_datetime",
    "_member_group",
    "_serialize_message_reactions",
    "_serialize_group_message",
    "_calculate_settlements",
    "_owned_listing",
    "_prepare_business_photos",
    "_prepare_avatar_image",
    "_store_business_photos",
    "unread_group_message_counts",
    "pending_group_rejoin_counts",
    "unread_journey_comment_notifications",
    "photo_for_destination",
    "page",
    "complete_pending_group_invite",
]



def _normalize_business_phone(value):
    raw = (value or "").strip()
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("+"):
        normalized = "+" + digits
    elif digits.startswith("0") and len(digits) in (10, 11):
        normalized = "+81" + digits[1:]
    else:
        return ""
    return normalized if re.fullmatch(r"\+[1-9]\d{7,14}", normalized) else ""


def _published_business_candidates(destination, limit=12):
    """Return destination listings with reviewed, unrated, and lower-rated options."""
    destination_key = "".join(destination.lower().split())
    if not destination_key:
        return []

    listings = BusinessListing.query.filter_by(is_published=True).all()
    relevant = []
    for listing in listings:
        location_text = "".join(f"{listing.prefecture or ''} {listing.address or ''}".lower().split())
        if destination_key in location_text or location_text and location_text in destination_key:
            relevant.append(listing)

    listing_ids = [item.id for item in relevant]
    stats = db.session.query(
        Review.listing_id, func.avg(Review.rating), func.count(Review.id)
    ).filter(Review.listing_id.in_(listing_ids)).group_by(Review.listing_id).all()
    review_stats = {listing_id: (float(avg), int(count)) for listing_id, avg, count in stats}

    # Use a Bayesian-style score so a high rating with very few reviews does
    # not automatically outrank a consistently well-reviewed popular listing.
    reviewed = [item for item in relevant if review_stats.get(item.id, (0.0, 0))[1] > 0]
    overall_average = sum(
        review_stats[item.id][0] * review_stats[item.id][1] for item in reviewed
    ) / sum(review_stats[item.id][1] for item in reviewed) if reviewed else 0
    prior_weight = 5

    def popularity_score(item):
        average, count = review_stats[item.id]
        return (count / (count + prior_weight)) * average + (prior_weight / (count + prior_weight)) * overall_average

    high_rated = [item for item in reviewed if review_stats[item.id][0] >= 4.0]
    unrated = [item for item in relevant if review_stats.get(item.id, (0.0, 0))[1] == 0]
    lower_rated = [item for item in reviewed if review_stats[item.id][0] < 4.0]
    high_rated.sort(key=lambda item: (popularity_score(item), review_stats[item.id][1]), reverse=True)
    lower_rated.sort(key=lambda item: (popularity_score(item), review_stats[item.id][1]), reverse=True)

    # Reserve room for unrated food and lodging options so the AI has choices
    # beyond places that already have reviews.
    unrated.sort(key=lambda item: (
        0 if item.category == "宿泊" else 1 if item.category == "飲食" else 2,
        item.id,
    ))
    reserved_unrated = []
    for category in ("宿泊", "飲食"):
        candidate = next((item for item in unrated if item.category == category), None)
        if candidate:
            reserved_unrated.append(candidate)
    for item in unrated:
        if len(reserved_unrated) >= min(2, limit):
            break
        if item not in reserved_unrated:
            reserved_unrated.append(item)

    selected = high_rated[:max(0, limit - len(reserved_unrated))] + reserved_unrated[:limit]
    for pool in (high_rated, unrated, lower_rated):
        for item in pool:
            if len(selected) >= limit:
                break
            if item not in selected:
                selected.append(item)

    candidates = []
    for item in selected[:limit]:
        average, count = review_stats.get(item.id, (0.0, 0))
        candidates.append({
            "id": item.id,
            "name": item.name[:120],
            "category": item.category[:50],
            "prefecture": item.prefecture[:20],
            "address": (item.address or "")[:255],
            "price_range": (item.price_range or "")[:100],
            "description": (item.description or "")[:500],
            "average": round(average, 1) if count else None,
            "review_count": count,
        })
    return candidates


def _append_review_popular_spots(answer, business_candidates, limit=3):
    """Ensure high-rated and a few unrated business listings become map-ready spots."""
    if not business_candidates:
        return answer
    missing_popular = [
        item for item in business_candidates[:limit]
        if item["review_count"] > 0 and item["average"] is not None and item["average"] >= 4.0
        and f"[[TABIDEA_LISTING_ID:{item['id']}]]" not in answer
    ]
    unrated = [
        item for item in business_candidates
        if item["review_count"] == 0 and item["average"] is None
        and f"[[TABIDEA_LISTING_ID:{item['id']}]]" not in answer
    ]
    missing_unrated = []
    for category in ("宿泊", "飲食"):
        item = next((candidate for candidate in unrated if candidate["category"] == category), None)
        if item:
            missing_unrated.append(item)
    for item in unrated:
        if len(missing_unrated) >= 2:
            break
        if item not in missing_unrated:
            missing_unrated.append(item)

    if not missing_popular and not missing_unrated:
        return answer

    lines = []
    if missing_popular:
        lines.extend(["## 口コミで人気のおすすめスポット", "事業者登録情報から、口コミ評価の高い候補です。"])
        for item in missing_popular:
            lines.append(f"- {item['name']} [おすすめスポット] [[TABIDEA_LISTING_ID:{item['id']}]]")
            details = [f"住所：{item['address'] or item['prefecture']}", f"ジャンル：{item['category']}"]
            if item["price_range"]:
                details.append(f"料金目安：{item['price_range']}")
            details.append(f"口コミ評価：{item['average']:.1f}/5（{item['review_count']}件）")
            lines.append("  " + "｜".join(details))
            if item["description"]:
                lines.append(f"  {item['description']}")
    if missing_unrated:
        lines.extend(["## 口コミがまだない施設候補", "口コミ評価はありません。訪問前に公式情報をご確認ください。"])
        for item in missing_unrated:
            lines.append(f"- {item['name']} [おすすめスポット] [[TABIDEA_LISTING_ID:{item['id']}]]")
            details = [f"住所：{item['address'] or item['prefecture']}", f"ジャンル：{item['category']}", "口コミ：まだありません"]
            if item["price_range"]:
                details.append(f"料金目安：{item['price_range']}")
            lines.append("  " + "｜".join(details))
            if item["description"]:
                lines.append(f"  {item['description']}")
    return answer.rstrip() + "\n\n" + "\n".join(lines)


def _email_fingerprint(scope, value):
    """認証情報やIPアドレスを平文保存せず、送信制限用の照合値を作ります。"""
    secret = str(current_app.config["SECRET_KEY"]).encode("utf-8")
    message = f"{scope}\0{value}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _allow_rate_limited_action(scope, value, limit, window_seconds):
    """同じ対象への短時間の連続送信をDBで抑えます。"""
    now = datetime.now(timezone.utc)
    fingerprint = _email_fingerprint(scope, value)
    db.session.query(FormRateLimitEvent).filter(
        FormRateLimitEvent.scope == scope,
        FormRateLimitEvent.created_at < now - timedelta(days=2),
    ).delete(synchronize_session=False)
    cutoff = now - timedelta(seconds=window_seconds)
    recent_count = FormRateLimitEvent.query.filter(
        FormRateLimitEvent.scope == scope,
        FormRateLimitEvent.fingerprint == fingerprint,
        FormRateLimitEvent.created_at >= cutoff,
    ).count()
    if recent_count >= limit:
        db.session.commit()
        return False
    db.session.add(FormRateLimitEvent(scope=scope, fingerprint=fingerprint, created_at=now))
    db.session.commit()
    return True


def _send_email(message):
    """共通のSMTP設定でメールを送り、通信失敗は呼び出し元へ返します。"""
    mail_server = current_app.config["MAIL_SERVER"]
    sender = current_app.config["MAIL_DEFAULT_SENDER"] or current_app.config["MAIL_USERNAME"]
    if not mail_server or not sender:
        return False
    message["From"] = sender
    context = ssl.create_default_context()
    try:
        if current_app.config["MAIL_USE_SSL"]:
            with smtplib.SMTP_SSL(
                mail_server, current_app.config["MAIL_PORT"], timeout=15, context=context
            ) as smtp:
                _smtp_login_and_send(smtp, message)
        else:
            with smtplib.SMTP(mail_server, current_app.config["MAIL_PORT"], timeout=15) as smtp:
                if current_app.config["MAIL_USE_TLS"]:
                    smtp.starttls(context=context)
                _smtp_login_and_send(smtp, message)
        return True
    except (OSError, smtplib.SMTPException, ValueError):
        current_app.logger.exception("Email delivery failed.")
        return False


def _smtp_login_and_send(smtp, message):
    username = current_app.config["MAIL_USERNAME"]
    if username:
        smtp.login(username, current_app.config["MAIL_PASSWORD"])
    smtp.send_message(message)


def _send_password_reset_link(email, reset_url):
    message = EmailMessage()
    message["Subject"] = "Tabidea パスワード再設定"
    message["To"] = email
    message.set_content(
        "パスワード再設定の依頼を受け付けました。\n"
        "次のリンクを30分以内に開いて、新しいパスワードを設定してください。\n\n"
        f"{reset_url}\n\n"
        "心当たりがない場合、このメールは破棄してください。"
    )
    if _send_email(message):
        return True
    if current_app.config["PASSWORD_RESET_DEV_MODE"]:
        current_app.logger.warning("LOCAL DEVELOPMENT ONLY — password reset link: %s", reset_url)
    else:
        current_app.logger.error("Password reset email is unavailable; configure SMTP and PUBLIC_BASE_URL.")
    return False


def _send_password_changed_notice(email):
    message = EmailMessage()
    message["Subject"] = "Tabidea パスワード変更のお知らせ"
    message["To"] = email
    message.set_content(
        "Tabideaアカウントのパスワードが変更されました。\n"
        "心当たりがない場合は、アカウントを確認するため運営へお問い合わせください。"
    )
    return _send_email(message)


def _send_contact_receipt(inquiry):
    message = EmailMessage()
    message["Subject"] = f"Tabidea お問い合わせ受付（受付番号 {inquiry.id}）"
    message["To"] = inquiry.email
    message.set_content(
        f"{inquiry.name} 様\n\n"
        "お問い合わせを受け付けました。内容を確認のうえ、必要な場合はこのメールアドレスへ返信します。\n"
        f"受付番号: {inquiry.id}\n"
        f"種別: {inquiry.category}\n"
        f"件名: {inquiry.subject}\n\n"
        "このメールは送信専用です。追加の連絡はTabideaのお問い合わせフォームをご利用ください。"
    )
    return _send_email(message)


def _record_view_history(user_id, target_type, target_id):
    entry = ViewHistory.query.filter_by(
        user_id=user_id, target_type=target_type, target_id=target_id
    ).first()
    now = datetime.now(timezone.utc)
    if entry:
        entry.viewed_at = now
    else:
        db.session.add(ViewHistory(
            user_id=user_id, target_type=target_type, target_id=target_id, viewed_at=now
        ))
    db.session.commit()
    old_ids = [row[0] for row in db.session.query(ViewHistory.id)
               .filter_by(user_id=user_id).order_by(ViewHistory.viewed_at.desc())
               .offset(200).all()]
    if old_ids:
        ViewHistory.query.filter(ViewHistory.id.in_(old_ids)).delete(synchronize_session=False)
        db.session.commit()


def _send_contact_notification(inquiry):
    recipient = current_app.config["CONTACT_EMAIL"]
    if not recipient:
        return False
    message = EmailMessage()
    message["Subject"] = f"Tabideaお問い合わせ: {inquiry.subject}"
    message["To"] = recipient
    message["Reply-To"] = inquiry.email
    message.set_content(
        f"受付番号: {inquiry.id}\n"
        f"お問い合わせ種別: {inquiry.category}\n"
        f"お名前: {inquiry.name}\n"
        f"メールアドレス: {inquiry.email}\n"
        f"受信日時: {inquiry.created_at}\n\n"
        f"{inquiry.message}"
    )
    return _send_email(message)


def _bounded_int(value, low, high, default):
    try:
        return min(high, max(low, int(value)))
    except (ValueError, TypeError):
        return default


def _profile_is_configured(profile):
    """A travel profile must contain each preference used by plan generation."""
    return bool(
        profile
        and profile.themes
        and profile.travel_pace
        and profile.budget_per_trip is not None
        and profile.transportation
        and profile.food_preference
    )


def _is_birthday_today(profile):
    """Return true when a saved travel profile has a birthday today in Japan."""
    if not profile or not profile.birth_date:
        return False
    # astimezone() uses the OS-configured local timezone and works on Windows
    # without installing the IANA tzdata database.
    today = datetime.now().astimezone().date()
    return (profile.birth_date.month, profile.birth_date.day) == (today.month, today.day)


def _traveler_only():
    if current_user.user_type != "traveler":
        abort(403)


def _business_only():
    if current_user.user_type != "business":
        abort(403)


def _owned_plan(item_id):
    item = db.session.get(TravelPlan, item_id)
    if not item or item.user_id != current_user.id or current_user.user_type != "traveler":
        abort(404)
    return item


def _visible_plan(item_id):
    plan = db.session.get(TravelPlan, item_id)
    if not plan or current_user.user_type != "traveler":
        abort(404)
    if plan.user_id == current_user.id:
        return plan
    if plan.group_id and TripGroupMember.query.filter_by(group_id=plan.group_id, user_id=current_user.id).first():
        return plan
    abort(404)


def _valid_note_datetime(value):
    if not value:
        return True
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M")
        return True
    except ValueError:
        return False


def _member_group(group_id):
    group = db.session.get(TripGroup, group_id)
    if (
        current_user.user_type != "traveler"
        or not group
        or not TripGroupMember.query.filter_by(group_id=group.id, user_id=current_user.id).first()
    ):
        abort(404)
    return group


def _serialize_message_reactions(message, viewer_id):
    counts = {}
    mine = ""
    for reaction in message.reactions:
        counts[reaction.emoji] = counts.get(reaction.emoji, 0) + 1
        if reaction.user_id == viewer_id:
            mine = reaction.emoji
    return {"counts": counts, "mine": mine}


def _serialize_group_message(message, viewer_id):
    created_at = message.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    reactions = _serialize_message_reactions(message, viewer_id)
    return {
        "id": message.id,
        "user_id": message.user_id,
        "username": message.user.username,
        "avatar": message.user.avatar or "👤",
        "avatar_image_url": url_for("user_avatar", user_id=message.user.id, v=message.user.updated_at.timestamp() if message.user.updated_at else 0) if message.user.avatar_image else "",
        "read_count": len(message.read_receipts),
        "content": message.content,
        "is_deleted": message.is_deleted,
        "created_at": created_at.isoformat(),
        "is_stamp": message.content.strip() in CHAT_STAMPS,
        "reaction_counts": reactions["counts"],
        "my_reaction": reactions["mine"],
    }


def _calculate_settlements(members, expenses):
    """Return minimal transfers, rotating indivisible yen across expenses."""
    balances = {membership.user_id: 0 for membership in members}
    users = {membership.user_id: membership.user for membership in members}
    # Recompute shares from the selected participants so legacy expenses get
    # the same fair remainder rotation as newly added expenses.
    for expense_index, expense in enumerate(sorted(expenses, key=lambda item: (item.spent_on, item.id))):
        balances[expense.paid_by_id] = balances.get(expense.paid_by_id, 0) + expense.amount
        participant_ids = sorted({share.user_id for share in expense.shares})
        if not participant_ids:
            continue
        base, remainder = divmod(expense.amount, len(participant_ids))
        offset = expense_index % len(participant_ids)
        for index, user_id in enumerate(participant_ids):
            share_amount = base + (1 if (index - offset) % len(participant_ids) < remainder else 0)
            balances[user_id] = balances.get(user_id, 0) - share_amount
    missing_user_ids = set(balances) - set(users)
    if missing_user_ids:
        users.update({user.id: user for user in User.query.filter(User.id.in_(missing_user_ids)).all()})
    # 立替額と各自の負担額の差から、支払う人と受け取る人を分けます。
    debtors = [[user_id, -balance] for user_id, balance in balances.items() if balance < 0]
    creditors = [[user_id, balance] for user_id, balance in balances.items() if balance > 0]
    result = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        amount = min(debtors[i][1], creditors[j][1])
        result.append({"payer": users[debtors[i][0]], "receiver": users[creditors[j][0]], "amount": amount})
        debtors[i][1] -= amount
        creditors[j][1] -= amount
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return result


def _owned_listing(item_id):
    item = db.session.get(BusinessListing, item_id)
    if not item or item.user_id != current_user.id or current_user.user_type != "business":
        abort(404)
    return item


def _prepare_business_photos(files):
    photos = [photo for photo in files if photo and photo.filename]
    if len(photos) > BUSINESS_MAX_PHOTOS:
        raise ValueError(f"写真は一度に{BUSINESS_MAX_PHOTOS}枚まで選択できます。")

    prepared = []
    for photo in photos:
        extension = Path(photo.filename).suffix.lower()
        image_type = ALBUM_IMAGE_TYPES.get(extension)
        if not image_type:
            raise ValueError("JPG、PNG、GIF、WebP形式の写真を選んでください。")
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
        # 拡張子だけでなく画像データの先頭も調べ、別形式への偽装を防ぎます。
        if size == 0 or size > BUSINESS_MAX_IMAGE_BYTES or not valid_signature:
            raise ValueError("1枚5MBまでのJPG、PNG、GIF、WebP画像を選んでください。")
        prepared.append((photo, extension))
    return prepared


def _prepare_avatar_image(upload):
    extension = Path(upload.filename).suffix.lower()
    image_type = ALBUM_IMAGE_TYPES.get(extension)
    if not image_type:
        raise ValueError("JPG、PNG、GIF、WebP形式の画像を選んでください。")
    upload.stream.seek(0, os.SEEK_END)
    size = upload.stream.tell()
    upload.stream.seek(0)
    header = upload.stream.read(12)
    upload.stream.seek(0)
    valid_signature = (
        (image_type == "jpeg" and header.startswith(b"\xff\xd8\xff"))
        or (image_type == "png" and header.startswith(b"\x89PNG\r\n\x1a\n"))
        or (image_type == "gif" and header[:6] in (b"GIF87a", b"GIF89a"))
        or (image_type == "webp" and header[:4] == b"RIFF" and header[8:12] == b"WEBP")
    )
    if size == 0 or size > AVATAR_MAX_IMAGE_BYTES or not valid_signature:
        raise ValueError("5MBまでのJPG、PNG、GIF、WebP画像を選んでください。")
    return upload, extension


def _store_business_photos(listing, prepared):
    if not prepared:
        return
    photo_dir = Path(current_app.instance_path) / "business_photos" / str(listing.id)
    photo_dir.mkdir(parents=True, exist_ok=True)
    # 元のファイル名を使わずランダム名で保存し、同名衝突や名前由来の問題を避けます。
    for photo, extension in prepared:
        filename = f"{secrets.token_hex(16)}{extension}"
        photo.save(photo_dir / filename)
        db.session.add(BusinessListingPhoto(listing_id=listing.id, filename=filename))


def unread_group_message_counts(user_id):
    rows = (db.session.query(GroupMessage.group_id, func.count(GroupMessage.id))
            .join(TripGroupMember, TripGroupMember.group_id == GroupMessage.group_id)
            .outerjoin(GroupMessageRead, and_(
                GroupMessageRead.message_id == GroupMessage.id,
                GroupMessageRead.user_id == user_id,
            ))
            .filter(
                TripGroupMember.user_id == user_id,
                GroupMessage.user_id != user_id,
                GroupMessageRead.id.is_(None),
                GroupMessage.is_deleted.is_(False),
            )
            .group_by(GroupMessage.group_id).all())
    return {group_id: count for group_id, count in rows}


def pending_group_rejoin_counts(owner_id):
    """Return pending rejoin-request counts for groups owned by this user."""
    rows = (db.session.query(TripGroupRejoinRequest.group_id, func.count(TripGroupRejoinRequest.id))
            .join(TripGroup, TripGroup.id == TripGroupRejoinRequest.group_id)
            .filter(TripGroup.owner_id == owner_id, TripGroupRejoinRequest.status == "pending")
            .group_by(TripGroupRejoinRequest.group_id).all())
    return {group_id: count for group_id, count in rows}


def unread_journey_comment_notifications(user_id):
    rows = (db.session.query(TravelStoryComment, TravelStory, User.username)
            .join(TravelStory, TravelStory.id == TravelStoryComment.story_id)
            .join(User, User.id == TravelStoryComment.user_id)
            .filter(
                TravelStory.user_id == user_id,
                TravelStoryComment.user_id != user_id,
                or_(TravelStory.comments_viewed_at.is_(None),
                    TravelStoryComment.created_at > TravelStory.comments_viewed_at),
            )
            .order_by(TravelStoryComment.created_at.desc()).all())
    notifications_by_story = {}
    for comment, story, username in rows:
        item = notifications_by_story.setdefault(story.id, {
            "story": story,
            "count": 0,
            "username": username or "旅行者",
            "content": comment.content[:120],
            "created_at": comment.created_at,
        })
        item["count"] += 1
    return sorted(notifications_by_story.values(),
                  key=lambda item: item["created_at"], reverse=True)


def photo_for_destination(destination):
    destination = (destination or "").strip()
    for prefecture, photo in sorted(PREFECTURE_PHOTOS.items(), key=lambda item: len(item[0]), reverse=True):
        short_name = prefecture[:-1] if prefecture.endswith(("県", "府", "都")) else prefecture
        if prefecture in destination or (short_name and short_name in destination):
            return photo
    return None


def page(name, **kwargs):
    return render_template("page.html", page=name, themes=THEMES, prefectures=PREFECTURES, categories=CATEGORIES, avatars=AVATARS, chat_stamps=CHAT_STAMPS, prefecture_photos=PREFECTURE_PHOTOS, photo_for_destination=photo_for_destination, **kwargs)


def complete_pending_group_invite(user):
    code = session.pop("pending_group_invite", None)
    if not code:
        return None
    if user.user_type != "traveler":
        flash("グループへの参加には旅行者アカウントが必要です。", "error")
        return url_for("index")
    group = TripGroup.query.filter_by(invite_code=code).first()
    if not group:
        flash("招待コードが見つかりません。", "error")
        return url_for("groups")
    if TripGroupBan.query.filter_by(group_id=group.id, user_id=user.id).first():
        flash("このグループへの参加は作成者によって禁止されています。", "error")
        return url_for("groups")
    membership = TripGroupMember.query.filter_by(group_id=group.id, user_id=user.id).first()
    if not membership:
        db.session.add(TripGroupMember(group_id=group.id, user_id=user.id))
        db.session.commit()
        flash("QRコードからグループに参加しました。", "success")
    else:
        flash("すでにこのグループに参加しています。", "info")
    return url_for("group_detail", group_id=group.id)
