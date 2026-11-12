"""Populate 188 local demo business accounts with balanced Geoapify POIs.

Names/addresses/categories are returned by Geoapify Places API. Prices and
opening hours are intentionally approximate demo values and explicitly marked
as unverified. The demo accounts do not represent or belong to these businesses.
"""
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import random
import re
import secrets
import string
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from app import app
from extensions import db
from models import BusinessDetail, BusinessListing, User
from werkzeug.security import generate_password_hash

OUT = ROOT / "business_demo_accounts_11-110.csv"
EXPANDED_OUT = ROOT / "business_demo_accounts_11-188.csv"
PREFECTURES = [
    ("北海道",141.35,43.06),("青森県",140.74,40.82),("岩手県",141.15,39.70),("宮城県",140.87,38.27),
    ("秋田県",140.10,39.72),("山形県",140.36,38.24),("福島県",140.47,37.75),("茨城県",140.45,36.34),
    ("栃木県",139.88,36.57),("群馬県",139.06,36.39),("埼玉県",139.65,35.86),("千葉県",140.12,35.60),
    ("東京都",139.69,35.68),("神奈川県",139.64,35.45),("新潟県",139.02,37.90),("富山県",137.21,36.70),
    ("石川県",136.63,36.59),("福井県",136.22,36.07),("山梨県",138.57,35.66),("長野県",138.18,36.65),
    ("岐阜県",136.76,35.42),("静岡県",138.38,34.98),("愛知県",136.91,35.18),("三重県",136.51,34.73),
    ("滋賀県",135.87,35.00),("京都府",135.76,35.02),("大阪府",135.52,34.69),("兵庫県",135.18,34.69),
    ("奈良県",135.83,34.69),("和歌山県",135.17,34.23),("鳥取県",134.24,35.50),("島根県",132.77,35.47),
    ("岡山県",133.93,34.66),("広島県",132.46,34.40),("山口県",131.47,34.19),("徳島県",134.56,34.07),
    ("香川県",134.04,34.34),("愛媛県",132.77,33.84),("高知県",133.53,33.56),("福岡県",130.42,33.59),
    ("佐賀県",130.30,33.25),("長崎県",129.87,32.75),("熊本県",130.71,32.79),("大分県",131.61,33.24),
    ("宮崎県",131.42,31.91),("鹿児島県",130.56,31.60),("沖縄県",127.68,26.21),
]
CATEGORY_QUERIES = [
    ("宿泊", "accommodation.hotel", "1泊 8,000〜25,000円程度（未確認・デモ用）"),
    ("飲食", "catering.restaurant", "1人 1,000〜3,000円程度（未確認・デモ用）"),
    ("観光・体験", "tourism.attraction", "入場・体験料 500〜3,000円程度（未確認・デモ用）"),
    ("その他", "commercial", "利用内容により異なります（未確認・デモ用）"),
]

def account_rows():
    if not OUT.exists():
        return []
    with OUT.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def fetch_places(key):
    def query(pref, lon, lat, kind, api_category, price):
        radii = (35000, 120000, 250000) if api_category == "tourism.attraction" else (35000, 120000)
        categories = [api_category, "tourism.sights", "heritage", "tourism"] if api_category == "tourism.attraction" else [api_category]
        for search_category in categories:
          for radius in radii:
            response = requests.get("https://api.geoapify.com/v2/places", params={
                "categories": search_category, "filter": f"circle:{lon},{lat},{radius}",
                "bias": f"proximity:{lon},{lat}", "limit": 10, "lang": "ja", "apiKey": key,
            }, timeout=15)
            response.raise_for_status()
            for feature in response.json().get("features", []):
                p = feature.get("properties", {})
                name = str(p.get("name") or "").strip()
                address = str(p.get("address_line2") or p.get("formatted") or "").strip()
                if name and address:
                    cats = p.get("categories") or []
                    return {"name":name[:120],"category":kind,"prefecture":pref,"address":address[:255],
                        "price":price,"website":(p.get("website") or "")[:2048],
                        "opening":(p.get("opening_hours") or "営業時間は公式情報を確認してください（未確認）")[:300],
                        "description":f"Geoapify Places APIで取得した施設情報。施設との提携・アカウント所有関係はありません。料金・営業時間等は未確認のデモ用仮情報です。分類: {', '.join(cats[:4])}"}
        return None

    found = {}
    jobs = [(pref, lon, lat, kind, cat, price) for pref, lon, lat in PREFECTURES
            for kind, cat, price in CATEGORY_QUERIES]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(query, *job) for job in jobs]
        for future in as_completed(futures):
            try:
                place = future.result()
            except requests.RequestException:
                continue
            if place:
                found[(place["prefecture"], place["category"])] = place
    return [found[(pref, kind)] for pref, _, _ in PREFECTURES for kind, _, _ in CATEGORY_QUERIES
            if (pref, kind) in found]

