"""旅ストーリー（旅行記フィード、いいね、コメント、プラン複製）のルーティング。"""

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

journeys_bp = Blueprint("journeys", __name__)

@journeys_bp.get("/journeys")
@login_required
def journey_feed():
    _traveler_only()
    tab = request.args.get("tab", "community")
    if tab not in {"community", "liked", "mine"}:
        tab = "community"
    if tab == "liked":
        query = (TravelStory.query.join(TravelStoryLike)
                 .filter(TravelStoryLike.user_id == current_user.id, TravelStory.is_public.is_(True)))
    elif tab == "mine":
        query = TravelStory.query.filter_by(user_id=current_user.id)
    else:
        query = TravelStory.query.filter_by(is_public=True)
    selected_destination = request.args.get("destination", "").strip()
    selected_days = request.args.get("days", "").strip()
    selected_keyword = request.args.get("q", "").strip()[:100]
    selected_max_budget = request.args.get("max_budget", "").strip()
    selected_sort = request.args.get("sort", "newest")
    query = query.join(TravelPlan, TravelStory.plan_id == TravelPlan.id).join(User, TravelStory.user_id == User.id)
    if selected_destination in PREFECTURES:
        query = query.filter(TravelPlan.destination == selected_destination)
    else:
        selected_destination = ""
    try:
        days_filter = int(selected_days)
        if not 1 <= days_filter <= 30:
            raise ValueError
        query = query.filter(TravelPlan.days == days_filter)
    except ValueError:
        selected_days = ""
    try:
        max_budget = int(selected_max_budget)
        if max_budget < 0:
            raise ValueError
        query = query.filter(TravelPlan.budget <= max_budget)
    except ValueError:
        selected_max_budget = ""
    if selected_keyword:
        pattern = f"%{selected_keyword}%"
        query = query.filter(or_(TravelPlan.title.ilike(pattern), TravelPlan.destination.ilike(pattern),
                                 TravelStory.introduction.ilike(pattern), User.username.ilike(pattern)))
    stories = query.order_by(TravelStory.created_at.desc()).all()
    if selected_sort == "likes":
        stories.sort(key=lambda story: (len(story.likes), story.created_at), reverse=True)
    else:
        selected_sort = "newest"
    if tab == "mine":
        comment_notifications = unread_journey_comment_notifications(current_user.id)
        unread_by_story = {item["story"].id: item["count"] for item in comment_notifications}
        for story in stories:
            story.unread_comment_count = unread_by_story.get(story.id, 0)
    liked_story_ids = {like.story_id for like in TravelStoryLike.query.filter_by(user_id=current_user.id).all()}
    return page("journeys", stories=stories, liked_story_ids=liked_story_ids, story_tab=tab,
                selected_destination=selected_destination, selected_days=selected_days,
                selected_keyword=selected_keyword, selected_max_budget=selected_max_budget, selected_sort=selected_sort)

@journeys_bp.get("/journeys/<int:story_id>")
@login_required
def journey_detail(story_id):
    _traveler_only()
    story = db.session.get(TravelStory, story_id)
    if not story or (not story.is_public and story.user_id != current_user.id):
        abort(404)
    if story.user_id != current_user.id:
        db.session.execute(
            TravelStory.__table__.update()
            .where(TravelStory.id == story.id)
            .values(view_count=TravelStory.view_count + 1)
        )
        db.session.commit()
        db.session.refresh(story)
    liked = TravelStoryLike.query.filter_by(story_id=story.id, user_id=current_user.id).first() is not None
    if story.user_id == current_user.id:
        story.comments_viewed_at = datetime.now(timezone.utc)
        db.session.commit()
    _record_view_history(current_user.id, "journey", story.id)
    return page("journey_detail", story=story, liked=liked)

@journeys_bp.get("/journeys/<int:story_id>/use")
@login_required
def use_journey_plan(story_id):
    _traveler_only()
    story = db.session.get(TravelStory, story_id)
    if not story or (not story.is_public and story.user_id != current_user.id):
        abort(404)
    return redirect(url_for("new_plan", from_story=story.id))

