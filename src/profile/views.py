from fastapi import APIRouter, status, Depends, HTTPException, Query
from typing import List
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..database import get_db
from src.models.user import BlockedUsers
from .schemas import Profile, FollowersList, FollowingList, SuggestedUser,SuggestedUserResponse
from .service import (
    get_followers_svc,
    get_following_svc,
    follow_svc,
    unfollow_svc,
    check_follow_svc,
    existing_user,
    get_suggested_users_svc,
)
from ..auth.service import get_current_user, get_user_by_username, send_notification_to_user
from ..models.user import User, UserDevice, Follow
from ..notification_service import send_push_notification
from ..auth.enums import AccountTypeEnum

class UserRequest(BaseModel):
    username: str

class ProfileRequest(BaseModel):
    username: str
    requesting_username: str

router = APIRouter(prefix="/profile", tags=["profile"])

@router.get("/user")
async def profile(request: ProfileRequest, db: Session = Depends(get_db)):
    db_user = await existing_user(db, request.username)
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid username")


    requesting_user = db.query(User).filter(User.username == request.requesting_username).first()
    if not requesting_user:
        raise HTTPException(status_code=404, detail="Requesting user not found")

    # ✅ Check if following
    is_following = db.query(Follow).filter(
        Follow.follower_id == requesting_user.id,
        Follow.following_id == db_user.id
    ).first() is not None

    # ✅ Check if blocked
    is_blocked = db.query(BlockedUsers).filter(
        BlockedUsers.blocker_id == requesting_user.id,
        BlockedUsers.blocked_id == db_user.id
    ).first() is not None

    # ✅ Always calculate this before returning anything
    target_followers_subq = db.query(Follow.follower_id).filter(
        Follow.following_id == db_user.id
    ).subquery()

    suggested_follower_count = db.query(Follow).filter(
        Follow.follower_id == requesting_user.id,
        Follow.following_id.in_(target_followers_subq)
    ).count()

    # ✅ If same user (viewing own profile)
    if requesting_user.id == db_user.id:
        return {
            **db_user.__dict__,
            "is_following": False,
            "is_blocked": False
        }

    # ✅ If private and not following — return limited profile + flags
    if db_user.account_type == AccountTypeEnum.PRIVATE and not is_following:
        return {
            "username": db_user.username,
            "name": db_user.name,
            "profile_pic": db_user.profile_pic,
            "account_type": db_user.account_type,
            "is_private": True,
            "is_following": is_following,
            "is_blocked": is_blocked
        }

    # ✅ Full profile
    return {
        **db_user.__dict__,
        "is_following": is_following,
        "is_blocked": is_blocked
    }




@router.post("/follow", status_code=status.HTTP_200_OK)
async def follow(
    request: UserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_user = current_user
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="invalid token"
        )

    res = await follow_svc(db, db_user.username, request.username)
    if res is False:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="could not follow"
        )
    elif res:
        followed_user = await get_user_by_username(db, request.username)

        # Fetch devices of followed user that allow follow notifications
        devices = db.query(UserDevice).filter(
            UserDevice.user_id == followed_user.id,
            UserDevice.notify_follow == True  # assuming this is the correct column name
        ).all()

        for device in devices:
            if device.device_token and device.platform:
                try:
                    await send_push_notification(
                        device_token=device.device_token,
                        platform=device.platform,
                        title="👥 New Follower!",
                        message=f"{current_user.username} is now following you."
                    )
                except Exception as e:
                    print(f"Notification send failed for device {device.device_id}: {e}")

        return {"message": "Followed successfully!"}


@router.post("/unfollow", status_code=status.HTTP_200_OK)
async def follow(request: UserRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_user = current_user
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="invalid token"
        )

    res = await unfollow_svc(db, db_user.username, request.username)
    if res == False:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="could not follow"
        )
    elif res:
        return {"message": "Unfollowed successfully!"}


@router.get("/followers", response_model=FollowersList)
async def get_followers(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        )
    return await get_followers_svc(db, current_user.id)

@router.get("/userfollowers", response_model=FollowersList)
async def get_followers_by_userid(request: UserRequest, db: Session = Depends(get_db)):
    user = await get_user_by_username(db, request.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        )
    return await get_followers_svc(db, user.id)

@router.get("/following", response_model=FollowingList)
async def get_following(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        )
    return await get_following_svc(db, current_user.id)

@router.get("/userfollowing", response_model=FollowingList)
async def get_following_by_userid(request: UserRequest, db: Session = Depends(get_db)):
    user = await get_user_by_username(db, request.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        )
    return await get_following_svc(db, user.id)



@router.get("/suggested", response_model=SuggestedUserResponse)
async def suggested_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(10)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return await get_suggested_users_svc(db, current_user.id, limit)