"""データベースのテーブルと、テーブル間のつながりを定義します。"""

from datetime import datetime, timezone
from flask_login import UserMixin
from extensions import db
from sqlalchemy import UniqueConstraint

def utcnow():
    return datetime.now(timezone.utc)

class User(UserMixin, db.Model):
    """ログイン情報と利用者種別（旅行者・事業者）を保存します。"""
    __tablename__ = "user_auth"
    id = db.Column("user_id", db.Integer, primary_key=True)
    username = db.Column("user_name", db.String(50), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)
    avatar = db.Column(db.String(16), nullable=False, default="👤", server_default="👤")
    avatar_image = db.Column(db.String(255), nullable=True)
    is_suspended = db.Column(db.Boolean, nullable=False, default=False, server_default="0", index=True)
    suspension_reason = db.Column(db.Text, nullable=True)
    suspended_at = db.Column(db.DateTime(timezone=True), nullable=True)
    suspended_by_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    profile = db.relationship("TravelerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    business_detail = db.relationship("BusinessDetail", back_populates="user", uselist=False, cascade="all, delete-orphan")


class AccountModerationLog(db.Model):
    """運営者によるアカウント停止・解除の監査記録です。"""
    __tablename__ = "account_moderation_logs"
    id = db.Column(db.Integer, primary_key=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id"), nullable=False, index=True)
    operator_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id"), nullable=False, index=True)
    action = db.Column(db.String(20), nullable=False, index=True)
    reason = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    target_user = db.relationship("User", foreign_keys=[target_user_id])
    operator = db.relationship("User", foreign_keys=[operator_id])


class AccountReport(db.Model):
    """利用者が不適切なアカウントを運営へ報告した記録です。"""
    __tablename__ = "account_reports"
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id"), nullable=False, index=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id"), nullable=False, index=True)
    category = db.Column(db.String(40), nullable=False)
    details = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open", server_default="open", index=True)
    admin_note = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    handled_at = db.Column(db.DateTime(timezone=True))
    handled_by_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id"))
    reporter = db.relationship("User", foreign_keys=[reporter_id])
    target_user = db.relationship("User", foreign_keys=[target_user_id])
    handled_by = db.relationship("User", foreign_keys=[handled_by_id])


