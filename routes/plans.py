"""旅行プラン作成・AI生成・持ち物リスト・翻訳のルーティング。"""

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

plans_bp = Blueprint("plans", __name__)

@plans_bp.get("/plans")
@login_required
def plans():
    _traveler_only()
    items = TravelPlan.query.filter_by(user_id=current_user.id).order_by(TravelPlan.updated_at.desc()).all()
    return page("plans", plans=items)

@plans_bp.get("/packing")
@login_required
def packing_plan_picker():
    _traveler_only()
    group_ids = [m.group_id for m in TripGroupMember.query.filter_by(user_id=current_user.id).all()]
    query = TravelPlan.query.filter(TravelPlan.user_id == current_user.id)
    if group_ids:
        query = TravelPlan.query.filter(
            or_(TravelPlan.user_id == current_user.id, TravelPlan.group_id.in_(group_ids))
        )
    items = query.order_by(TravelPlan.updated_at.desc()).all()
    return page("packing_picker", plans=items)

@plans_bp.route("/plans/new", methods=["GET", "POST"])
@login_required
def new_plan():
    _traveler_only()
    profile = current_user.profile
    profile_ready = _profile_is_configured(profile)
    default_budget = (profile.budget_per_trip or "") if profile and profile.budget_per_trip is not None else ""
    values = {"destination": "未定", "start_date": "", "end_date": "", "days": 1, "people": 2, "budget": default_budget, "theme": "", "preferences": "", "companions": "", "use_profile": profile_ready, "manual_themes": [], "manual_pace": "", "manual_transport": "", "manual_food": "", "manual_age_group": "", "inspiration_story_id": "", "inspiration_story_title": ""}
    inspiration_story = None
    if request.method == "GET":
        requested_destination = request.args.get("destination", "").strip()
        if requested_destination in PREFECTURES:
            values["destination"] = requested_destination
    if request.method == "GET" and request.args.get("from_story", "").isdigit():
        candidate = db.session.get(TravelStory, int(request.args["from_story"]))
        if candidate and (candidate.is_public or candidate.user_id == current_user.id):
            inspiration_story = candidate
            source_plan = candidate.plan
            values.update({
                "destination": source_plan.destination,
                "start_date": source_plan.start_date.isoformat() if source_plan.start_date else "",
                "end_date": source_plan.end_date.isoformat() if source_plan.end_date else "",
                "days": source_plan.days,
                "people": source_plan.num_people, "budget": source_plan.budget,
                "theme": source_plan.theme or "",
                "manual_themes": [theme.strip() for theme in re.split(r"[、,，]", source_plan.theme or "") if theme.strip() in THEMES],
                "preferences": "この旅行記の行程やスポットを参考にしながら、自分の条件に合わせて新しいプランを作ってください。",
                "inspiration_story_id": str(candidate.id), "inspiration_story_title": source_plan.title,
            })
    if request.method == "POST":
        values.update({k: request.form.get(k, "").strip() for k in ("destination", "start_date", "end_date", "people", "budget", "theme", "preferences", "companions", "manual_pace", "manual_transport", "manual_food", "manual_age_group")})
        # 参考にする旅行記は、公開中か自分の投稿だけを読み込みます。
        raw_story_id = request.form.get("inspiration_story_id", "").strip()
        if raw_story_id.isdigit():
            candidate = db.session.get(TravelStory, int(raw_story_id))
            if candidate and (candidate.is_public or candidate.user_id == current_user.id):
                inspiration_story = candidate
                values["inspiration_story_id"] = str(candidate.id)
                values["inspiration_story_title"] = candidate.plan.title
        values["use_profile"] = request.form.get("use_profile") == "on"
        values["manual_themes"] = [theme for theme in request.form.getlist("manual_themes") if theme in THEMES]
        budget_was_provided = bool(values["budget"].strip())
        try:
            start_date = date.fromisoformat(values["start_date"])
            end_date = date.fromisoformat(values["end_date"])
            days_count = (end_date - start_date).days + 1
        except (TypeError, ValueError):
            start_date = end_date = None
            days_count = 0
        if not 1 <= days_count <= 30:
            flash("出発日と帰着日を選択してください。旅行期間は1〜30日で指定できます。", "error")
            return page("new_plan", values=values, profile=profile, profile_ready=profile_ready)
        values["days"] = days_count
        values["start_date"] = start_date.isoformat()
        values["end_date"] = end_date.isoformat()
        values["people"] = _bounded_int(values["people"], 1, 30, 1)
        values["budget"] = _bounded_int(values["budget"], 0, 100000000, 0)
        if not values["destination"]:
            flash("行き先を入力してください。", "error")
            return page("new_plan", values=values, profile=profile, profile_ready=profile_ready)
        manual_preferences = None
        if values["use_profile"] and not profile_ready:
            flash("プロフィールを参照するには、旅行プロフィールの必須項目を設定してください。チェックを外すと今回の好みを入力できます。", "error")
            return page("new_plan", values=values, profile=profile, profile_ready=profile_ready)
        if not values["use_profile"]:
            allowed_paces = {"ゆっくり過ごしたい", "標準的に回りたい", "できるだけ多く回りたい"}
            allowed_transport = {"公共交通機関", "徒歩中心", "レンタカー", "自家用車", "こだわらない"}
            allowed_food = {"ご当地グルメを楽しみたい", "カフェ・スイーツが好き", "食事は手短にしたい", "特にこだわらない"}
            allowed_age = {"10代以下", "20代", "30代", "40代", "50代", "60代以上", "子ども連れ", "年代を指定しない"}
            valid = (
                bool(values["manual_themes"])
                and values["manual_pace"] in allowed_paces
                and values["manual_transport"] in allowed_transport
                and values["manual_food"] in allowed_food
                and values["manual_age_group"] in allowed_age
                and budget_was_provided
                and bool(values["preferences"])
            )
            if not valid:
                flash("プロフィールを使わない場合は、今回の旅のテーマ・ペース・予算・移動手段・食事・年代・希望をすべて入力してください。", "error")
                return page("new_plan", values=values, profile=profile, profile_ready=profile_ready)
            values["theme"] = "、".join(values["manual_themes"])
            manual_preferences = {
                "themes": values["manual_themes"], "pace": values["manual_pace"],
                "budget": values["budget"], "transport": values["manual_transport"],
                "food": values["manual_food"], "age_group": values["manual_age_group"],
            }
        prompt_values = dict(values)
        if values["companions"]:
            prompt_values["preferences"] = f"{values['preferences']}\n年代・同行者など: {values['companions']}".strip()
        if inspiration_story:
            prompt_values["inspiration"] = inspiration_story.plan.ai_response[:5000]
        # 行き先にある公開事業者情報を集め、AIへの依頼文に添えます。
        business_candidates = _published_business_candidates(values["destination"])
        system, prompt = plan_prompts(prompt_values, current_user.profile if values["use_profile"] else None, business_candidates, manual_preferences)
        # 外部AIの失敗は利用者向けメッセージに変換し、入力画面へ戻します。
        try:
            answer = generate_text(system, prompt)
        except AIServiceError as exc:
            flash(str(exc), "error")
            return page("new_plan", values=values, profile=profile, profile_ready=profile_ready), 502
        answer = _append_review_popular_spots(answer, business_candidates)
        plan = TravelPlan(
            user_id=current_user.id, title=f"{values['destination']}の旅行プラン",
            destination=values["destination"][:100], start_date=start_date, end_date=end_date, days=values["days"],
            num_people=values["people"], budget=values["budget"] or 0,
            theme=values["theme"][:200], preferences=prompt_values["preferences"][:4000], ai_response=answer,
        )
        # AIの回答を旅行プランとして保存し、詳細画面へ移動します。
        db.session.add(plan)
        db.session.commit()
        flash("AIプランを生成して保存しました。", "success")
        return redirect(url_for("plan_detail", plan_id=plan.id))
    return page("new_plan", values=values, profile=profile, profile_ready=profile_ready)

