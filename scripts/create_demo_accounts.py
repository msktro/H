"""Create local demo accounts and export their one-time passwords to a CSV."""
import csv
import os
import secrets
import string
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app
from extensions import db
from models import BusinessDetail, TravelerProfile, User

OUTPUT = ROOT / "demo_accounts.csv"
ALPHABET = string.ascii_letters + string.digits + "!@#$%&*-_+"


def main():
    generated = []
    with app.app_context():
        targets = []
        for role, label, prefix in (
            ("traveler", "旅行者", "traveler"),
            ("business", "事業者", "business"),
        ):
            for number in range(1, 11):
                email = f"{prefix}{number:02d}@demo.tabidea.local"
                targets.append((role, label, prefix, number, email))

        existing = [email for *_, email in targets if User.query.filter_by(email=email).first()]
        if existing:
            raise SystemExit(
                "デモ用メールアドレスがすでに登録されています。既存データを変更せず終了しました。"
            )

        rows = []
        for role, label, prefix, number, email in targets:
            password = "".join(secrets.choice(ALPHABET) for _ in range(20))
            user = User(
                username=f"{label}デモ{number:02d}",
                email=email,
                password_hash=__import__("werkzeug.security", fromlist=["generate_password_hash"]).generate_password_hash(password),
                user_type=role,
            )
            if role == "traveler":
                user.profile = TravelerProfile()
            else:
                user.business_detail = BusinessDetail()
            db.session.add(user)
            rows.append([label, user.username, email, password])

        db.session.commit()

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8-sig", newline="", delete=False, dir=ROOT, suffix=".tmp"
        ) as handle:
            temp_path = Path(handle.name)
            writer = csv.writer(handle)
            writer.writerow(["アカウント種別", "表示名", "ログインID（メールアドレス）", "パスワード"])
            writer.writerows(rows)
        os.replace(temp_path, OUTPUT)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()

    print(f"旅行者10件・事業者10件を作成しました。")
    print(f"ログイン情報は {OUTPUT} に保存しました。")
    print("パスワードは画面やターミナルには表示していません。")


if __name__ == "__main__":
    main()
