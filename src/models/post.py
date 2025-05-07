from requests import Session
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Table, func, Enum, Interval, Boolean, UniqueConstraint, NVARCHAR
from sqlalchemy.orm import relationship, backref
from datetime import datetime, timezone, timedelta
from src.database import Base
from ..post.enums import VisibilityEnum, MediaTypeEnum

# Many-to-Many Association Table (users ↔ Liked posts)
post_likes = Table(
    "post_likes", Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("post_id", Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
)

# Many-to-Many Association Table (posts ↔ hashtags)
post_hashtags = Table(
    "post_hashtags",
    Base.metadata,
    Column("post_id", Integer, ForeignKey("posts.id")),
    Column("hashtag_id", Integer, ForeignKey("hashtags.id"))
)

# likes model (Tracks who liked which post)
class Like(Base):
    __tablename__ = "likes"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    user_id = Column(Integer, ForeignKey("users.id"))
    post_id = Column(Integer, ForeignKey("posts.id"))
    
    post = relationship("Post", back_populates="likes")
    user = relationship("User", back_populates="likes")

# Comment Model
class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    content = Column(NVARCHAR("max"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    report_count = Column(Integer, default=0)

    post_id = Column(Integer, ForeignKey("posts.id"))
    user_id = Column(Integer, ForeignKey("users.id"))

    post = relationship("Post", back_populates="comments")
    user = relationship("User", back_populates="comments")

# Post Model
class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(NVARCHAR("max"))
    media = Column(String)
    location = Column(String)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    report_count = Column(Integer, default=0)
    views_count = Column(Integer, default=0)  # NEW
    save_count = Column(Integer, default=0)   # NEW
    category_of_content = Column(NVARCHAR(100), nullable=True)  # NEW
    media_type = Column(String(50), nullable=True)  # NEW
    author_id = Column(Integer, ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
    visibility = Column(Enum(VisibilityEnum), nullable=False, default="public")
    thumbnail = Column(String, nullable=True)
    video_length = Column(Integer, default=0, nullable=False)
    comments_disabled = Column(Boolean, default=False, nullable=False)
    # Many-to-Many Relationships
    liked_by_users = relationship("User", secondary="post_likes", back_populates="liked_posts")
    hashtags = relationship("Hashtag", secondary="post_hashtags", back_populates="posts")

    # One-to-Many Relationships
    likes = relationship("Like", back_populates="post", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    share_count = Column(Integer, default=0)
    saved_by_users = relationship("UserSavedPosts", back_populates="post", cascade="all, delete")
    shared_by_users = relationship("UserSharedPosts", back_populates="post", cascade="all, delete")
    interactions = relationship("MediaInteraction", back_populates="media", cascade="all, delete-orphan")
    def update_likes_and_comments_count(self, db: Session):
        """Update likes_count and comments_count for the post."""
        self.likes_count = (
            db.query(func.count(Like.id)).filter(Like.post_id == self.id).scalar() or 0
        )
        self.comments_count = (
            db.query(func.count(Comment.id)).filter(Comment.post_id == self.id).scalar() or 0
        )

# Hashtag Model
class Hashtag(Base):
    __tablename__ = "hashtags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(NVARCHAR(255), unique=True)

    posts = relationship("Post", secondary="post_hashtags", back_populates="hashtags")

class UserSavedPosts(Base):
    __tablename__ = "user_saved_posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    saved_post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    # Post attributes to be saved
    content = Column(NVARCHAR(255))
    media = Column(String)
    location = Column(String)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    visibility = Column(Enum(VisibilityEnum), nullable=False, default="public")

    # Relationships
    user = relationship("User", back_populates="saved_posts")
    post = relationship("Post", back_populates="saved_by_users")

class UserSharedPosts(Base):
    __tablename__ = "user_shared_posts"

    id = Column(Integer, primary_key=True, index=True)
    sender_user_id = Column(Integer, ForeignKey("users.id", ondelete="NO ACTION"), nullable=False)
    receiver_user_id = Column(Integer, ForeignKey("users.id", ondelete="NO ACTION"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    sender = relationship("User", foreign_keys=[sender_user_id], back_populates="shared_posts_sent")
    receiver = relationship("User", foreign_keys=[receiver_user_id], back_populates="shared_posts_received")
    post = relationship("Post", back_populates="shared_by_users")
    
class MediaInteraction(Base):
    __tablename__ = "media_interactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)  # ID of the post
    watched_time = Column(Integer, default=0)
    media_type = Column(Enum(MediaTypeEnum), nullable=False, default=MediaTypeEnum.image)  # Media type: image or video
    video_length = Column(Integer, nullable=True, default=timedelta(seconds=0))  # Length of video in seconds (nullable for images)
    skipped = Column(Boolean, default=False)  # Whether the user skipped the content
    # completed = Column(Boolean, default=False)  # Whether the user finished watching
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))  # Timestamp of interaction

    user = relationship("User", back_populates="media_interactions")
    media = relationship("Post", back_populates="interactions")