"""Add one clearly fictional, published sample listing to each demo business account."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app
from extensions import db
from models import BusinessListing, User


SAMPLES = [
    ("北の森デモロッジ", "宿泊", "北海道", "札幌市（デモ住所）", "1泊 8,000円〜", "北海道の自然を楽しむ宿のサンプルです。設備・料金・営業時間はすべて架空のデモ情報です。"),
    ("りんご畑デモ体験", "観光・体験", "青森県", "弘前市（デモ住所）", "体験 2,000円〜", "りんご畑を巡る体験施設のサンプルです。実在の施設ではありません。"),
    ("東京まち歩きデモ案内所", "観光・体験", "東京都", "台東区（デモ住所）", "案内 1,500円〜", "下町散策を案内する店舗のサンプルです。実在の施設ではありません。"),
    ("信州そばデモ食堂", "飲食", "長野県", "松本市（デモ住所）", "食事 1,200円〜", "信州そばを提供する飲食店のサンプルです。実在の店舗ではありません。"),
    ("京の小径デモ工房", "観光・体験", "京都府", "京都市（デモ住所）", "体験 3,000円〜", "伝統工芸を体験できる工房のサンプルです。実在の施設ではありません。"),
    ("大阪まんぷくデモ食堂", "飲食", "大阪府", "大阪市（デモ住所）", "食事 900円〜", "大阪グルメを楽しむ飲食店のサンプルです。実在の店舗ではありません。"),
    ("瀬戸内デモクルーズ", "交通", "広島県", "尾道市（デモ住所）", "乗船 2,500円〜", "瀬戸内海を巡る船旅のサンプルです。運航情報・料金は架空です。"),
    ("博多屋台デモ横丁", "飲食", "福岡県", "福岡市（デモ住所）", "食事 1,000円〜", "屋台街をイメージした飲食店のサンプルです。実在の店舗ではありません。"),
    ("桜島デモ展望スポット", "観光・体験", "鹿児島県", "鹿児島市（デモ住所）", "見学 無料（デモ）", "火山と海の景色を楽しむスポットのサンプルです。実在の施設ではありません。"),
    ("沖縄そらデモカフェ", "飲食", "沖縄県", "那覇市（デモ住所）", "飲み物 600円〜", "沖縄の雰囲気を楽しむカフェのサンプルです。実在の店舗ではありません。"),
]


def main():
    created = 0
    skipped = []
    with app.app_context():
        for number, sample in enumerate(SAMPLES, start=1):
            email = f"business{number:02d}@demo.tabidea.local"
            user = User.query.filter_by(email=email, user_type="business").first()
            if not user:
                skipped.append(f"business{number:02d}: account not found")
                continue
            if BusinessListing.query.filter_by(user_id=user.id).first():
                skipped.append(f"business{number:02d}: listing already exists")
                continue
            name, category, prefecture, address, price_range, description = sample
            db.session.add(BusinessListing(
                user_id=user.id,
                name=f"デモ{number:02d}｜{name}",
                category=category,
                prefecture=prefecture,
                address=address,
                price_range=price_range,
                website_url="",
                description=f"【デモ用サンプル】{description}",
                is_published=True,
            ))
            created += 1
        db.session.commit()
    print(f"サンプル掲載情報を{created}件登録しました（公開状態）。")
    if skipped:
        print("スキップ: " + "; ".join(skipped))


if __name__ == "__main__":
    main()