@plans_bp.get("/plans/<int:plan_id>")
@login_required
def plan_detail(plan_id):
    plan = _visible_plan(plan_id)
    story = TravelStory.query.filter_by(plan_id=plan.id, user_id=current_user.id).first() if plan.user_id == current_user.id else None
    return page("plan_detail", plan=plan, story=story, is_plan_owner=plan.user_id == current_user.id)

@plans_bp.post("/plans/<int:plan_id>/rename")
@login_required
def rename_plan(plan_id):
    _traveler_only()
    plan = _owned_plan(plan_id)
    title = request.form.get("title", "").strip()
    if not title or len(title) > 100:
        flash("プラン名は1〜100文字で入力してください。", "error")
        return redirect(url_for("plan_detail", plan_id=plan.id))
    plan.title = title
    db.session.commit()
    flash("プラン名を更新しました。", "success")
    return redirect(url_for("plan_detail", plan_id=plan.id))

@plans_bp.route("/plans/<int:plan_id>/packing", methods=["GET", "POST"])
@login_required
def packing_list(plan_id):
    _traveler_only()
    plan = _visible_plan(plan_id)
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "add_template":
            template_name = request.form.get("template", "")
            if template_name not in PACKING_TEMPLATES:
                flash("持ち物テンプレートを選択してください。", "error")
            else:
                added = 0
                for name, category in PACKING_TEMPLATES[template_name]:
                    exists = PackingItem.query.filter_by(plan_id=plan.id, user_id=current_user.id, name=name).first()
                    if not exists:
                        db.session.add(PackingItem(plan_id=plan.id, user_id=current_user.id, name=name, category=category))
                        added += 1
                db.session.commit()
                flash(f"テンプレート「{template_name}」から{added}件追加しました。", "success")
        elif action == "add_item":
            name = request.form.get("name", "").strip()
            category = request.form.get("category", "その他")
            if not name or len(name) > 100 or category not in PACKING_CATEGORIES:
                flash("持ち物名を1〜100文字で入力してください。", "error")
            elif PackingItem.query.filter_by(plan_id=plan.id, user_id=current_user.id, name=name).first():
                flash("この持ち物はすでに登録されています。", "info")
            else:
                db.session.add(PackingItem(plan_id=plan.id, user_id=current_user.id, name=name, category=category))
                db.session.commit()
                flash("持ち物を追加しました。", "success")
        else:
            abort(400)
        return redirect(url_for("packing_list", plan_id=plan.id))
    items = PackingItem.query.filter_by(plan_id=plan.id, user_id=current_user.id).order_by(PackingItem.id).all()
    checked_count = sum(item.is_checked for item in items)
    return page("packing_list", plan=plan, items=items, packing_categories=PACKING_CATEGORIES,
                packing_templates=PACKING_TEMPLATES.keys(), checked_count=checked_count)

