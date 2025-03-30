from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..database import get_db
from .schemas import Profile, FollowersList, FollowingList
from .service import (
    get_followers_svc,
    get_following_svc,
    follow_svc,
    unfollow_svc,
    check_follow_svc,
    existing_user,
)
from ..auth.service import get_current_user, get_user_by_username
from ..models import User
from ..notification_service import send_push_notification

class UserRequest(BaseModel):
    username: str

router = APIRouter(prefix="/profile", tags=["profile"])

@router.get("/user", response_model=Profile)
async def profile(request: UserRequest, db: Session = Depends(get_db)):
    db_user = await existing_user(db, request.username)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid username"
        )
    return db_user


@router.post("/follow", status_code=status.HTTP_204_NO_CONTENT)
async def follow(request: UserRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_user = current_user
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="invalid token"
        )

    res = await follow_svc(db, db_user.username, request.username)
    if res == False:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="could not follow"
        )
    elif res:
        followed_user = await get_user_by_username(db, request.username)
        
        # Send notification to followed user
        await send_push_notification(
            device_token=followed_user.device_token,
            platform=followed_user.platform,
            title="👥 New Follower!",
            message=f"{current_user.username} is now following you."
        )
        return {"message": "Followed successfully!"}


@router.post("/unfollow", status_code=status.HTTP_204_NO_CONTENT)
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