@journeys_bp.post("/journeys/<int:story_id>/comments")
@login_required
def add_journey_comment(story_id):
    _traveler_only()
    story = TravelStory.query.filter_by(id=story_id, is_public=True).first_or_404()
    content = request.form.get("content", "").strip()
    if not content or len(content) > 1200:
        flash("コメントは1〜1,200文字で入力してください。", "error")
    elif story.user_id == current_user.id:
        flash("自分の旅行記にはコメントできません。", "info")
    else:
        db.session.add(TravelStoryComment(story_id=story.id, user_id=current_user.id, content=content))
        db.session.commit()
        flash("コメントを投稿しました。", "success")
    return redirect(url_for("journey_detail", story_id=story.id) + "#journey-comments")

@journeys_bp.post("/journeys/<int:story_id>/comments/<int:comment_id>/reply")
@login_required
def reply_journey_comment(story_id, comment_id):
    _traveler_only()
    story = TravelStory.query.filter_by(id=story_id, is_public=True, user_id=current_user.id).first_or_404()
    parent = TravelStoryComment.query.filter_by(id=comment_id, story_id=story.id, parent_id=None).first_or_404()
    content = request.form.get("content", "").strip()
    if not content or len(content) > 1200:
        flash("返信は1〜1,200文字で入力してください。", "error")
    elif parent.user_id == current_user.id:
        flash("自分のコメントには返信できません。", "info")
    else:
        db.session.add(TravelStoryComment(story_id=story.id, parent_id=parent.id,
                                          user_id=current_user.id, content=content))
        story.comments_viewed_at = datetime.now(timezone.utc)
        db.session.commit()
        flash("返信しました。", "success")
    return redirect(url_for("journey_detail", story_id=story.id) + "#journey-comments")

@journeys_bp.post("/journeys/<int:story_id>/comments/<int:comment_id>/delete")
@login_required
def delete_journey_comment(story_id, comment_id):
    _traveler_only()
    comment = TravelStoryComment.query.filter_by(id=comment_id, story_id=story_id, user_id=current_user.id).first_or_404()
    db.session.delete(comment)
    db.session.commit()
    flash("コメントを削除しました。", "success")
    return redirect(url_for("journey_detail", story_id=story_id) + "#journey-comments")

@journeys_bp.post("/plans/<int:plan_id>/journey")
@login_required
def publish_journey(plan_id):
    _traveler_only()
    plan = _owned_plan(plan_id)
    introduction = request.form.get("introduction", "").strip()
    if len(introduction) > 1200:
        flash("旅行記の紹介文は1,200文字以内で入力してください。", "error")
        return redirect(url_for("plan_detail", plan_id=plan.id))
    story = TravelStory.query.filter_by(plan_id=plan.id, user_id=current_user.id).first()
    if story:
        story.introduction = introduction
        story.is_public = True
    else:
        story = TravelStory(plan_id=plan.id, user_id=current_user.id, introduction=introduction,
                            comments_viewed_at=datetime.now(timezone.utc))
        db.session.add(story)
    db.session.commit()
    flash("旅行記を公開しました。みんなの旅行記から見られます。", "success")
    return redirect(url_for("journey_detail", story_id=story.id))

@journeys_bp.post("/journeys/<int:story_id>/visibility")
@login_required
def toggle_journey_visibility(story_id):
    _traveler_only()
    story = TravelStory.query.filter_by(id=story_id, user_id=current_user.id).first_or_404()
    story.is_public = not story.is_public
    db.session.commit()
    flash("旅行記を公開しました。" if story.is_public else "旅行記を非公開にしました。", "success")
    return redirect(url_for("journey_detail", story_id=story.id))

@journeys_bp.post("/journeys/<int:story_id>/like")
@login_required
def toggle_journey_like(story_id):
    _traveler_only()
    story = TravelStory.query.filter_by(id=story_id, is_public=True).first_or_404()
    if story.user_id == current_user.id:
        flash("自分の旅行記にはいいねできません。", "info")
    else:
        like = TravelStoryLike.query.filter_by(story_id=story.id, user_id=current_user.id).first()
        if like:
            db.session.delete(like)
        else:
            db.session.add(TravelStoryLike(story_id=story.id, user_id=current_user.id))
        db.session.commit()
    referrer = request.referrer or ""
    if referrer and urlparse(referrer).netloc == request.host:
        return redirect(referrer)
    return redirect(url_for("journey_detail", story_id=story.id))

