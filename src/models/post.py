from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Table
from sqlalchemy.orm import relationship, backref
from datetime import datetime, timezone
from src.database import Base

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
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), primary_key=True)
    post = relationship("Post", back_populates="likes")
    user = relationship("User", back_populates="likes")

# Comment Model
class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    post_id = Column(Integer, ForeignKey("posts.id"))
    user_id = Column(Integer, ForeignKey("users.id"))

    post = relationship("Post", back_populates="comments")
    user = relationship("User", back_populates="comments")

# Post Model
class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String)
    media = Column(String)
    location = Column(String)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)

    author_id = Column(Integer, ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")

    # Many-to-Many Relationships
    liked_by_users = relationship("User", secondary="post_likes", back_populates="liked_posts")
    hashtags = relationship("Hashtag", secondary="post_hashtags", back_populates="posts")

    # One-to-Many Relationships
    likes = relationship("Like", back_populates="post", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    share_count = Column(Integer, default=0)
    saved_by_users = relationship("UserSavedPosts", back_populates="post", cascade="all, delete")
    shared_by_users = relationship("UserSharedPosts", back_populates="post", cascade="all, delete")
    
    def update_likes_and_comments_count(self, db_session):
        self.likes_count = db_session.query(Like).filter(Like.post_id == self.id).count()
        self.comments_count = db_session.query(Comment).filter(Comment.post_id == self.id).count()

# Hashtag Model
class Hashtag(Base):
    __tablename__ = "hashtags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True)

    posts = relationship("Post", secondary="post_hashtags", back_populates="hashtags")

class UserSavedPosts(Base):
    __tablename__ = "user_saved_posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    saved_post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))  # Metadata column

    # Relationships
    user = relationship("User", back_populates="saved_posts")
    post = relationship("Post", back_populates="saved_by_users")

class UserSharedPosts(Base):
    __tablename__ = "user_shared_posts"

    id = Column(Integer, primary_key=True, index=True)
    sender_user_id = Column(Integer, ForeignKey("users.id", ondelete="NO ACTION"), nullable=False)
    receiver_user_id = Column(Integer, ForeignKey("users.id", ondelete="NO ACTION"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    sender = relationship("User", foreign_keys=[sender_user_id], back_populates="shared_posts_sent")
    receiver = relationship("User", foreign_keys=[receiver_user_id], back_populates="shared_posts_received")
    post = relationship("Post", back_populates="shared_by_users")