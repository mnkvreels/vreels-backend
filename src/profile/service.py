from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models.user import User, Follow, FollowRequest, BlockedUsers
from ..models.activity import Activity
from .schemas import FollowersList, FollowingList, Profile
from ..auth.service import get_user_from_user_id, existing_user


# follow
async def follow_svc(db: Session, follower: str, following: str):
    if follower == following:
        raise HTTPException(status_code=400, detail="You cannot follow yourself.")

    # ✅ Get session-bound user objects
    db_follower = db.query(User).filter(User.username == follower).first()
    db_following = db.query(User).filter(User.username == following).first()

    if not db_follower or not db_following:
        raise HTTPException(status_code=404, detail="User not found")

    existing = db.query(Follow).filter_by(
        follower_id=db_follower.id,
        following_id=db_following.id
    ).first()

    if existing:
        return {"message": "Already following"}

    try:
        # ✅ Create follow
        follow = Follow(follower_id=db_follower.id, following_id=db_following.id)
        db.add(follow)
        db.flush()

        # ✅ Recalculate counts from fresh DB values
        follower_count = db.query(Follow).filter(Follow.follower_id == db_follower.id).count()
        following_count = db.query(Follow).filter(Follow.following_id == db_following.id).count()

        # ✅ Force SQLAlchemy to detect changes
        db.query(User).filter(User.id == db_follower.id).update({"following_count": follower_count})
        db.query(User).filter(User.id == db_following.id).update({"followers_count": following_count})

        db.commit()
        return {"message": "Followed successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Follow failed: {e}")


# unfollow activity
async def unfollow_svc(db: Session, follower: str, following: str):
    if follower == following:
        raise HTTPException(status_code=400, detail="You cannot unfollow yourself.")

    db_follower = db.query(User).filter(User.username == follower).first()
    db_following = db.query(User).filter(User.username == following).first()

    if not db_follower or not db_following:
        raise HTTPException(status_code=404, detail="User not found")

    existing = db.query(Follow).filter_by(
        follower_id=db_follower.id,
        following_id=db_following.id
    ).first()

    if not existing:
        raise HTTPException(status_code=400, detail="You are not following this user.")

    try:
        db.delete(existing)
        db.flush()

        # ✅ Recalculate counts
        follower_count = db.query(Follow).filter(Follow.follower_id == db_follower.id).count()
        following_count = db.query(Follow).filter(Follow.following_id == db_following.id).count()

        # ✅ Update directly in DB (ensures update is detected)
        db.query(User).filter(User.id == db_follower.id).update({"following_count": follower_count})
        db.query(User).filter(User.id == db_following.id).update({"followers_count": following_count})

        db.commit()
        return {"message": "Unfollowed successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unfollow failed: {e}")


'''
# get followers
async def get_followers_svc(db: Session, user_id: int) -> FollowersList:
    db_user = await get_user_from_user_id(db, user_id)
    if not db_user:
        return FollowersList(followers=[])

    try:
        # Get users who follow the current user
        db_followers = (
            db.query(User)
            .join(Follow, Follow.follower_id == User.id)
            .filter(Follow.following_id == user_id)
            .distinct(User.id)
            .all()
        )

    except Exception:
        raise HTTPException(status_code=500, detail="Database error")

    followers = []
    for follower in db_followers:
        # Check if current user is following this follower (follow back)
        is_following_back = (
            db.query(Follow)
            .filter(
                Follow.follower_id == user_id,
                Follow.following_id == follower.id
            )
            .first()
            is not None
        )

        followers.append(
            {
                "user_id": follower.id,
                "profile_pic": follower.profile_pic,
                "name": follower.name,
                "username": follower.username,
                "phone_number": follower.phone_number,
                "follow_back": not is_following_back,  # True if you’re NOT following them
            }
        )



    return FollowersList(followers=followers)

'''

async def get_followers_svc(db: Session, user_id: int) -> FollowersList:
    try:
        db_user = await get_user_from_user_id(db, user_id)
        if not db_user:
            return FollowersList()

        # Followers
        db_followers = (
            db.query(User)
            .join(Follow, Follow.follower_id == User.id)
            .filter(Follow.following_id == user_id)
            .distinct(User.id)
            .all()
        )

        # Pending requests
        db_requests = (
            db.query(FollowRequest)
            .filter(FollowRequest.target_id == user_id)
            .all()
        )

        followers = []
        for follower in db_followers:
            is_following_back = (
                db.query(Follow)
                .filter(
                    Follow.follower_id == user_id,
                    Follow.following_id == follower.id
                )
                .first()
                is not None
            )

            followers.append({
                "user_id": follower.id,
                "profile_pic": follower.profile_pic,
                "name": follower.name,
                "username": follower.username,
                "phone_number": follower.phone_number,
                "follow_back": not is_following_back
            })

        # Use dicts instead of FollowRequestItem
        pending_requests = []
        for r in db_requests:
            if not r.requester:
                continue  # skip if relationship is broken

            pending_requests.append({
                "requester_id": r.requester.id,
                "requester_username": r.requester.username,
                "requester_profile_pic": r.requester.profile_pic,
                "created_at": str(r.created_at)  # make it JSON-safe
            })

        return FollowersList(
            followers=followers,
            pending_requests=pending_requests
        )

    except Exception as e:
        print("❌ Error in get_followers_svc:", e)
        raise HTTPException(status_code=500, detail="Database error")


