from sqlalchemy import Column, Date, DateTime, Integer, String, Boolean, Enum, ForeignKey, BigInteger
from datetime import datetime, timezone
from sqlalchemy.orm import relationship, backref
from src.database import Base
from src.auth.enums import GenderEnum

class Follow(Base):
    """
    The Follow class represents a many-to-many relationship between users.
    """
    __tablename__ = "Follows"

    follower_id = Column(Integer, ForeignKey("Users.id"), primary_key=True)
    following_id = Column(Integer, ForeignKey("Users.id"), primary_key=True)

class User(Base):
    __tablename__ = "Users"

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
    
    # Many-to-Many Relationships
    liked_posts = relationship("Post", secondary="post_likes", back_populates="liked_by_users")
    followers = relationship("User", secondary="Follows",
                             primaryjoin=id == Follow.following_id,
                             secondaryjoin=id == Follow.follower_id,
                             backref="following")

    followers_count = Column(BigInteger, default=0)
    following_count = Column(BigInteger, default=0)
