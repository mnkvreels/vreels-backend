from pydantic import BaseModel
from typing import Optional
from ..auth.enums import AccountTypeEnum
from ..auth.schemas import UserBase


class Profile(UserBase):
    id: Optional[int] = None
    name: Optional[str] = None
    bio: Optional[str] = None
    profile_pic: Optional[str] = None
    account_type: Optional[AccountTypeEnum] = None
    followers_count: Optional[int] = 0
    following_count: Optional[int] = 0

    class Config:
        orm_mode = True


class UserSchema(BaseModel):
    user_id: int
    profile_pic: Optional[str] = None
    username: str
    name: Optional[str] = None

    class Config:
        orm_mode = True


class FollowingList(BaseModel):
    following: list[UserSchema] = []


class FollowersList(BaseModel):
    followers: list[UserSchema] = []


class SuggestedUser(BaseModel):
    id: int
    username: str
    full_name: Optional [str] = None
    profile_picture_url: Optional [str]  = None