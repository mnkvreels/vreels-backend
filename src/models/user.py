from sqlalchemy import VARCHAR, Column, Date, DateTime, Integer, String, Boolean, Enum, ForeignKey, BigInteger, NVARCHAR, Index
from datetime import datetime, timezone
from sqlalchemy.orm import relationship, backref
from src.database import Base
from src.auth.enums import GenderEnum, AccountTypeEnum

class Follow(Base):
    __tablename__ = "follows"
    __table_args__ = (
        Index("ix_follows_follower_id", "follower_id"),
        Index("ix_follows_following_id", "following_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    follower_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    following_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    follower_user = relationship("User", back_populates="following", foreign_keys=[follower_id])
    following_user = relationship("User", back_populates="followers", foreign_keys=[following_id])


class FollowRequest(Base):
    __tablename__ = "follow_requests"
    __table_args__ = (
        Index("ix_followrequest_requester_target", "requester_id", "target_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    target_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    requester = relationship("User", foreign_keys=[requester_id], backref="sent_follow_requests")
    target = relationship("User", foreign_keys=[target_id], backref="received_follow_requests")



class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(BigInteger, unique=True)
    username = Column(String(255), unique=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    name = Column(NVARCHAR(255))
    dob = Column(Date)
    gender = Column(Enum(GenderEnum))
    profile_pic = Column(String)
    bio = Column(NVARCHAR(255))
    email = Column(String(255), unique=True)
    location = Column(NVARCHAR(255))
    account_type = Column(Enum(AccountTypeEnum), default=AccountTypeEnum.PUBLIC, nullable=False)
    report_count = Column(Integer, default=0)
    # One-to-Many relationships
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="user", cascade="all, delete-orphan")
    liked_posts = relationship("Post", secondary="post_likes", back_populates="liked_by_users")
    
    # Many-to-Many Relationships (via Follow table)
    followers = relationship("Follow", back_populates="following_user", foreign_keys="[Follow.following_id]")
    following = relationship("Follow", back_populates="follower_user", foreign_keys="[Follow.follower_id]")

    followers_count = Column(BigInteger, default=0)
    following_count = Column(BigInteger, default=0)
    saved_posts = relationship("UserSavedPosts", back_populates="user", cascade="all, delete")
    # Relationship for sent shares (user who is sharing)
    shared_posts_sent = relationship("UserSharedPosts", foreign_keys="[UserSharedPosts.sender_user_id]", back_populates="sender", cascade="all, delete")

    # Relationship for received shares (user who receives the shared post)
    shared_posts_received = relationship("UserSharedPosts", foreign_keys="[UserSharedPosts.receiver_user_id]", back_populates="receiver", cascade="all, delete")
    devices = relationship("UserDevice", back_populates="user", cascade="all, delete-orphan")
    media_interactions = relationship("MediaInteraction", back_populates="user", cascade="all, delete-orphan")

class BlockedUsers(Base):
    __tablename__ = "blocked_users"
    __table_args__ = (
        Index("ix_blockedusers_blocker_blocked", "blocker_id", "blocked_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    blocker_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    blocked_id = Column(Integer, ForeignKey("users.id"), nullable=False)

# Database Model for OTP
class OTP(Base):
    __tablename__ = "otp"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    otp = Column(VARCHAR(255))
    created_at = Column(DateTime, default=datetime.now(timezone.utc)) 

class UserDevice(Base):
    __tablename__ = "user_devices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    device_id = Column(String(255), unique=True)
    device_token = Column(String(255), nullable=False)
    platform = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    # Notification flags
    notify_likes = Column(Boolean, default=True)
    notify_comments = Column(Boolean, default=True)
    notify_share = Column(Boolean, default=True)
    notify_calls = Column(Boolean, default=True)
    notify_messages = Column(Boolean, default=True)
    notify_follow = Column(Boolean, default=True)
    notify_posts = Column(Boolean, default=True)
    notify_status = Column(Boolean, default=True)
    sync_contacts = Column(Boolean, default=False)

    user = relationship("User", back_populates="devices")

    def __repr__(self):
        return f"<UserDevice(user_id={self.user_id}, device_id={self.device_id}, platform={self.platform})>"
    
class UserDeviceContact(Base):
    __tablename__ = "user_device_contacts"

    id = Column(Integer, primary_key=True, index=True)
    user_device_id = Column(Integer, ForeignKey("user_devices.id", ondelete="CASCADE"), nullable=False)
    name = Column(NVARCHAR(255), nullable=False)
    phone_number = Column(String(50), nullable=False)

    user_device = relationship("UserDevice", backref="device_contacts")
