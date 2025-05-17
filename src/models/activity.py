from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime, timezone
from src.database import Base

class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False)  
    timestamp = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))

    liked_post_id = Column(Integer)   # ID of liked post (if applicable)
    liked_pouch_id = Column(Integer)
    commented_post_id = Column(Integer)   # ID of commented post (if applicable)

    username_like = Column(String)  # User who liked the post
    username_comment = Column(String)  # User who commented

    liked_media = Column(String)  # Image of liked post
    commented_media = Column(String)  # Image of commented post

    followed_username = Column(String)  # Username of the user who followed
    followed_user_pic = Column(String)  # Profile pic of the followed user
