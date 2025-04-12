from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models.user import User, Follow
from ..models.activity import Activity
from .schemas import FollowersList, FollowingList, Profile
from ..auth.service import get_user_from_user_id, existing_user


# follow
async def follow_svc(db: Session, follower: str, following: str):
    if follower == following:
        raise HTTPException(status_code=400, detail="You cannot follow yourself.")
    
    db_follower = await existing_user(db, follower, "")
    db_following = await existing_user(db, following, "")
    if not db_follower or not db_following:
        return {"error": "User not found."}

    # Check if the follow relationship already exists
    db_follow = (
        db.query(Follow)
        .filter_by(follower_id=db_follower.id, following_id=db_following.id)
        .first()
    )
    if db_follow:
        # Already following
        return {"message": f"You are already following {db_following.username}."}

    try:
        # Create the follow relationship
        db_follow = Follow(follower_id=db_follower.id, following_id=db_following.id)
        db.add(db_follow)

        # Recalculate follower and following counts dynamically
        db_follower.following_count += 1
        db_following.followers_count += 1

        # Create a follow activity
        follow_activity = Activity(
            username=following,
            followed_username=db_follower.username,
            followed_user_pic=db_follower.profile_pic,
        )
        db.add(follow_activity)

        db.commit()
        return {"message": f"You are now following {db_following.username}."}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error following user: {str(e)}")



# unfollow activity
async def unfollow_svc(db: Session, follower: str, following: str):
    if follower == following:
        raise HTTPException(status_code=400, detail="You cannot unfollow yourself.")
    
    db_follower = await existing_user(db, follower, "")
    db_following = await existing_user(db, following, "")
    if not db_follower or not db_following:
        return {"error": "User not found."}

    # Check if the follow relationship exists
    db_follow = (
        db.query(Follow)
        .filter_by(follower_id=db_follower.id, following_id=db_following.id)
        .first()
    )
    if not db_follow:
        # Not following, return error message
        raise HTTPException(status_code=400, detail=f"You are not following {db_following.username}.")

    try:
        # Remove the follow relationship
        db.delete(db_follow)

        # Recalculate follower and following counts dynamically
        db_follower.following_count -= 1
        db_following.followers_count -= 1

        db.commit()
        return {"message": f"You have unfollowed {db_following.username}."}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error unfollowing user: {str(e)}")



# get followers
async def get_followers_svc(db: Session, user_id: int) -> list[FollowersList]:
    db_user = await get_user_from_user_id(db, user_id)
    if not db_user:
        return []

    try:
        # Fetch followers by joining the Follow table and User table
        db_followers = (
            db.query(User)  # Directly select distinct users
            .join(Follow, Follow.follower_id == User.id)  # Join on the follower ID
            .filter(Follow.following_id == user_id)  # We want the followers of the user
            .distinct(User.id)  # Ensures each follower is unique
            .all()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database error")

    followers = []
    for user in db_followers:
        followers.append(
            {
                "user_id": user.id,
                "profile_pic": user.profile_pic,
                "name": user.name,
                "username": user.username,
            }
        )

    return FollowersList(followers=followers)


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

'''
# Suggested followers (friends-of-friends)
async def get_suggested_users_svc(db: Session, user_id: int, limit: int = 10):
    try:
        # Step 1: Get the users current user is following
        following = (
            db.query(Follow.following_id)
            .filter(Follow.follower_id == user_id)
            .distinct()
            .all()
        )
        following_ids = [f[0] for f in following]
        print(following_ids)
        if not following_ids:
            return []

        # Step 2: Get second-degree connections (users followed by people the user follows)
        second_degree = (
            db.query(User)
            .join(Follow, Follow.following_id == User.id)
            .filter(
                Follow.follower_id.in_(following_ids),
                Follow.following_id != user_id,
                ~Follow.following_id.in_(
                    db.query(Follow.following_id).filter(Follow.follower_id == user_id)
                )
            )
            .distinct(User.id)
            .limit(limit)
            .all()
        )
        print(second_degree)

        suggestions = []
        for user in second_degree:
            suggestions.append({
                "id": user.id,
                "username": user.username,
                "full_name": user.name,
                "profile_picture_url": user.profile_pic
            })

        return suggestions

    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch suggested users.")
'''

async def get_suggested_users_svc(db: Session, user_id: int, limit: int = 10):
    try:
        # First-degree connections (people the user is already following)
        following_ids = db.query(Follow.following_id).filter(Follow.follower_id == user_id).all()
        following_ids = [fid[0] for fid in following_ids]

        # Scenario 1: Friends-of-Friends
        second_degree_users = (
            db.query(User)
            .join(Follow, Follow.following_id == User.id)
            .filter(
                Follow.follower_id.in_(following_ids),
                Follow.following_id != user_id,
                ~Follow.following_id.in_(following_ids)
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
                Follow.follower_id != user_id
            )
            .distinct(User.id)
        )

        # Combine both queries using `union`
        combined = second_degree_users.union(followers_not_followed_back).limit(limit).all()

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

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch suggestions: {str(e)}")
