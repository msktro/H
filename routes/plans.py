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
        today_jst = datetime.now(timezone(timedelta(hours=9))).date()
        if start_date and start_date < today_jst:
            flash("出発日は今日以降の日付を選択してください。", "error")
            return page("new_plan", values=values, profile=profile, profile_ready=profile_ready)
        if not 1 <= days_count <= 30:
            flash("出発日と帰着日を選択してください。旅行期間は開始日から最大30日です。", "error")
            return page("new_plan", values=values, profile=profile, profile_ready=profile_ready)
        values["days"] = days_count
        values["start_date"] = start_date.isoformat()
        values["end_date"] = end_date.isoformat()
        values["people"] = _bounded_int(values["people"], 1, 30, 1)
        values["budget"] = _bounded_int(values["budget"], 0, 100000000, 0)
        destination_tokens = [part.strip() for part in re.split(r"[、,，/・]", values["destination"]) if part.strip()]
        if not destination_tokens:
            destination_tokens = ["未定"]
        invalid_destinations = [name for name in destination_tokens if name != "未定" and name not in PREFECTURES]
        if invalid_destinations or ("未定" in destination_tokens and len(destination_tokens) > 1):
            flash("行き先は一覧から都道府県を選択してください。", "error")
            return page("new_plan", values=values, profile=profile, profile_ready=profile_ready)
        selected_destinations = [name for name in destination_tokens if name != "未定"]
        if len(selected_destinations) > 8:
            flash("選べる都道府県は最大8県です。移動時間も含めて現実的なプランを作れる範囲で選んでください。", "error")
            return page("new_plan", values=values, profile=profile, profile_ready=profile_ready)
        values["destination"] = "、".join(selected_destinations) if selected_destinations else "未定"
        if len(values["destination"]) > 100:
            flash("選択した都道府県が多すぎます。数を減らしてください。", "error")
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
        business_candidates = _published_business_candidates(values["destination"], start_date=start_date, end_date=end_date)
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

