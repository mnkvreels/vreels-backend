from pydantic import BaseModel
from typing import List, Optional, Union
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

class CommentDeleteRequest(BaseModel):
    post_id: int
    comment_ids: Union[int, List[int]]

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
    thumbnail: Optional[str]
    video_length: Optional[int] = None
    hashtags: Optional[List[str]] = []
    comments_disabled: Optional[bool] = False

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
    comments_disabled: Optional[bool]

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
    
class PostResponse(BaseModel):
    id: int
    content: Optional[str]
    media: Optional[str]
    location: Optional[str]
    created_at: datetime
    visibility: str
    category_of_content: Optional[str]
    media_type: Optional[str]
    thumbnail: Optional[str]
    video_length: Optional[int]
    author_id: int
    likes_count: int
    comments_count: int
    views_count: int
    save_count: int
    share_count: int

    class Config:
        orm_mode = True  # This is critical to allow Pydantic to work with ORM objects

class SeedPexelsRequest(BaseModel):
    category: str = "nature"
    count: int = 5
    include_images: bool = True
    include_videos: bool = True

class DeleteAllCommentsRequest(BaseModel):
    post_id: int
    disable_comments: bool = False  # Optional, defaults to False if not provided

class PouchPreviewRequest(BaseModel):
    name: str
    description: Optional[str] = None
    visibility: VisibilityEnum
    post_ids: Optional[List[int]] = []    # For pre-selecting posts if needed


class PouchCreateRequest(BaseModel):
    name: str
    description: Optional[str]
    visibility: Optional[VisibilityEnum]
    post_ids:Optional[List[int]]

class PouchUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[VisibilityEnum] = None
    new_post_ids: Optional[List[int]] = None
    remove_post_ids: Optional[List[int]]

class PouchRequest(BaseModel):
    pouch_id: int