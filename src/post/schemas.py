from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


# Pydantic model for Hashtag
class Hashtag(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


# Pydantic model for Comment
class Comment(BaseModel):
    id: int
    content: str
    created_at: datetime
    user_id: int
    post_id: int

    class Config:
        orm_mode = True


# Pydantic model for Like (to represent users who liked the post)
class Like(BaseModel):
    user_id: int
    post_id: int

    class Config:
        orm_mode = True


# Pydantic model for Post creation (when creating a new post)
class PostCreate(BaseModel):
    content: Optional[str] = None
    media: Optional[str] = None
    location: Optional[str] = None

    class Config:
        orm_mode = True


# Pydantic model for Post (when retrieving a post)
class Post(PostCreate):
    id: int
    author_id: int
    likes_count: int
    comments_count: int  # New field for the count of comments
    created_at: datetime
    hashtags: List[Hashtag] = []  # List of Hashtags related to the post
    comments: List[Comment] = []  # List of Comments related to the post
    likes: List[Like] = []  # List of Likes (users who liked the post)

    class Config:
        orm_mode = True
