"""Give sample travel stories demo-only views and likes; safe to rerun."""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app
from extensions import db
from models import TravelPlan, TravelStory, TravelStoryLike, User


def main():
    rng = random.Random(20261027)
    with app.app_context():
        demo_users = (User.query
                      .filter(User.user_type == "traveler",
                              User.email.like("traveler%@demo.tabidea.local"),
                              User.username.like("旅行者デモ%"))
                      .order_by(User.id).all())
        if len(demo_users) < 9:
            raise SystemExit("旅行者デモアカウントが9件見つからないため、変更していません。")

        stories = (TravelStory.query
                   .join(TravelPlan, TravelStory.plan_id == TravelPlan.id)
                   .filter(TravelPlan.title.like("【サンプル】%"), TravelStory.is_public.is_(True))
                   .order_by(TravelStory.id).all())
        if not stories:
            raise SystemExit("公開中のサンプル旅行記が見つからないため、変更していません。")

        for story in stories:
            # Only use demo travelers and never add a self-like.
            eligible = [user for user in demo_users if user.id != story.user_id]
            rng.shuffle(eligible)
            target_likes = rng.randint(2, min(8, len(eligible)))
            existing_demo_likes = {
                like.user_id for like in TravelStoryLike.query.filter_by(story_id=story.id).all()
                if any(user.id == like.user_id for user in demo_users)
            }
            needed = max(0, target_likes - len(existing_demo_likes))
            for user in (candidate for candidate in eligible if candidate.id not in existing_demo_likes):
                if needed <= 0:
                    break
                db.session.add(TravelStoryLike(story_id=story.id, user_id=user.id))
                needed -= 1
            story.view_count = rng.randint(28, 246)

        db.session.commit()
        print(f"サンプル旅行記{len(stories)}件の閲覧数を設定し、デモ用いいねを追加しました。")


if __name__ == "__main__":
    main()