class AccountWarning(db.Model):
    """運営者から利用者へ送る警告と確認状態を保存します。"""
    __tablename__ = "account_warnings"
    id = db.Column(db.Integer, primary_key=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id"), nullable=False, index=True)
    operator_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id"), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    acknowledged_at = db.Column(db.DateTime(timezone=True), nullable=True)
    target_user = db.relationship("User", foreign_keys=[target_user_id])
    operator = db.relationship("User", foreign_keys=[operator_id])

class TravelerProfile(db.Model):
    """旅行者の好みを保存し、AIプラン作成時の参考にします。"""
    __tablename__ = "general_detail"
    id = db.Column("general_detail_id", db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id"), unique=True, nullable=False)
    birth_date = db.Column(db.Date)
    gender = db.Column(db.String(30))
    interest_themes = db.Column(db.Text, default="")
    travel_pace = db.Column(db.String(30), default="")
    budget_per_trip = db.Column(db.Integer)
    transportation = db.Column(db.String(100), default="")
    food_preference = db.Column(db.String(100), default="")
    avoid_conditions = db.Column(db.Text, default="")
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    user = db.relationship("User", back_populates="profile")
    @property
    def themes(self):
        return [x for x in (self.interest_themes or "").split(",") if x]

class TripGroup(db.Model):
    """旅行仲間のグループ本体と招待コードを保存します。"""
    __tablename__ = "trip_groups"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    icon = db.Column(db.String(16), nullable=False, default="🧳", server_default="🧳")
    icon_image = db.Column(db.String(255), nullable=True)
    invite_code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    owner = db.relationship("User", foreign_keys=[owner_id])
    members = db.relationship("TripGroupMember", back_populates="group", cascade="all, delete-orphan")
    bans = db.relationship("TripGroupBan", back_populates="group", cascade="all, delete-orphan")
    rejoin_requests = db.relationship("TripGroupRejoinRequest", back_populates="group", cascade="all, delete-orphan")
    messages = db.relationship("GroupMessage", back_populates="group", cascade="all, delete-orphan", order_by="GroupMessage.id")
    album_photos = db.relationship("GroupAlbumPhoto", back_populates="group", cascade="all, delete-orphan", order_by="GroupAlbumPhoto.created_at.desc()")
    travel_notes = db.relationship("GroupTravelNote", back_populates="group", cascade="all, delete-orphan", order_by="GroupTravelNote.starts_at")

class TripGroupMember(db.Model):
    """グループに参加している利用者を結び付けます。"""
    __tablename__ = "trip_group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_trip_group_member"),)
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("trip_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    joined_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    group = db.relationship("TripGroup", back_populates="members")
    user = db.relationship("User", backref=db.backref("trip_group_memberships", cascade="all, delete-orphan"))

class TripGroupBan(db.Model):
    """グループ作成者が参加を禁止した利用者を記録します。"""
    __tablename__ = "trip_group_bans"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_trip_group_ban"),)
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("trip_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    banned_by_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    group = db.relationship("TripGroup", back_populates="bans")
    user = db.relationship("User", foreign_keys=[user_id])
    banned_by = db.relationship("User", foreign_keys=[banned_by_id])

class TripGroupRejoinRequest(db.Model):
    """BANされた利用者からのグループ再参加申請を保存します。"""
    __tablename__ = "trip_group_rejoin_requests"
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("trip_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    requested_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    status = db.Column(db.String(16), nullable=False, default="pending", index=True)
    handled_at = db.Column(db.DateTime(timezone=True), nullable=True)
    group = db.relationship("TripGroup", back_populates="rejoin_requests")
    user = db.relationship("User", foreign_keys=[user_id])

class GroupMessage(db.Model):
    """グループ内のチャット投稿を保存します。"""
    __tablename__ = "group_messages"
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("trip_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    content = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    group = db.relationship("TripGroup", back_populates="messages")
    user = db.relationship("User")
    read_receipts = db.relationship("GroupMessageRead", back_populates="message", cascade="all, delete-orphan", order_by="GroupMessageRead.read_at")

class GroupMessageRead(db.Model):
    """誰がどのチャットを読んだか記録します。"""
    __tablename__ = "group_message_reads"
    __table_args__ = (UniqueConstraint("message_id", "user_id", name="uq_group_message_reader"),)
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("group_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    read_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    message = db.relationship("GroupMessage", back_populates="read_receipts")
    user = db.relationship("User")

class GroupMessageReaction(db.Model):
    """チャット投稿へのリアクションを記録します。"""
    __tablename__ = "group_message_reactions"
    __table_args__ = (UniqueConstraint("message_id", "user_id", name="uq_group_message_reaction_user"),)
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("group_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    emoji = db.Column(db.String(16), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    message = db.relationship("GroupMessage", backref=db.backref("reactions", cascade="all, delete-orphan", order_by="GroupMessageReaction.created_at"))
    user = db.relationship("User")

class GroupAlbumPhoto(db.Model):
    """グループ旅行のアルバム写真情報を保存します。"""
    __tablename__ = "group_album_photos"
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("trip_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    filename = db.Column(db.String(80), nullable=False, unique=True)
    caption = db.Column(db.String(300), nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    group = db.relationship("TripGroup", back_populates="album_photos")
    user = db.relationship("User")

class GroupExpense(db.Model):
    """グループ旅行で発生した費用を保存します。"""
    __tablename__ = "group_expenses"
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("trip_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    paid_by_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id"), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    spent_on = db.Column(db.Date, default=lambda: datetime.now(timezone.utc).date(), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    payer = db.relationship("User", foreign_keys=[paid_by_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    shares = db.relationship("GroupExpenseShare", back_populates="expense", cascade="all, delete-orphan")

class GroupExpenseShare(db.Model):
    """費用を誰がいくら負担するか記録します。"""
    __tablename__ = "group_expense_shares"
    id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(db.Integer, db.ForeignKey("group_expenses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    expense = db.relationship("GroupExpense", back_populates="shares")
    user = db.relationship("User")

class GroupBudget(db.Model):
    """グループで設定した旅行予算を保存します。"""
    __tablename__ = "group_budgets"
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("trip_groups.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    amount = db.Column(db.Integer, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    group = db.relationship("TripGroup")

class GroupTravelNote(db.Model):
    """旅程や予約など、グループで共有するメモを保存します。"""
    __tablename__ = "group_travel_notes"
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("trip_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    category = db.Column(db.String(20), nullable=False, default="メモ")
    title = db.Column(db.String(120), nullable=False)
    starts_at = db.Column(db.String(16), nullable=False, default="")
    location = db.Column(db.String(200), nullable=False, default="")
    reservation_url = db.Column(db.String(2048), nullable=False, default="")
    details = db.Column(db.String(2000), nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    group = db.relationship("TripGroup", back_populates="travel_notes")
    creator = db.relationship("User")

class BusinessDetail(db.Model):
    """事業者アカウントの連絡先などを保存します。"""
    __tablename__ = "business_detail"
    id = db.Column("business_detail_id", db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id"), unique=True, nullable=False)
    postal_code = db.Column(db.String(8))
    address = db.Column(db.String(255))
    phone_number = db.Column(db.String(20))
    contact_email = db.Column(db.String(255))
    website_url = db.Column(db.String(2048))
    contact_person = db.Column(db.String(100))
    user = db.relationship("User", back_populates="business_detail")

class TravelPlan(db.Model):
    """AIで作成した旅行プランと条件を保存します。"""
    __tablename__ = "travel_plans"
    id = db.Column("plan_id", db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id"), nullable=False, index=True)
    group_id = db.Column(db.Integer)
    title = db.Column(db.String(100), nullable=False)
    destination = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    days = db.Column(db.Integer, nullable=False, default=1)
    num_people = db.Column(db.Integer, nullable=False, default=1)
    budget = db.Column(db.Integer, nullable=False, default=0)
    theme = db.Column(db.String(200), default="")
    preferences = db.Column(db.Text, default="")
    ai_response = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    user = db.relationship("User", backref=db.backref("plans", cascade="all, delete-orphan"))
    packing_items = db.relationship("PackingItem", back_populates="plan", cascade="all, delete-orphan", order_by="PackingItem.id")
    travel_story = db.relationship("TravelStory", back_populates="plan", uselist=False, cascade="all, delete-orphan")

class TravelStory(db.Model):
    """公開・非公開の旅行記を保存します。"""
    __tablename__ = "travel_stories"
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("travel_plans.plan_id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    introduction = db.Column(db.String(1200), nullable=False, default="")
    is_public = db.Column(db.Boolean, nullable=False, default=True)
    view_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    comments_viewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    plan = db.relationship("TravelPlan", back_populates="travel_story")
    user = db.relationship("User")
    likes = db.relationship("TravelStoryLike", back_populates="story", cascade="all, delete-orphan")
    comments = db.relationship("TravelStoryComment", back_populates="story", cascade="all, delete-orphan", order_by="TravelStoryComment.created_at.asc()")

class TravelStoryLike(db.Model):
    """旅行記への「いいね」を記録します。"""
    __tablename__ = "travel_story_likes"
    __table_args__ = (UniqueConstraint("story_id", "user_id", name="uq_travel_story_like"),)
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey("travel_stories.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    story = db.relationship("TravelStory", back_populates="likes")
    user = db.relationship("User")

class TravelStoryComment(db.Model):
    """旅行記に付いたコメントと返信を保存します。"""
    __tablename__ = "travel_story_comments"
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey("travel_stories.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("travel_story_comments.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    content = db.Column(db.String(1200), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    story = db.relationship("TravelStory", back_populates="comments")
    user = db.relationship("User")
    parent = db.relationship("TravelStoryComment", remote_side=[id], back_populates="replies")
    replies = db.relationship("TravelStoryComment", back_populates="parent", cascade="all, delete-orphan", order_by="TravelStoryComment.created_at.asc()")

class PackingItem(db.Model):
    """旅行ごとの持ち物とチェック状態を保存します。"""
    __tablename__ = "packing_items"
    __table_args__ = (UniqueConstraint("plan_id", "user_id", "name", name="uq_packing_item_user_plan_name"),)
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("travel_plans.plan_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(40), nullable=False, default="その他")
    is_checked = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    plan = db.relationship("TravelPlan", back_populates="packing_items")
    user = db.relationship("User")

class BusinessListing(db.Model):
    """旅行者向けに掲載する施設・店舗情報を保存します。"""
    __tablename__ = "business_listings"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    prefecture = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(255), default="")
    price_range = db.Column(db.String(100), default="")
    website_url = db.Column(db.String(2048), default="")
    description = db.Column(db.Text, nullable=False)
    representative_name = db.Column(db.String(100), default="", nullable=False)
    phone = db.Column(db.String(20), default="", nullable=False)
    phone_verified = db.Column(db.Boolean, default=False, nullable=False)
    phone_verification_hash = db.Column(db.String(256), default="", nullable=False)
    phone_verification_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    phone_verification_sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    phone_verification_attempts = db.Column(db.Integer, default=0, nullable=False)
    access = db.Column(db.Text, default="", nullable=False)
    opening_hours = db.Column(db.String(300), default="", nullable=False)
    is_published = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    user = db.relationship("User", backref=db.backref("listings", cascade="all, delete-orphan"))
    reviews = db.relationship("Review", back_populates="listing", cascade="all, delete-orphan", order_by="Review.created_at.desc()")
    photos = db.relationship("BusinessListingPhoto", back_populates="listing", cascade="all, delete-orphan", order_by="BusinessListingPhoto.id")

class BusinessListingPhoto(db.Model):
    """施設・店舗に登録された写真を保存します。"""
    __tablename__ = "business_listing_photos"
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("business_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    listing = db.relationship("BusinessListing", back_populates="photos")

class Favorite(db.Model):
    """利用者がお気に入りにした掲載情報を記録します。"""
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "listing_id", name="uq_favorite_user_listing"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("business_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    listing = db.relationship("BusinessListing")
    user = db.relationship("User")

class Review(db.Model):
    """掲載施設・店舗への評価と口コミを保存します。"""
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("listing_id", "user_id", name="uq_review_listing_user"),)
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("business_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    listing = db.relationship("BusinessListing", back_populates="reviews")
    user = db.relationship("User")

class ViewHistory(db.Model):
    """利用者が閲覧した旅行記などの履歴を保存します。"""
    __tablename__ = "view_histories"
    __table_args__ = (UniqueConstraint("user_id", "target_type", "target_id", name="uq_view_history_target"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    target_type = db.Column(db.String(20), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    viewed_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False, index=True)

class AppNoticeRead(db.Model):
    """利用者がお知らせを読んだ状態を記録します。"""
    __tablename__ = "app_notice_reads"
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), primary_key=True)
    latest_notice_id = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    user = db.relationship("User")

class OperatorNotice(db.Model):
    """運営者が対象別に配信するお知らせを保存します。"""
    __tablename__ = "operator_notices"
    id = db.Column(db.Integer, primary_key=True)
    audience = db.Column(db.String(20), nullable=False, index=True)  # all / traveler / business
    category = db.Column(db.String(40), nullable=False, default="運営からのお知らせ")
    title = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="1", index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    author = db.relationship("User", foreign_keys=[author_id])
    reads = db.relationship("OperatorNoticeRead", back_populates="notice", cascade="all, delete-orphan")


class OperatorNoticeRead(db.Model):
    """運営からのお知らせを利用者ごとに既読管理します。"""
    __tablename__ = "operator_notice_reads"
    __table_args__ = (UniqueConstraint("notice_id", "user_id", name="uq_operator_notice_reader"),)
    id = db.Column(db.Integer, primary_key=True)
    notice_id = db.Column(db.Integer, db.ForeignKey("operator_notices.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    read_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    notice = db.relationship("OperatorNotice", back_populates="reads")
    user = db.relationship("User")


class PasswordResetToken(db.Model):
    """期限と使用状態をDBで管理する、再設定リンクのハッシュだけを保存します。"""
    __tablename__ = "password_reset_tokens"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    used_at = db.Column(db.DateTime(timezone=True))


class FormRateLimitEvent(db.Model):
    """お問い合わせ・再設定リンクの送信回数を、匿名化した照合値で管理します。"""
    __tablename__ = "form_rate_limit_events"
    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(40), nullable=False, index=True)
    fingerprint = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class ContactInquiry(db.Model):
    """お問い合わせフォームから届いた内容を保存します。"""
    __tablename__ = "contact_inquiries"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    category = db.Column(db.String(40), nullable=False)
    subject = db.Column(db.String(160), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
