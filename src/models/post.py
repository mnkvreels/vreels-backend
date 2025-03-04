from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Table
from sqlalchemy.orm import relationship, backref
from datetime import datetime, timezone
from src.database import Base

# Many-to-Many Association Table (Users ↔ Liked Posts)
post_likes = Table(
    "post_likes", Base.metadata,
    Column("user_id", Integer, ForeignKey("Users.id", ondelete="CASCADE"), primary_key=True),
    Column("post_id", Integer, ForeignKey("Posts.id", ondelete="CASCADE"), primary_key=True)
)

# Many-to-Many Association Table (Posts ↔ Hashtags)
post_hashtags = Table(
    "post_hashtags",
    Base.metadata,
    Column("post_id", Integer, ForeignKey("Posts.id")),
    Column("hashtag_id", Integer, ForeignKey("Hashtags.id"))
)

# Likes model (Tracks who liked which post)
class Like(Base):
    __tablename__ = "Likes"

    user_id = Column(Integer, ForeignKey("Users.id"), primary_key=True)
    post_id = Column(Integer, ForeignKey("Posts.id"), primary_key=True)

# Comment Model
class Comment(Base):
    __tablename__ = "Comments"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    post_id = Column(Integer, ForeignKey("Posts.id"))
    user_id = Column(Integer, ForeignKey("Users.id"))

    post = relationship("Post", back_populates="comments")
    user = relationship("User", back_populates="comments")

# Post Model
class Post(Base):
    __tablename__ = "Posts"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String)
    media = Column(String)
    location = Column(String)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)

    author_id = Column(Integer, ForeignKey("Users.id"))
    author = relationship("User", back_populates="posts")

    # Many-to-Many Relationships
    liked_by_users = relationship("User", secondary="post_likes", back_populates="liked_posts")
    hashtags = relationship("Hashtag", secondary="post_hashtags", back_populates="posts")

    # One-to-Many Relationships
    likes = relationship("Like", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")

    def update_likes_and_comments_count(self, db_session):
        self.likes_count = db_session.query(Like).filter(Like.post_id == self.id).count()
        self.comments_count = db_session.query(Comment).filter(Comment.post_id == self.id).count()

# Hashtag Model
class Hashtag(Base):
    __tablename__ = "Hashtags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True)

    posts = relationship("Post", secondary="post_hashtags", back_populates="hashtags")