@plans_bp.route("/plans/manual", methods=["GET", "POST"])
@login_required
def manual_plan():
    """AIを使わず、旅行記向けの旅行プランを自分で作成します。"""
    _traveler_only()
    draft = {"title": "", "destination": "", "start_date": "", "days": 1, "people": 1, "budget": "", "introduction": "", "day_titles": [], "stops": []}
    if request.method == "POST":
        draft.update({"title": request.form.get("title", "").strip(), "destination": request.form.get("destination", "").strip(), "start_date": request.form.get("start_date", "").strip(), "days": request.form.get("days", "1").strip(), "people": request.form.get("people", "1").strip(), "budget": request.form.get("budget", "").strip(), "introduction": request.form.get("introduction", "").strip(), "day_titles": request.form.getlist("day_title")})
        try:
            days, people, budget = int(draft["days"]), int(draft["people"]), int(draft["budget"])
            start_date = date.fromisoformat(draft["start_date"])
        except (TypeError, ValueError):
            days = people = budget = 0
            start_date = None
        stop_days = request.form.getlist("stop_day")
        stop_times = request.form.getlist("stop_time")
        stop_names = request.form.getlist("stop_name")
        stop_categories = request.form.getlist("stop_category")
        stop_descriptions = request.form.getlist("stop_description")
        lists = (stop_days, stop_times, stop_names, stop_categories, stop_descriptions)
        draft["stops"] = [{"day": stop_days[i], "time": stop_times[i], "name": stop_names[i], "category": stop_categories[i], "description": stop_descriptions[i]} for i in range(min(map(len, lists)))]
        def invalid(message):
            flash(message, "error")
            return page("manual_plan", manual_draft=draft)
        today_jst = datetime.now(timezone(timedelta(hours=9))).date()
        if start_date and start_date < today_jst:
            return invalid("出発日は今日以降の日付を選択してください。")
        if not draft["title"] or len(draft["title"]) > 100:
            return invalid("プラン名を1〜100文字で入力してください。")
        if not draft["destination"] or len(draft["destination"]) > 100:
            return invalid("行き先を1〜100文字で入力してください。")
        if not start_date or not 1 <= days <= 30 or len(draft["day_titles"]) != days:
            return invalid("出発日と、日数に合った日ごとの予定を確認してください。")
        if not 1 <= people <= 30 or not 0 <= budget <= 100000000:
            return invalid("人数は1〜30人、予算は0〜100,000,000円で入力してください。")
        if len(draft["introduction"]) > 1200 or len(set(map(len, lists))) != 1:
            return invalid("紹介文またはスポット情報を確認してください。")
        if any(not title.strip() or len(title.strip()) > 100 for title in draft["day_titles"]):
            return invalid("各日の見出しを1〜100文字で入力してください。")
        categories = {"観光・体験", "食事", "宿泊", "移動", "自由時間", "その他"}
        grouped = {day: [] for day in range(1, days + 1)}
        for item in draft["stops"]:
            try:
                day_number = int(item["day"])
            except (TypeError, ValueError):
                return invalid("スポットの日付を確認してください。")
            spot_time = item["time"].strip()
            if not 1 <= day_number <= days or not item["name"].strip() or len(item["name"].strip()) > 160:
                return invalid("各スポットの対象日と名前を確認してください。")
            if spot_time and not re.fullmatch(r"(?:[01]?\d|2[0-3]):[0-5]\d", spot_time):
                return invalid("スポットの時刻は例のように09:30で入力してください。")
            if item["category"] not in categories or len(item["description"]) > 1000:
                return invalid("スポットの種類または説明文を確認してください。")
            grouped[day_number].append({**item, "time": spot_time, "name": item["name"].strip(), "description": item["description"].strip()})
        if any(not grouped[day] for day in grouped):
            return invalid("各日にスポットを1件以上追加してください。")
        content = ["# 旅のしおり"]
        if draft["introduction"]:
            content.extend(["## 旅のハイライト", draft["introduction"]])
        for day_number in range(1, days + 1):
            content.append(f"## 第{day_number}日目｜{draft['day_titles'][day_number - 1].strip()}")
            periods = {"午前": [], "午後": [], "夕方": []}
            for item in grouped[day_number]:
                hour = int(item["time"].split(":", 1)[0]) if item["time"] else 13
                period = "午前" if hour < 12 else "夕方" if hour >= 17 else "午後"
                periods[period].append(item)
            for period in ("午前", "午後", "夕方"):
                if not periods[period]:
                    continue
                content.append(f"### {period}")
                for item in periods[period]:
                    prefix = f"{item['time']}｜" if item["time"] else ""
                    content.append(f"- {prefix}{item['name']}")
                    content.append(f"種類：{item['category']}")
                    if item["description"]:
                        content.extend(item["description"].splitlines())
        plan = TravelPlan(user_id=current_user.id, title=draft["title"], destination=draft["destination"], start_date=start_date, end_date=start_date + timedelta(days=days - 1), days=days, num_people=people, budget=budget, theme="自分で作成", preferences="手入力で作成した旅行プラン", ai_response="\n".join(content))
        db.session.add(plan)
        db.session.commit()
        flash("手作りの旅行プランを保存しました。旅行記として公開できます。", "success")
        return redirect(url_for("plan_detail", plan_id=plan.id))
    return page("manual_plan", manual_draft=draft)


