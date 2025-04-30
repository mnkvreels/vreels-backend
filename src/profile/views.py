from fastapi import APIRouter, status, Depends, HTTPException, Query
from typing import List
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..database import get_db
from src.models.user import BlockedUsers, FollowRequest
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

class CancelRequestInput(BaseModel):
    username: str  # target user to whom follow request was sent

router = APIRouter(prefix="/profile", tags=["profile"])

@router.get("/user")
async def profile(request: ProfileRequest, db: Session = Depends(get_db)):
    # ✅ Fetch both users at once
    db_users = db.query(User).filter(
        User.username.in_([request.username, request.requesting_username])
    ).all()

    user_map = {u.username: u for u in db_users}
    db_user = user_map.get(request.username)
    requesting_user = user_map.get(request.requesting_username)

    if not db_user or not requesting_user:
        raise HTTPException(status_code=404, detail="User(s) not found")

    # ✅ Check if following
    is_following = db.query(Follow).filter(
        Follow.follower_id == requesting_user.id,
        Follow.following_id == db_user.id
    ).first() is not None

    # ✅ Check if db_user follows requesting_user (mutual follow)
    is_follows = db.query(Follow).filter(
        Follow.follower_id == db_user.id,
        Follow.following_id == requesting_user.id
    ).first() is not None

    # ✅ Check if follow request is pending (is_requested)
    is_requested = db.query(FollowRequest).filter_by(
        requester_id=requesting_user.id,
        target_id=db_user.id
    ).first() is not None

    # ✅ Check if db_user received a request from requesting_user
    is_requested_to_me = db.query(FollowRequest).filter_by(
        requester_id=db_user.id,
        target_id=requesting_user.id
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
            "is_blocked": False,
            "is_requested": False,
            "is_requested_to_me": False,
            "is_follows": False
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
            "is_blocked": is_blocked,
            "is_requested": is_requested,
            "is_requested_to_me": is_requested_to_me,
            "is_follows": is_follows
        }

    # ✅ Full profile
    return {
        **db_user.__dict__,
        "is_following": is_following,
        "is_blocked": is_blocked,
        "is_requested": is_requested,
        "is_requested_to_me": is_requested_to_me,
        "is_follows": is_follows
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
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid token"
        )

    target_user = await get_user_by_username(db, request.username)
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    # ✅ Check if already following
    existing_follow = db.query(Follow).filter_by(
        follower_id=db_user.id,
        following_id=target_user.id
    ).first()

    if existing_follow:
        return {"status": "already_following", "message": "Already following"}

    # ✅ If private, create follow request
    if target_user.account_type == AccountTypeEnum.PRIVATE:
        # Check if already requested
        existing_request = db.query(FollowRequest).filter_by(
            requester_id=db_user.id,
            target_id=target_user.id
        ).first()
        if existing_request:
            return {"status": "pending", "message": "Follow request already sent"}

        follow_request = FollowRequest(requester_id=db_user.id, target_id=target_user.id)
        db.add(follow_request)
        db.commit()

        # (Optional) Send notification to target user
        devices = db.query(UserDevice).filter(
            UserDevice.user_id == target_user.id,
            UserDevice.notify_follow == True
        ).all()

        for device in devices:
            if device.device_token and device.platform:
                try:
                    await send_push_notification(
                        device_token=device.device_token,
                        platform=device.platform,
                        title="🔔 New Follow Request",
                        message=f"{current_user.username} requested to follow you."
                    )
                except Exception as e:
                    print(f"Notification send failed for device {device.device_id}: {e}")

        return {"status": "pending", "message": "Follow request sent"}

    # ✅ If public, direct follow
    res = await follow_svc(db, db_user.username, request.username)
    if res is False:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Could not follow"
        )
    elif res:
        followed_user = await get_user_by_username(db, request.username)

        # Fetch devices of followed user that allow follow notifications
        devices = db.query(UserDevice).filter(
            UserDevice.user_id == followed_user.id,
            UserDevice.notify_follow == True
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

        return {"status": "success", "message": "Followed successfully"}

@router.post("/follow-requests/accept", status_code=status.HTTP_200_OK)
async def accept_follow_request(
    request: UserRequest,  # { "username": "requester_username" }
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    target_user = current_user

    # Get the follow request
    requester = await get_user_by_username(db, request.username)
    if not requester:
        raise HTTPException(status_code=404, detail="Requester not found")

    follow_request = db.query(FollowRequest).filter_by(
        requester_id=requester.id,
        target_id=target_user.id
    ).first()

    if not follow_request:
        raise HTTPException(status_code=404, detail="Follow request not found")

    # Accept: Create follow
    await follow_svc(db, requester.username, target_user.username)

    # Delete the follow request
    db.delete(follow_request)
    db.commit()

    return {"message": "Follow request accepted"}

@router.post("/follow-requests/reject", status_code=status.HTTP_200_OK)
async def reject_follow_request(
    request: UserRequest,  # { "username": "requester_username" }
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    target_user = current_user

    requester = await get_user_by_username(db, request.username)
    if not requester:
        raise HTTPException(status_code=404, detail="Requester not found")

    follow_request = db.query(FollowRequest).filter_by(
        requester_id=requester.id,
        target_id=target_user.id
    ).first()

    if not follow_request:
        raise HTTPException(status_code=404, detail="Follow request not found")

    db.delete(follow_request)
    db.commit()

    return {"message": "Follow request rejected"}


@router.get("/follow-requests/pending", status_code=status.HTTP_200_OK)
async def pending_follow_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    requests = db.query(FollowRequest).filter(
        FollowRequest.target_id == current_user.id
    ).all()

    return [{
        "requester_id": r.requester.id,
        "requester_username": r.requester.username,
        "requester_profile_pic": r.requester.profile_pic,
        "created_at": r.created_at
    } for r in requests]


@router.delete("/follow-requests/cancel", status_code=status.HTTP_200_OK)
async def cancel_follow_request(
    request: CancelRequestInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Get the user you originally sent the request to
    target_user = await get_user_by_username(db, request.username)
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    # Find the pending request
    follow_request = db.query(FollowRequest).filter_by(
        requester_id=current_user.id,
        target_id=target_user.id
    ).first()

    if not follow_request:
        raise HTTPException(
            status_code=404, detail="No pending follow request found"
        )

    # Delete the request
    db.delete(follow_request)
    db.commit()

    return {"message": "Follow request cancelled successfully."}


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