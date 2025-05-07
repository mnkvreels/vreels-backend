from pydantic import BaseModel
from typing import Optional, List, Any
from ..auth.enums import AccountTypeEnum
from ..auth.schemas import UserBase
from datetime import datetime


class Profile(UserBase):
    id: Optional[int] = None
    name: Optional[str] = None
    bio: Optional[str] = None
    profile_pic: Optional[str] = None
    account_type: Optional[AccountTypeEnum] = None
    followers_count: Optional[int] = 0
    following_count: Optional[int] = 0
    suggested_follower_count: Optional[int] = 0
    is_following: bool
    is_blocked: bool
    has_requested: bool   # 🚨 NEW FIELD


    class Config:
        orm_mode = True


class UserSchema(BaseModel):
    user_id: int
    profile_pic: Optional[str] = None
    username: str
    name: Optional[str] = None
    phone_number: int
    follow_back: Optional[bool] = None 

    class Config:
        orm_mode = True




class FollowingList(BaseModel):
    following: list[UserSchema] = []


class FollowersList(BaseModel):
    followers: list[UserSchema] = []
    pending_requests: List[Any] = []


class SuggestedUser(BaseModel):
    id: int
    username: str
    full_name: Optional [str] = None
    profile_picture_url: Optional [str]  = None
    account_type: Optional[AccountTypeEnum] = None  # 👈 Add this
    is_following: bool = False                      # 👈 Add this
    is_requested: bool = False                      # 👈 Add this

class SuggestedUserResponse(BaseModel):
    total_count: int
    suggested_users: list[SuggestedUser]