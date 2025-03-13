from sqlalchemy import Column, Date, DateTime, Integer, String, Boolean, Enum, ForeignKey, BigInteger
from datetime import datetime, timezone
from sqlalchemy.orm import relationship, backref
from src.database import Base
from src.auth.enums import GenderEnum

class Follow(Base):
    """
    The Follow class represents a many-to-many relationship between users.
    """
    __tablename__ = "follows"

    follower_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    following_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    
    # Define relationships to access follower and following users
    following_user = relationship("User", back_populates="followers", foreign_keys=[follower_id])
    follower_user = relationship("User", back_populates="following", foreign_keys=[following_id])


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(BigInteger, unique=True)
    username = Column(String(255), unique=True)
    # hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    name = Column(String(255))
    dob = Column(Date)
    gender = Column(Enum(GenderEnum))
    profile_pic = Column(String)
    bio = Column(String(255))
    email = Column(String(255), unique=True)
    location = Column(String(255))

    # One-to-Many relationships
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="user", cascade="all, delete-orphan")
    # Many-to-Many Relationships
    liked_posts = relationship("Post", secondary="post_likes", back_populates="liked_by_users")
    followers = relationship("User", secondary="follows",
                             primaryjoin=id == Follow.following_id,
                             secondaryjoin=id == Follow.follower_id,
                             backref="following")
    
    followers = relationship("Follow", back_populates="following_user", foreign_keys="[Follow.follower_id]")
    following = relationship("Follow", back_populates="follower_user", foreign_keys="[Follow.following_id]")

    followers_count = Column(BigInteger, default=0)
    following_count = Column(BigInteger, default=0)
    saved_posts = relationship("UserSavedPosts", back_populates="user", cascade="all, delete")
    # Relationship for sent shares (user who is sharing)
    shared_posts_sent = relationship("UserSharedPosts", foreign_keys="[UserSharedPosts.sender_user_id]", back_populates="sender", cascade="all, delete")

    # Relationship for received shares (user who receives the shared post)
    shared_posts_received = relationship("UserSharedPosts", foreign_keys="[UserSharedPosts.receiver_user_id]", back_populates="receiver", cascade="all, delete")
