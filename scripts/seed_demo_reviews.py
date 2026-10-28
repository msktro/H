"""Add clearly labeled sample reviews to fictional demo business listings."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app
from extensions import db
from models import BusinessListing, Review, User


RATING_SETS = (
    (5, 4, 5, 4, 5),
    (4, 5, 4, 5, 4),
    (5, 5, 4, 5, 5),
    (4, 4, 5, 4, 5),
)

COMMENTS = {
    "宿泊": (
        "落ち着いて過ごせる雰囲気をイメージした宿のサンプルです。",
        "旅行中にゆっくり休める場所を探す想定のデモ投稿です。",
        "宿泊先を比べる画面の確認用に登録したサンプル口コミです。",
    ),
    "飲食": (
        "旅先の食事を楽しむ場面を想定したデモ投稿です。",
        "メニューや料金を比べる動作確認用のサンプル口コミです。",
        "旅行中に立ち寄る飲食店を探す画面用のサンプルです。",
    ),
    "観光・体験": (
        "旅先で体験を楽しむ場面を想定したデモ投稿です。",
        "観光スポットの評価表示を確認するためのサンプル口コミです。",
        "旅行の予定に入れる体験先を探す画面用のサンプルです。",
    ),
    "交通": (
        "移動や乗り物の候補表示を確認するためのサンプル口コミです。",
        "旅先での移動サービスを比べる想定のデモ投稿です。",
        "交通カテゴリの評価表示を確認するサンプル口コミです。",
    ),
    "その他": (
        "掲載情報と口コミ表示を確認するためのサンプル投稿です。",
        "旅行中に立ち寄る場所を探す画面用のデモ口コミです。",
        "動作確認用に登録したサンプル口コミです。",
    ),
}


def main():
    added = 0
    skipped_existing = 0
    missing_accounts = []
    with app.app_context():
        reviewers = []
        for number in range(1, 11):
            email = f"traveler{number:02d}@demo.tabidea.local"
            user = User.query.filter_by(email=email, user_type="traveler").first()
            if user:
                reviewers.append(user)
            else:
                missing_accounts.append(email)
        if not reviewers:
            raise SystemExit("旅行者デモアカウントがありません。先にデモアカウントを作成してください。")

        listings = (BusinessListing.query.join(User)
                    .filter(
                        User.user_type == "business",
                        User.email.like("business%@demo.tabidea.local"),
                    ).order_by(BusinessListing.id).all())
        for listing in listings:
            rating_set = RATING_SETS[listing.id % len(RATING_SETS)]
            comments = COMMENTS.get(listing.category, COMMENTS["その他"])
            for index, reviewer in enumerate(reviewers[:5]):
                existing = Review.query.filter_by(
                    listing_id=listing.id, user_id=reviewer.id
                ).first()
                if existing:
                    skipped_existing += 1
                    continue
                comment = (
                    f"【デモ口コミ】{comments[index % len(comments)]}"
                    "実際の利用者の感想ではなく、アプリ動作確認用の架空データです。"
                )
                db.session.add(Review(
                    listing_id=listing.id,
                    user_id=reviewer.id,
                    rating=rating_set[index % len(rating_set)],
                    comment=comment,
                ))
                added += 1
        db.session.commit()

    print(f"デモ掲載情報: {len(listings)}件")
    print(f"サンプル口コミ追加: {added}件（各掲載情報に最大5件）")
    print(f"既存口コミのためスキップ: {skipped_existing}件")
    if missing_accounts:
        print(f"見つからない旅行者デモアカウント: {len(missing_accounts)}件")


if __name__ == "__main__":
    main()
