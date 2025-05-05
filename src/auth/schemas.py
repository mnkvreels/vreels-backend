from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, List
from .enums import GenderEnum, AccountTypeEnum

# Base class for user data with essential fields
class UserBase(BaseModel):
    """
    UserBase class is a base model for representing a user's basic information
    such as email and username.
    """
    phone_number: int  # User's phone number
    username: str # User's username
    
    class Config:
        arbitrary_types_allowed = True 


# Class for creating a new user, inheriting from UserBase
class UserCreate(UserBase):
    """
    UserCreate class is used when creating a new user, adding the password field.
    """
    # password: str  # User's password (to be hashed later)


# Class for updating user profile information, inheriting from BaseModel
class UserUpdate(BaseModel):
    """
    UserUpdate class represents the fields that can be updated for a user.
    All fields are optional for partial updates.
    """
    username: Optional[str] = None
    name: Optional[str] = None  # User's full name (optional)
    dob: Optional[date] = None  # User's date of birth (optional)
    gender: Optional[GenderEnum] = None  # User's gender (optional)
    bio: Optional[str] = None  # User's bio (optional)
    email: Optional[str] = None # User's email
    location: Optional[str] = None  # User's location (optional)
    profile_pic: Optional[str] = None  # Link to user's profile picture (optional)
    phone_number: Optional[int]
    account_type: Optional[AccountTypeEnum] = None
    followers_count: Optional[int]
    following_count: Optional[int]
    suggested_follower_count: Optional[int] = 0


# Full user profile including the created date and ID, combining UserBase and UserUpdate
class User(UserBase, UserUpdate):
    """
    User class is a complete user profile including all user details.
    Inherits from UserBase and UserUpdate to combine both basic and update fields.
    """
    id: int  # Unique ID for the user
    created_at: datetime  # Timestamp of when the user account was created
    is_active: bool
    is_verified: bool # For email verification

    class Config:
        # Tells Pydantic to treat this model as an ORM model (SQLAlchemy)
        orm_mode = True
        
# class VerifyOTPRequest(BaseModel):
#     phone_number: str
#     otp: str

# # Request OTP for Password Reset
# class ResetPasswordRequest(BaseModel):
#     phone_number: str

# # Verify OTP and Set New Password
# class ResetPasswordVerify(BaseModel):
#     phone_number: str
#     otp: str
#     new_password: str

class UserIdRequest(BaseModel):
    user_id: Optional[int]
    username: Optional[str]
    
class DeviceTokenRequest(BaseModel):
    device_id: str
    device_token: str
    platform: str  # iOS or Android
    
class UpdateNotificationFlagsRequest(BaseModel):
    device_id: str
    notify_likes: Optional[bool]
    notify_comments: Optional[bool]
    notify_share: Optional[bool]
    notify_calls: Optional[bool]
    notify_messages: Optional[bool]
    notify_follow: Optional[bool]
    notify_posts: Optional[bool]
    notify_status: Optional[bool]
    sync_contacts: Optional[bool]
    
class ContactIn(BaseModel):
    name: str
    phone_number: str

class ToggleContactsSyncRequest(BaseModel):
    device_id: str
    sync_contacts: bool
    contacts: List[ContactIn] = []