@plans_bp.get("/plans/<int:plan_id>")
@login_required
def plan_detail(plan_id):
    plan = _visible_plan(plan_id)
    story = TravelStory.query.filter_by(plan_id=plan.id, user_id=current_user.id).first() if plan.user_id == current_user.id else None
    suggestions = _published_business_candidates(plan.destination, limit=30, start_date=plan.start_date, end_date=plan.end_date) if plan.user_id == current_user.id else []
    return page("plan_detail", plan=plan, story=story, is_plan_owner=plan.user_id == current_user.id, spot_suggestions=suggestions)

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
    # Group-shared plans use the plan owner's list as the group's shared checklist.
    list_owner_id = plan.user_id if plan.group_id else current_user.id
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "add_template":
            template_name = request.form.get("template", "")
            if template_name not in PACKING_TEMPLATES:
                flash("持ち物テンプレートを選択してください。", "error")
            else:
                added = 0
                for name, category in PACKING_TEMPLATES[template_name]:
                    exists = PackingItem.query.filter_by(plan_id=plan.id, user_id=list_owner_id, name=name).first()
                    if not exists:
                        db.session.add(PackingItem(plan_id=plan.id, user_id=list_owner_id, name=name, category=category))
                        added += 1
                db.session.commit()
                flash(f"テンプレート「{template_name}」から{added}件追加しました。", "success")
        elif action == "add_item":
            name = request.form.get("name", "").strip()
            category = request.form.get("category", "その他")
            if not name or len(name) > 100 or category not in PACKING_CATEGORIES:
                flash("持ち物名を1〜100文字で入力してください。", "error")
            elif PackingItem.query.filter_by(plan_id=plan.id, user_id=list_owner_id, name=name).first():
                flash("この持ち物はすでに登録されています。", "info")
            else:
                db.session.add(PackingItem(plan_id=plan.id, user_id=list_owner_id, name=name, category=category))
                db.session.commit()
                flash("持ち物を追加しました。", "success")
        elif action == "save_preset":
            preset_name = request.form.get("preset_name", "").strip()
            current_items = PackingItem.query.filter_by(plan_id=plan.id, user_id=list_owner_id).order_by(PackingItem.id).all()
            if not 1 <= len(preset_name) <= 60:
                flash("プリセット名を1〜60文字で入力してください。", "error")
            elif not current_items:
                flash("先に持ち物を追加してからプリセットを保存してください。", "error")
            elif len(current_items) > 200:
                flash("プリセットに保存できる持ち物は200件までです。", "error")
            elif PackingPreset.query.filter_by(user_id=current_user.id, name=preset_name).first():
                flash("同じ名前のプリセットがあります。別の名前にしてください。", "error")
            else:
                preset_items = [{"name": item.name, "category": item.category} for item in current_items]
                db.session.add(PackingPreset(user_id=current_user.id, name=preset_name,
                                             items_json=json.dumps(preset_items, ensure_ascii=False)))
                db.session.commit()
                flash(f"「{preset_name}」を自分の持ち物プリセットに保存しました。", "success")
        elif action == "add_preset":
            preset_id = request.form.get("preset_id", type=int)
            preset = PackingPreset.query.filter_by(id=preset_id, user_id=current_user.id).first() if preset_id else None
            if not preset:
                flash("プリセットが見つかりません。", "error")
            else:
                try:
                    preset_items = json.loads(preset.items_json)
                except (TypeError, ValueError):
                    preset_items = []
                added = 0
                for entry in preset_items[:200] if isinstance(preset_items, list) else []:
                    if not isinstance(entry, dict):
                        continue
                    name = str(entry.get("name", "")).strip()
                    category = entry.get("category", "その他")
                    if not name or len(name) > 100 or category not in PACKING_CATEGORIES:
                        continue
                    if PackingItem.query.filter_by(plan_id=plan.id, user_id=list_owner_id, name=name).first():
                        continue
                    db.session.add(PackingItem(plan_id=plan.id, user_id=list_owner_id, name=name, category=category))
                    added += 1
                db.session.commit()
                flash(f"「{preset.name}」から{added}件追加しました。重複する持ち物は追加していません。", "success")
        elif action == "delete_preset":
            preset_id = request.form.get("preset_id", type=int)
            preset = PackingPreset.query.filter_by(id=preset_id, user_id=current_user.id).first() if preset_id else None
            if not preset:
                flash("削除するプリセットが見つかりません。", "error")
            else:
                db.session.delete(preset)
                db.session.commit()
                flash(f"プリセット「{preset.name}」を削除しました。", "info")
        else:
            abort(400)
        return redirect(url_for("packing_list", plan_id=plan.id))
    items = PackingItem.query.filter_by(plan_id=plan.id, user_id=list_owner_id).order_by(PackingItem.id).all()
    checked_count = sum(item.is_checked for item in items)
    presets = PackingPreset.query.filter_by(user_id=current_user.id).order_by(PackingPreset.created_at.desc(), PackingPreset.id.desc()).all()
    preset_counts = {}
    for preset in presets:
        try:
            decoded = json.loads(preset.items_json)
            preset_counts[preset.id] = len(decoded) if isinstance(decoded, list) else 0
        except (TypeError, ValueError):
            preset_counts[preset.id] = 0
    return page("packing_list", plan=plan, items=items, packing_categories=PACKING_CATEGORIES,
                packing_templates=PACKING_TEMPLATES.keys(), checked_count=checked_count,
                custom_packing_presets=presets, packing_preset_counts=preset_counts,
                shared_list=bool(plan.group_id))

