"""Create 100 additional business demo accounts and public fictional listings."""
import csv
import os
import secrets
import string
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import CATEGORIES, PREFECTURES, app
from extensions import db
from models import BusinessDetail, BusinessListing, User
from werkzeug.security import generate_password_hash

OUTPUT = ROOT / "business_demo_accounts_11-110.csv"
ALPHABET = string.ascii_letters + string.digits + "!@#$%&*-_+"
CATEGORY_SUFFIX = {
    "宿泊": "の宿",
    "飲食": "の食堂",
    "観光・体験": "の体験施設",
    "交通": "の観光交通",
    "その他": "の観光サービス",
}


def read_account_rows():
    if not OUTPUT.exists():
        return ["アカウント種別", "表示名", "ログインID（メールアドレス）", "パスワード"], []
    with OUTPUT.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or ["アカウント種別", "表示名", "ログインID（メールアドレス）", "パスワード"]
        return fields, list(reader)


def main():
    fields, rows = read_account_rows()
    email_column = "ログインID（メールアドレス）"
    known_emails = {row.get(email_column, "") for row in rows}
    created_accounts = 0
    created_listings = 0
    skipped_existing = []
    generated_rows = []

    with app.app_context():
        for number in range(11, 111):
            email = f"business{number:02d}@demo.tabidea.local"
            user = User.query.filter_by(email=email).first()
            if user and user.user_type != "business":
                skipped_existing.append(f"{number:02d}: email belongs to a non-business account")
                continue
            if user:
                if email not in known_emails:
                    # Recover safely if the database commit succeeded but a prior
                    # run stopped before saving the credential CSV.
                    password = "".join(secrets.choice(ALPHABET) for _ in range(20))
                    user.password_hash = generate_password_hash(password)
                    generated_rows.append(["事業者", user.username, email, password])
                    known_emails.add(email)
                username = user.username
            else:
                password = "".join(secrets.choice(ALPHABET) for _ in range(20))
                user = User(
                    username=f"事業者デモ{number:02d}",
                    email=email,
                    password_hash=generate_password_hash(password),
                    user_type="business",
                    business_detail=BusinessDetail(),
                )
                db.session.add(user)
                db.session.flush()
                created_accounts += 1
                if email not in known_emails:
                    generated_rows.append(["事業者", user.username, email, password])
                    known_emails.add(email)

            if not BusinessListing.query.filter_by(user_id=user.id).first():
                prefecture = PREFECTURES[(number - 11) % len(PREFECTURES)]
                category = CATEGORIES[(number - 11) % len(CATEGORIES)]
                sample_name = f"デモ{number:03d}｜{prefecture[:2]}{CATEGORY_SUFFIX[category]}"
                db.session.add(BusinessListing(
                    user_id=user.id,
                    name=sample_name,
                    category=category,
                    prefecture=prefecture,
                    address=f"{prefecture} デモエリア",
                    price_range="デモ用料金（架空）",
                    website_url="",
                    description="【架空デモ用】口コミ投稿と都道府県絞り込みの確認に使用するサンプル掲載情報です。実在の施設・店舗・サービスとは関係ありません。",
                    is_published=True,
                ))
                created_listings += 1

        db.session.commit()

    if generated_rows:
        rows.extend(dict(zip(fields, row)) for row in generated_rows)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8-sig", newline="", delete=False,
                dir=ROOT, suffix=".tmp"
            ) as handle:
                temp_path = Path(handle.name)
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            os.replace(temp_path, OUTPUT)
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink()

    print(f"新規作成: 事業者アカウント{created_accounts}件、公開サンプル施設{created_listings}件")
    print(f"ログイン情報を {OUTPUT} に保存しました。パスワードは画面に表示していません。")
    if skipped_existing:
        print("確認が必要な既存アカウント: " + "; ".join(skipped_existing))


if __name__ == "__main__":
    main()
