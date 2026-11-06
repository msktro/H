"""Geoapify API連携（場所検索、周辺スポット、ルート検索）のルーティング。"""

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

geoapify_bp = Blueprint("geoapify", __name__)

@geoapify_bp.get("/api/geoapify/places")
@login_required
def geoapify_places():
    _traveler_only()
    if not current_app.config["GEOAPIFY_API_KEY"]:
        return jsonify(error="Geoapify APIキーが未設定です。.envにGEOAPIFY_API_KEYを設定してください。"), 503
    query = request.args.get("q", "").strip()[:120]
    if len(query) < 2:
        return jsonify(results=[])
    try:
        response = requests.get(
            "https://api.geoapify.com/v1/geocode/autocomplete",
            params={"text": query, "filter": "countrycode:jp", "lang": "ja", "limit": 6,
                    "format": "json", "apiKey": current_app.config["GEOAPIFY_API_KEY"]},
            timeout=12,
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        places = []
        for place in results:
            try:
                lat, lon = float(place["lat"]), float(place["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if 20 <= lat <= 46.5 and 122 <= lon <= 154:
                places.append({"name": (place.get("name") or place.get("address_line1") or place.get("formatted") or "場所")[:160],
                               "address": (place.get("formatted") or "")[:240], "lat": lat, "lon": lon})
        return jsonify(results=places)
    except (requests.RequestException, ValueError) as exc:
        current_app.logger.warning("Geoapify place lookup failed: %s", exc)
        return jsonify(error="場所を検索できませんでした。APIキーや通信状態を確認してください。"), 502

@geoapify_bp.get("/api/geoapify/nearby")
@login_required
def geoapify_nearby():
    _traveler_only()
    if not current_app.config["GEOAPIFY_API_KEY"]:
        return jsonify(error="Geoapify APIキーが未設定です。.envにGEOAPIFY_API_KEYを設定してください。"), 503
    try:
        lat, lon = float(request.args.get("lat", "")), float(request.args.get("lon", ""))
        if not (20 <= lat <= 46.5 and 122 <= lon <= 154):
            raise ValueError("out of Japan")
    except ValueError:
        return jsonify(error="地点の座標が正しくありません。"), 400
    try:
        response = requests.get(
            "https://api.geoapify.com/v2/places",
            params={"categories": "tourism,catering,accommodation",
                    "filter": f"circle:{lon:.6f},{lat:.6f},10000",
                    "bias": f"proximity:{lon:.6f},{lat:.6f}", "limit": 10,
                    "lang": "ja", "apiKey": current_app.config["GEOAPIFY_API_KEY"]},
            timeout=12,
        )
        response.raise_for_status()
        places = []
        for feature in response.json().get("features", []):
            props = feature.get("properties") or {}
            try:
                place_lat, place_lon = float(props["lat"]), float(props["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if props.get("name") and 20 <= place_lat <= 46.5 and 122 <= place_lon <= 154:
                places.append({"name": str(props["name"])[:160],
                               "address": str(props.get("formatted") or "")[:240],
                               "lat": place_lat, "lon": place_lon})
        return jsonify(results=places)
    except (requests.RequestException, ValueError) as exc:
        current_app.logger.warning("Geoapify nearby places failed: %s", exc)
        return jsonify(error="周辺の場所を取得できませんでした。APIキーや通信状態を確認してください。"), 502

@geoapify_bp.post("/api/geoapify/route")
@login_required
def geoapify_route():
    _traveler_only()
    if not current_app.config["GEOAPIFY_API_KEY"]:
        return jsonify(error="Geoapify APIキーが未設定です。.envにGEOAPIFY_API_KEYを設定してください。"), 503
    payload = request.get_json(silent=True) or {}
    waypoints = payload.get("waypoints")
    mode = payload.get("mode", "walk")
    allowed_modes = {"walk", "drive", "bicycle", "transit"}
    if mode not in allowed_modes or not isinstance(waypoints, list) or not 2 <= len(waypoints) <= 8:
        return jsonify(error="地点を2〜8か所選び、移動方法を指定してください。"), 400
    normalized = []
    try:
        for point in waypoints:
            lat, lon = float(point["lat"]), float(point["lon"])
            if not (20 <= lat <= 46.5 and 122 <= lon <= 154):
                raise ValueError("out of Japan")
            normalized.append(f"{lat:.6f},{lon:.6f}")
    except (KeyError, TypeError, ValueError):
        return jsonify(error="地点の座標が正しくありません。検索結果から選び直してください。"), 400
    try:
        response = requests.get(
            "https://api.geoapify.com/v1/routing",
            params={"waypoints": "|".join(normalized), "mode": mode, "lang": "ja",
                    "units": "metric", "apiKey": current_app.config["GEOAPIFY_API_KEY"]},
            timeout=25,
        )
        response.raise_for_status()
        route = response.json()
        feature = (route.get("features") or [None])[0]
        if not feature or not feature.get("geometry"):
            return jsonify(error="ルートが見つかりませんでした。地点や移動方法を変更してください。"), 422
        props = feature.get("properties") or {}
        return jsonify(geojson=route, distance=props.get("distance"), time=props.get("time"))
    except (requests.RequestException, ValueError) as exc:
        current_app.logger.warning("Geoapify route calculation failed: %s", exc)
        return jsonify(error="ルートを計算できませんでした。APIキー、利用上限、地点を確認してください。"), 502

