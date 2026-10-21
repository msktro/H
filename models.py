from datetime import datetime, timezone
from flask_login import UserMixin
from extensions import db
from sqlalchemy import UniqueConstraint

def utcnow():
    return datetime.now(timezone.utc)

class User(UserMixin, db.Model):
    __tablename__ = "user_auth"
    id = db.Column("user_id", db.Integer, primary_key=True)
    username = db.Column("user_name", db.String(50), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)
    avatar = db.Column(db.String(16), nullable=False, default="👤", server_default="👤")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    profile = db.relationship("TravelerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    business_detail = db.relationship("BusinessDetail", back_populates="user", uselist=False, cascade="all, delete-orphan")

class TravelerProfile(db.Model):
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
    __tablename__ = "trip_groups"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    invite_code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    owner = db.relationship("User", foreign_keys=[owner_id])
    members = db.relationship("TripGroupMember", back_populates="group", cascade="all, delete-orphan")
    messages = db.relationship("GroupMessage", back_populates="group", cascade="all, delete-orphan", order_by="GroupMessage.id")
    album_photos = db.relationship("GroupAlbumPhoto", back_populates="group", cascade="all, delete-orphan", order_by="GroupAlbumPhoto.created_at.desc()")
    travel_notes = db.relationship("GroupTravelNote", back_populates="group", cascade="all, delete-orphan", order_by="GroupTravelNote.starts_at")

class TripGroupMember(db.Model):
    __tablename__ = "trip_group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_trip_group_member"),)
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("trip_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    joined_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    group = db.relationship("TripGroup", back_populates="members")
    user = db.relationship("User", backref=db.backref("trip_group_memberships", cascade="all, delete-orphan"))

class GroupMessage(db.Model):
    __tablename__ = "group_messages"
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("trip_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    content = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    group = db.relationship("TripGroup", back_populates="messages")
    user = db.relationship("User")

class GroupAlbumPhoto(db.Model):
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
    __tablename__ = "group_expense_shares"
    id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(db.Integer, db.ForeignKey("group_expenses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    expense = db.relationship("GroupExpense", back_populates="shares")
    user = db.relationship("User")

class GroupBudget(db.Model):
    __tablename__ = "group_budgets"
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("trip_groups.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    amount = db.Column(db.Integer, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    group = db.relationship("TripGroup")

class GroupTravelNote(db.Model):
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

class PackingItem(db.Model):
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
    is_published = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    user = db.relationship("User", backref=db.backref("listings", cascade="all, delete-orphan"))
    reviews = db.relationship("Review", back_populates="listing", cascade="all, delete-orphan", order_by="Review.created_at.desc()")
    photos = db.relationship("BusinessListingPhoto", back_populates="listing", cascade="all, delete-orphan", order_by="BusinessListingPhoto.id")

class BusinessListingPhoto(db.Model):
    __tablename__ = "business_listing_photos"
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("business_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    listing = db.relationship("BusinessListing", back_populates="photos")

class Favorite(db.Model):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "listing_id", name="uq_favorite_user_listing"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("business_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    listing = db.relationship("BusinessListing")
    user = db.relationship("User")

class Review(db.Model):
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

class ContactInquiry(db.Model):
    __tablename__ = "contact_inquiries"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    category = db.Column(db.String(40), nullable=False)
    subject = db.Column(db.String(160), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