@plans_bp.post("/plans/<int:plan_id>/packing/<int:item_id>/toggle")
@login_required
def toggle_packing_item(plan_id, item_id):
    _traveler_only()
    plan = _visible_plan(plan_id)
    owner_id = plan.user_id if plan.group_id else current_user.id
    item = PackingItem.query.filter_by(id=item_id, plan_id=plan.id, user_id=owner_id).first_or_404()
    item.is_checked = not item.is_checked
    db.session.commit()
    return redirect(url_for("packing_list", plan_id=plan.id))

@plans_bp.post("/plans/<int:plan_id>/packing/<int:item_id>/delete")
@login_required
def delete_packing_item(plan_id, item_id):
    _traveler_only()
    plan = _visible_plan(plan_id)
    owner_id = plan.user_id if plan.group_id else current_user.id
    item = PackingItem.query.filter_by(id=item_id, plan_id=plan.id, user_id=owner_id).first_or_404()
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
        answer = generate_text(system, prompt, temperature=0.25)
        plan.ai_response = answer
        db.session.commit()
        flash("希望を反映してプランを更新しました。", "success")
    except AIServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("plan_detail", plan_id=plan.id))

@plans_bp.post("/plans/<int:plan_id>/spot/<path:old_name>/edit")
@login_required
def edit_plan_spot(plan_id, old_name):
    plan = _owned_plan(plan_id)
    old_name = old_name.strip()[:160]
    new_name = request.form.get("new_name", "").strip()[:160]
    new_listing_id = request.form.get("new_listing_id", "").strip()
    old_description = request.form.get("old_description", "").strip()[:3000]
    new_description = request.form.get("new_description", "").strip()[:3000]
    if not old_name or not new_name or (old_description and not new_description):
        flash("スポット名と説明を入力してください。", "error")
        return redirect(url_for("plan_detail", plan_id=plan.id))
    selected_listing = None
    if new_listing_id.isdigit():
        selected_listing = BusinessListing.query.filter_by(id=int(new_listing_id), is_published=True).first()
        if not selected_listing or selected_listing.name != new_name:
            flash("選択した掲載スポットを確認できませんでした。もう一度候補を選んでください。", "error")
            return redirect(url_for("plan_detail", plan_id=plan.id))
    lines = plan.ai_response.splitlines()
    for index, line in enumerate(lines):
        if old_name in line:
            line = line.replace(old_name, new_name, 1)
            line = re.sub(r"\s*\[おすすめスポット\]\s*\[\[TABIDEA_LISTING_ID:\d+\]\]", "", line)
            if selected_listing:
                line = f"{line.rstrip()} [おすすめスポット] [[TABIDEA_LISTING_ID:{selected_listing.id}]]"
            lines[index] = line
            if old_description and new_description:
                old_detail_lines = [part.strip() for part in old_description.splitlines() if part.strip()]
                new_detail_lines = new_description.splitlines()
                detail_indices = []
                for detail_index in range(index + 1, len(lines)):
                    detail = lines[detail_index]
                    if detail.lstrip().startswith(("- ", "* ", "##", "#")):
                        break
                    if detail.strip():
                        detail_indices.append(detail_index)
                        if len(detail_indices) >= len(old_detail_lines):
                            break
                if detail_indices and old_detail_lines and old_detail_lines[0] in lines[detail_indices[0]]:
                    start = detail_indices[0]
                    end = detail_indices[-1] + 1
                    lines[start:end] = new_detail_lines
            plan.ai_response = "\n".join(lines)
            db.session.commit()
            flash("スポット名と説明を更新しました。", "success")
            break
    else:
        flash("対象のスポットが見つかりませんでした。", "error")
    return redirect(url_for("plan_detail", plan_id=plan.id))

@plans_bp.post("/plans/<int:plan_id>/delete")
@login_required
def delete_plan(plan_id):
    db.session.delete(_owned_plan(plan_id))
    db.session.commit()
    flash("プランを削除しました。", "info")
    return redirect(url_for("plans"))

