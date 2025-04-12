from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from .enums import VisibilityEnum, MediaTypeEnum

class PaginationMetadata(BaseModel):
    total_count: int
    total_pages: int
    page: int
    limit: int
    
    class Config:
        orm_mode = True

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
    username: Optional[str]
    created_at: datetime
    user_id: int
    post_id: int
    metadata: PaginationMetadata

    class Config:
        orm_mode = True


# Pydantic model for Like (to represent users who liked the post)
class Like(BaseModel):
    id: int
    created_at: datetime
    username: Optional[str]
    user_id: int
    post_id: int
    metadata: PaginationMetadata
    
    class Config:
        orm_mode = True

# Pydantic model for Post creation (when creating a new post)
class PostCreate(BaseModel):
    content: Optional[str] = None
    media: Optional[str] = None
    location: Optional[str] = None
    visibility: VisibilityEnum = VisibilityEnum.public
    category_of_content: Optional[str]
    media_type: Optional[str]

    class Config:
        orm_mode = True


# Pydantic model for Post (when retrieving a post)
class Post(PostCreate):
    id: int
    author_id: int
    likes_count: int
    comments_count: int  # New field for the count of comments
    created_at: datetime
    hashtags: List[Hashtag] = []  # List of hashtags related to the post
    comments: dict = []  # List of comments related to the post
    likes: dict = []  # List of likes (users who liked the post)

    class Config:
        orm_mode = True
        
class PostUpdate(BaseModel):
    content: Optional[str]
    location: Optional[str]
    visibility: Optional[VisibilityEnum]
    category_of_content: Optional[str]
    views_count: Optional[int]
    media_type: Optional[str]

# Pyndantic model for saving a post (when user tries to save a post)
class SavePostRequest(BaseModel):
    post_id: int
    
class SharePostRequest(BaseModel):
    receiver_user_ids: List[int]  # The user who will receive the post
    post_id: int
    
class MediaInteractionRequest(BaseModel):
    post_id: int
    watched_time: int  # in seconds
    media_type: MediaTypeEnum
    video_length: Optional[int] = 0  # nullable for images