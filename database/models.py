from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, String, Boolean, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase): pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    full_name: Mapped[str] = mapped_column(String)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    coins_balance: Mapped[int] = mapped_column(Integer, default=0)
    referral_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    premium_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    premium_lessons_quota: Mapped[int] = mapped_column(Integer, default=0)
    premium_lessons_used: Mapped[int] = mapped_column(Integer, default=0)
    checkin_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_checkin: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"), nullable=True)
    title_uz: Mapped[str] = mapped_column(String)
    title_ru: Mapped[str] = mapped_column(String)
    order_num: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    children = relationship("Category", back_populates="parent", cascade="all, delete-orphan")
    parent = relationship("Category", back_populates="children", remote_side=[id])
    lessons = relationship("Lesson", back_populates="category", cascade="all, delete-orphan")


class Lesson(Base):
    __tablename__ = "lessons"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    title_uz: Mapped[str] = mapped_column(String)
    title_ru: Mapped[str] = mapped_column(String)
    content_uz: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_ru: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    video_file_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    video_title_uz: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    video_title_ru: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    coin_cost: Mapped[int] = mapped_column(Integer, default=0)
    is_premium_only: Mapped[bool] = mapped_column(Boolean, default=False)
    order_num: Mapped[int] = mapped_column(Integer, default=0)

    category = relationship("Category", back_populates="lessons")


class PremiumPackage(Base):
    __tablename__ = "premium_packages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_uz: Mapped[str] = mapped_column(String)
    name_ru: Mapped[str] = mapped_column(String)
    price_uzs: Mapped[int] = mapped_column(Integer)
    price_coins: Mapped[int] = mapped_column(Integer, default=0)
    lessons_quota: Mapped[int] = mapped_column(Integer)
    bonus_coins: Mapped[int] = mapped_column(Integer, default=0)
    duration_days: Mapped[int] = mapped_column(Integer, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UnlockedLesson(Base):
    __tablename__ = "unlocked_lessons"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CoinTransaction(Base):
    __tablename__ = "coin_transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(30))
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PaymentRequest(Base):
    __tablename__ = "payment_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    package_id: Mapped[int] = mapped_column(ForeignKey("premium_packages.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    file_id: Mapped[str] = mapped_column(String)
    file_type: Mapped[str] = mapped_column(String(10))
    admin_comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PromoCode(Base):
    __tablename__ = "promo_codes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    coins_amount: Mapped[int] = mapped_column(Integer)
    max_uses: Mapped[int] = mapped_column(Integer, default=100)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PromoCodeUsage(Base):
    __tablename__ = "promo_code_usage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    promo_code_id: Mapped[int] = mapped_column(ForeignKey("promo_codes.id"))
    used_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RequiredChannel(Base):
    __tablename__ = "required_channels"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger)
    channel_username: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)