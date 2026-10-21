"""Attach category-matched sample photos to existing demo business listings.

Run with: python scripts/load_business_demo_photos.py
The operation is repeatable: listings with any existing photo are left alone.
"""
from collections import defaultdict
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app
from extensions import db
from models import BusinessListing, BusinessListingPhoto, User


ASSETS = {
    "宿泊": ("lodging_1.jpg", "lodging_2.jpg", "lodging_3.jpg"),
    "飲食": ("food_1.jpg", "food_2.jpg", "food_3.jpg"),
    "観光・体験": ("experience_1.jpg", "experience_2.jpg", "experience_3.jpg"),
    "交通": ("transport_1.jpg", "transport_2.jpg", "transport_3.jpg"),
    "その他": ("other_1.jpg", "other_2.jpg", "other_3.jpg"),
}


def main():
    source_dir = ROOT / "static" / "demo_business_photos"
    photo_root = Path(app.instance_path) / "business_photos"
    assigned_by_category = defaultdict(int)
    copied_files = []
    attached = 0
    skipped = 0

    with app.app_context():
        listings = (
            BusinessListing.query.join(User)
            .filter(User.user_type == "business", User.email.like("business%@demo.tabidea.local"))
            .order_by(BusinessListing.id)
            .all()
        )
        try:
            for listing in listings:
                if listing.photos:
                    skipped += 1
                    continue

                category = listing.category if listing.category in ASSETS else "その他"
                options = ASSETS[category]
                index = assigned_by_category[category] % len(options)
                assigned_by_category[category] += 1
                asset_name = options[index]
                source = source_dir / asset_name
                if not source.is_file():
                    raise FileNotFoundError(f"Missing sample asset: {source}")

                filename = f"demo_{Path(asset_name).stem}_{listing.id}.jpg"
                target_dir = photo_root / str(listing.id)
                target_dir.mkdir(parents=True, exist_ok=True)
                target = target_dir / filename
                shutil.copyfile(source, target)
                copied_files.append(target)
                db.session.add(BusinessListingPhoto(listing_id=listing.id, filename=filename))
                attached += 1

            db.session.commit()
        except Exception:
            db.session.rollback()
            for path in copied_files:
                path.unlink(missing_ok=True)
            raise

    print(f"Demo business listings found: {len(listings)}")
    print(f"Sample photos attached: {attached}")
    print(f"Skipped because photos already exist: {skipped}")


if __name__ == "__main__":
    main()