@plans_bp.post("/plans/<int:plan_id>/packing/<int:item_id>/toggle")
@login_required
def toggle_packing_item(plan_id, item_id):
    _traveler_only()
    plan = _visible_plan(plan_id)
    item = PackingItem.query.filter_by(id=item_id, plan_id=plan.id, user_id=current_user.id).first_or_404()
    item.is_checked = not item.is_checked
    db.session.commit()
    return redirect(url_for("packing_list", plan_id=plan.id))

@plans_bp.post("/plans/<int:plan_id>/packing/<int:item_id>/delete")
@login_required
def delete_packing_item(plan_id, item_id):
    _traveler_only()
    plan = _visible_plan(plan_id)
    item = PackingItem.query.filter_by(id=item_id, plan_id=plan.id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("持ち物を削除しました。", "info")
    return redirect(url_for("packing_list", plan_id=plan.id))

@plans_bp.get("/translate")
@login_required
# 翻訳、口コミ、お気に入り
def translate_page():
    _traveler_only()
    group_ids = [m.group_id for m in TripGroupMember.query.filter_by(user_id=current_user.id).all()]
    plans = TravelPlan.query.filter(
        or_(TravelPlan.user_id == current_user.id, TravelPlan.group_id.in_(group_ids))
    ).order_by(TravelPlan.updated_at.desc()).all()
    requested_id = request.args.get("plan_id", "").strip()
    selected_plan = next((item for item in plans if str(item.id) == requested_id), None)
    if not selected_plan and plans and not requested_id:
        selected_plan = plans[0]
    return page(
        "translate", plans=plans, selected_plan=selected_plan,
    )

@plans_bp.post("/api/plans/<int:plan_id>/translate")
@login_required
def translate_plan_api(plan_id):
    plan = _visible_plan(plan_id)
    payload = request.get_json(silent=True) or {}
    locale = payload.get("locale", "")
    languages = {
        "en": "英語", "ko": "韓国語", "zh-CN": "簡体字中国語",
        "zh-TW": "繁体字中国語", "th": "タイ語",
    }
    if locale not in languages:
        return jsonify(error="翻訳先の言語を選択してください。"), 400
    system, prompt = translation_prompts(plan.ai_response[:16000], languages[locale])
    try:
        translated = generate_text(system, prompt, temperature=0.2)
    except AIServiceError as exc:
        return jsonify(error=str(exc)), 502
    return jsonify(text=translated)

@plans_bp.post("/plans/<int:plan_id>/change")
@login_required
def change_plan(plan_id):
    plan = _owned_plan(plan_id)
    instruction = request.form.get("instruction", "").strip()[:2000]
    if not instruction:
        flash("変更したい内容を入力してください。", "error")
        return redirect(url_for("plan_detail", plan_id=plan.id))
    business_candidates = _published_business_candidates(plan.destination)
    system, prompt = change_prompts(plan, instruction, business_candidates)
    try:
        answer = generate_text(system, prompt)
        plan.ai_response = _append_review_popular_spots(answer, business_candidates)
        db.session.commit()
        flash("希望を反映してプランを更新しました。", "success")
    except AIServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("plan_detail", plan_id=plan.id))

@plans_bp.post("/plans/<int:plan_id>/delete")
@login_required
def delete_plan(plan_id):
    db.session.delete(_owned_plan(plan_id))
    db.session.commit()
    flash("プランを削除しました。", "info")
    return redirect(url_for("plans"))