# get following
async def get_following_svc(db: Session, user_id: int) -> list[FollowingList]:
    db_user = await get_user_from_user_id(db, user_id)
    if not db_user:
        return []

    try:
        # Avoid duplicates by selecting distinct `following_id`
        db_following = (
            db.query(User)
            .join(Follow, Follow.following_id == User.id)
            .filter(Follow.follower_id == user_id)
            .distinct(User.id)  # This ensures no duplicate users
            .all()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database error")

    # Prepare the response with distinct following users
    following = []
    for user in db_following:
        following.append(
            {
                "user_id": user.id,
                "profile_pic": user.profile_pic,
                "name": user.name,
                "username": user.username,
                "phone_number": user.phone_number,
            }
        )

    return FollowingList(following=following)


async def check_follow_svc(db: Session, current_user: str, user: str):
    db_follower = await existing_user(db, current_user, "")
    db_following = await existing_user(db, user, "")
    if not db_follower or not db_following:
        return False
    db_following = (
        db.query(Follow)
        .filter_by(follower_id=db_follower.id, following_id=db_following.id)
        .first()
    )
    if db_following:
        return True
    return False

async def get_suggested_users_svc(db: Session, user_id: int, limit: int = 10):
    try:
        # First-degree connections (people the user is already following)
        following_ids = db.query(Follow.following_id).filter(Follow.follower_id == user_id).all()
        following_ids = [fid[0] for fid in following_ids]

        # 🔒 Get all users blocked by or blocking this user
        blocked_ids = set(
            row[0] for row in db.query(BlockedUsers.blocked_id)
            .filter(BlockedUsers.blocker_id == user_id)
        ).union(
            row[0] for row in db.query(BlockedUsers.blocker_id)
            .filter(BlockedUsers.blocked_id == user_id)
        )

        # Scenario 1: Friends-of-Friends
        second_degree_users = (
            db.query(User)
            .join(Follow, Follow.following_id == User.id)
            .filter(
                Follow.follower_id.in_(following_ids),
                Follow.following_id != user_id,
                ~Follow.following_id.in_(following_ids),
                ~User.id.in_(blocked_ids)  # ✅ Exclude blocked users
            )
            .distinct(User.id)
        )

        # Scenario 2: People who follow current user but user is not following back
        followers_not_followed_back = (
            db.query(User)
            .join(Follow, Follow.follower_id == User.id)
            .filter(
                Follow.following_id == user_id,
                ~Follow.follower_id.in_(following_ids),
                Follow.follower_id != user_id,
                ~User.id.in_(blocked_ids)  # ✅ Exclude blocked users
            )
            .distinct(User.id)
        )

        # Combine both queries using union
        #combined = second_degree_users.union(followers_not_followed_back).limit(limit).all()
        # Combine both
        combined_query = second_degree_users.union(followers_not_followed_back).distinct(User.id)

        # ✅ Get total count first (before limiting)
        total_count = combined_query.count()

        # ✅ Get limited results
        combined_results = combined_query.limit(limit).all()

        # Build response
        suggestions = []
        for user in combined_results:
            # Check if follow request is pending
            is_requested = db.query(FollowRequest).filter_by(
                requester_id=user_id,
                target_id=user.id
            ).first() is not None

            # Check if already following
            is_following = db.query(Follow).filter_by(
                follower_id=user_id,
                following_id=user.id
            ).first() is not None

            suggestions.append({
                "id": user.id,
                "username": user.username,
                "full_name": user.name,
                "profile_picture_url": user.profile_pic,
                "account_type": user.account_type,
                "is_following": is_following,
                "is_requested": is_requested
            })


        return {
            "total_count": total_count,
            "suggested_users": suggestions
        }
        '''
        # Final suggestion list
        suggestions = []
        for user in combined:
            suggestions.append({
                "id": user.id,
                "username": user.username,
                "full_name": user.name,
                "profile_picture_url": user.profile_pic
            })

        return suggestions
        '''

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch suggestions: {str(e)}")
    