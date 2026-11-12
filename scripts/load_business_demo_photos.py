"""Attach category-matched sample photos to existing demo business listings.

Run with: python scripts/load_business_demo_photos.py
For AWS, deploy this code and static/demo_business_photos first, then run the
same command from the app directory on the server to attach photos to its DB.
The operation is repeatable: venue-specific photos replace generated placeholders,
but photos uploaded by a business owner are preserved.
"""
from collections import defaultdict
from pathlib import Path
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
PLACE_PHOTOS = {
    "フクイラプトル": "place_fukui_raptor.jpg",
    "静岡県庁別館": "place_shizuoka_annex.jpg",
    "DoubleTree by Hilton Osaka Castle": "place_doubletree_osaka_castle.jpg",
    "県庁CLASS": "place_saga_kencho_class.jpg",
}


def main():
    assigned_by_category = defaultdict(int)
    attached = 0
    skipped = 0

    with app.app_context():
        listings = (
            BusinessListing.query.join(User)
            .filter(User.user_type == "business", User.email.like("business%@demo.tabidea.local"))
            .order_by(BusinessListing.id)
            .all()
        )
        for listing in listings:
            place_photo = PLACE_PHOTOS.get(listing.name)
            if place_photo:
                if any(photo.filename == place_photo for photo in listing.photos):
                    skipped += 1
                    continue
                # Replace only generated demo placeholders. Preserve any real
                # photo uploaded to the listing by its account owner.
                if any(not photo.filename.startswith("demo_") for photo in listing.photos):
                    skipped += 1
                    continue
                for photo in list(listing.photos):
                    db.session.delete(photo)
                source = ROOT / "static" / "business_place_photos" / place_photo
                if not source.is_file():
                    raise FileNotFoundError(f"Missing place photo: {source}")
                db.session.add(BusinessListingPhoto(listing_id=listing.id, filename=place_photo))
                attached += 1
                continue

            if listing.photos:
                skipped += 1
                continue

            category = listing.category if listing.category in ASSETS else "その他"
            options = ASSETS[category]
            index = assigned_by_category[category] % len(options)
            assigned_by_category[category] += 1
            asset_name = options[index]
            source = ROOT / "static" / "demo_business_photos" / asset_name
            if not source.is_file():
                raise FileNotFoundError(f"Missing sample asset: {source}")

            # Keep only the shared asset's filename in the database. The photo
            # route serves it from the deployed app's static directory, which
            # avoids dependence on ephemeral AWS instance storage.
            filename = f"demo_{asset_name}"
            db.session.add(BusinessListingPhoto(listing_id=listing.id, filename=filename))
            attached += 1

        db.session.commit()

    print(f"Demo business listings found: {len(listings)}")
    print(f"Sample photos attached: {attached}")
    print(f"Skipped because photos already exist: {skipped}")


if __name__ == "__main__":
    main()
