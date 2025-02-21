from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Table
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from src.database import Base
import importlib

# In src/auth/models.py or src/post/models.py
def get_user_model():
    user_model = importlib.import_module('src.auth.models')
    return user_model.User

# Post-Hashtag Relationship
post_hashtags = Table(
    "post_hashtags",
    Base.metadata,
    Column("post_id", Integer, ForeignKey("Posts.id")),
    Column("hashtag_id", Integer, ForeignKey("Hashtags.id")),
)

# Likes model  (Tracking who liked the post)
class Like(Base):
    __tablename__ = "Likes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("Users.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("Posts.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    # Relationship back to the User model
    user = relationship("User", backref="likes")  # Use backref here instead of back_populates

    # Relationship back to the Post model
    post = relationship("Post", back_populates="liked_by_users")



# Comment Model
class Comment(Base):
    __tablename__ = "Comments"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)  # Content of the comment
    created_at = Column(DateTime, default=datetime.now(timezone.utc))  # Timestamp for when the comment was created

    post_id = Column(Integer, ForeignKey("Posts.id"))  # Reference to the post the comment belongs to
    user_id = Column(Integer, ForeignKey("Users.id"))  # Reference to the user who made the comment

    post = relationship("Post", back_populates="comments")
    user = relationship("auth.models.User", back_populates="comments")


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

    hashtags = relationship("Hashtag", secondary=post_hashtags, back_populates="Posts")

    # Relationship for liked users
    liked_by_users = relationship(
        "User", secondary="Likes", back_populates="liked_posts"
    )

    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")

    def update_likes_and_comments_count(self, db_session):
        self.likes_count = len(db_session.query(Like).filter(Like.c.post_id == self.id).all())
        self.comments_count = len(db_session.query(Comment).filter(Comment.post_id == self.id).all())


# Hashtag Model
class Hashtag(Base):
    __tablename__ = "Hashtags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)

    posts = relationship("Post", secondary=post_hashtags, back_populates="Hashtags")
    