def main():
    key = os.getenv("GEOAPIFY_API_KEY", "").strip()
    if not key:
        raise SystemExit("GEOAPIFY_API_KEY is not configured")
    places = fetch_places(key)
    expected = len(PREFECTURES) * len(CATEGORY_QUERIES)
    if len(places) != expected:
        coverage = {(p["prefecture"], p["category"]) for p in places}
        missing = [f"{pref}/{kind}" for pref, _, _ in PREFECTURES for kind, _, _ in CATEGORY_QUERIES if (pref,kind) not in coverage]
        raise SystemExit(f"Only {len(places)}/{expected} prefecture/genre entries found; database unchanged. Missing: {', '.join(missing)}")
    rows = account_rows()
    row_by_email = {r.get("ログインID（メールアドレス）"): r for r in rows}
    expanded_rows = []
    if EXPANDED_OUT.exists():
        with EXPANDED_OUT.open(encoding="utf-8-sig", newline="") as f:
            expanded_rows = list(csv.DictReader(f))
    expanded_by_email = {r.get("ログインID（メールアドレス）"): r for r in expanded_rows}
    updated = 0
    with app.app_context():
        users = []
        passwords = {}
        display_names = {}
        alphabet = string.ascii_letters + string.digits + "!@#$%&*-_+"
        for i in range(1, expected + 1):
            email = f"business{i:02d}@demo.tabidea.local"
            user = User.query.filter_by(email=email, user_type="business").first()
            if user is None:
                password = "".join(secrets.choice(alphabet) for _ in range(20))
                user = User(username=f"事業者デモ{i:03d}", email=email,
                    password_hash=generate_password_hash(password), user_type="business", business_detail=BusinessDetail())
                db.session.add(user); db.session.flush()
                passwords[email] = password
            elif i > 110 and email not in expanded_by_email:
                # Recover safely if the initial creation committed before its CSV was written.
                password = "".join(secrets.choice(alphabet) for _ in range(20))
                user.password_hash = generate_password_hash(password)
                passwords[email] = password
            users.append(user)
        for index, (user, place) in enumerate(zip(users, places), start=1):
            listing = BusinessListing.query.filter_by(user_id=user.id).first()
            if not listing:
                listing = BusinessListing(user_id=user.id, is_published=True)
                db.session.add(listing)
            listing.name = place["name"]
            listing.category = place["category"]
            listing.prefecture = place["prefecture"]
            listing.address = place["address"]
            listing.price_range = place["price"]
            listing.website_url = place["website"]
            listing.opening_hours = place["opening"]
            listing.description = place["description"]
            listing.is_published = True
            user.username = place["name"][:50]
            if user.business_detail:
                user.business_detail.address = place["address"][:255]
                user.business_detail.website_url = place["website"] or None
            email = f"business{index:02d}@demo.tabidea.local"
            if email in row_by_email:
                row_by_email[email]["表示名"] = user.username
            display_names[email] = user.username
            updated += 1
        db.session.commit()
    if rows:
        with OUT.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader(); writer.writerows(rows)
    if passwords:
        existing_emails = set(expanded_by_email)
        extra = [{"アカウント種別":"事業者","表示名":display_names[email],
                  "ログインID（メールアドレス）":email,"パスワード":password}
                 for email,password in passwords.items() if email not in existing_emails]
        with EXPANDED_OUT.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["アカウント種別","表示名","ログインID（メールアドレス）","パスワード"])
            writer.writeheader(); writer.writerows(extra)
    print(f"Updated {updated} listings: 47 prefectures x 4 genres. Approximate fields are labeled unverified.")

if __name__ == "__main__":
    main()
