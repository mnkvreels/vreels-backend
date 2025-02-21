from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime, timezone
from src.database import Base


class Activity(Base):
    # The name of the table in the database
    __tablename__ = "activities"

    # Primary key for the activity entry
    id = Column(Integer, primary_key=True)

    # Username of the activity receiver (who the activity is performed on)
    username = Column(String, nullable=False)  

    # Timestamp when the activity occurs (defaults to current UTC time)
    timestamp = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))

    # Represents the post ID that was liked (if the activity is a like)
    liked_post_id = Column(Integer)
    
    # Represents the post ID that was commented (if the activity is a comment)
    commented_post_id = Column(Integer)

    # The username of the person who liked the post (if applicable)
    username_like = Column(String)
    
    # The username of the person who commented the post (if applicable)
    username_comment = Column(String)

    # The image of the liked post (if applicable)
    liked_post_image = Column(String)
    
    # The image of the commented post (if applicable)
    commented_post_image = Column(String)

    # Username of the user who followed the activity receiver (if applicable)
    followed_username = Column(String)  

    # Profile picture of the user who followed the activity receiver
    followed_user_pic = Column(String)

