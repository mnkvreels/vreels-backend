from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models.user import User, Follow
from ..models.activity import Activity
from .schemas import FollowersList, FollowingList, Profile
from ..auth.service import get_user_from_user_id, existing_user


# follow
async def follow_svc(db: Session, follower: str, following: str):
    db_follower = await existing_user(db, follower, "")
    db_following = await existing_user(db, following, "")
    if not db_follower or not db_following:
        return False

    db_follow = (
        db.query(Follow)
        .filter_by(follower_id=db_follower.id, following_id=db_following.id)
        .first()
    )
    if db_follow:
        return False

    db_follow = Follow(follower_id=db_follower.id, following_id=db_following.id)
    db.add(db_follow)

    db_follower.following_count += 1
    db_following.followers_count += 1

    follow_activity = Activity(
        username=following,
        followed_username=db_follower.username,
        followed_user_pic=db_follower.profile_pic,
    )
    db.add(follow_activity)

    db.commit()


# unfollow activity
async def unfollow_svc(db: Session, follower: str, following: str):
    db_follower = await existing_user(db, follower, "")
    db_following = await existing_user(db, following, "")
    if not db_follower or not db_following:
        return False

    db_follow = (
        db.query(Follow)
        .filter_by(follower_id=db_follower.id, following_id=db_following.id)
        .first()
    )
    if not db_follow:
        return False

    db.delete(db_follow)

    db_follower.following_count -= 1
    db_following.followers_count -= 1

    db.commit()


# get followers
async def get_followers_svc(db: Session, user_id: int) -> list[FollowersList]:
    db_user = await get_user_from_user_id(db, user_id)
    if not db_user:
        return []

    try:
        db_followers = (
            db.query(Follow)
            .filter(Follow.following_id == user_id)
            .join(User, User.id == Follow.follower_id)
            .all()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database error")

    followers = []
    for follow in db_followers:
        followers.append(
            {
                "profile_pic": follow.follower_user.profile_pic,
                "name": follow.follower_user.name,
                "username": follow.follower_user.username,
            }
        )

    return {"Followers": FollowersList(followers=followers) , "db_followers": db_followers }


# get following
async def get_following_svc(db: Session, user_id: int) -> list[FollowingList]:
    db_user = await get_user_from_user_id(db, user_id)
    if not db_user:
        return []

    try:
        db_followers = (
            db.query(Follow)
            .filter(Follow.follower_id == user_id)
            .join(User, User.id == Follow.following_id)
            .all()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database error")

    following = []
    for follow in db_followers:
        following.append(
            {
                "profile_pic": follow.following_user.profile_pic,
                "name": follow.following_user.name,
                "username": follow.following_user.username,
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