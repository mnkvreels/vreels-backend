from sqlalchemy import Column, Date, DateTime, Integer, String, Boolean, Enum, ForeignKey
from datetime import datetime, timezone
from sqlalchemy.orm import relationship
from src.database import Base
from src.auth.enums import GenderEnum
from src.post.models import Like, Comment, Post

class Follow(Base):
    """
    The FollowRelation class represents a many-to-many relationship between users.
    A user can follow multiple users, and can also be followed by multiple users.
    """
    __tablename__ = "Follows"

    # Foreign key to user being followed
    follower_id = Column(Integer, ForeignKey("Users.id"), primary_key=True)
    # Foreign key to user who is following
    following_id = Column(Integer, ForeignKey("Users.id"), primary_key=True)

    # Relationship to the User class for the follower
    follower = relationship(
        "User", foreign_keys=[follower_id], back_populates="followers"
    )

    # Relationship to the User class for the followed user
    following = relationship(
        "User", foreign_keys=[following_id], back_populates="following"
    )

class User(Base):
    __tablename__ = "Users"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(Integer, unique=True)
    username = Column(String(255), unique=True)
    hashed_password = Column(String, nullable=False)
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

    posts = relationship("Post", back_populates="author")

    # Relationship with liked posts
    liked_posts = relationship(
        "Post", secondary="Likes", backref="liked_by_users"
    )

    # Other relationships
    commented_posts = relationship(
        "Post", secondary="Comments", back_populates="commented_by_users"
    )
    
    followers = relationship(
        Follow, foreign_keys=[Follow.following_id], back_populates="following"
    )
    following = relationship(
        Follow, foreign_keys=[Follow.follower_id], back_populates="followers"
    )

    followers_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)


