from sqlalchemy.orm import Session, joinedload, aliased
from sqlalchemy.sql import case
import re
import math
from typing import Union, Optional
from sqlalchemy import desc, func, select
from fastapi import HTTPException
from .schemas import PostCreate, Post as PostSchema, Hashtag as HashtagSchema, SharePostRequest
from ..models.post import Post, Hashtag, post_hashtags, Comment, UserSavedPosts, UserSharedPosts, Like, post_likes
from ..models.user import User, Follow, FollowRequest, BlockedUsers
from ..auth.schemas import User as UserSchema
from ..models.post import VisibilityEnum
from ..models.activity import Activity
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

# create hashtag from posts' content
# hey #fun
async def create_hashtags_svc(db: Session, post: Post):
    if post.content:
        regex = r"#\w+"
        matches = re.findall(regex, post.content)

        for match in matches:
            name = match[1:]

            hashtag = db.query(Hashtag).filter(Hashtag.name == name).first()
            if not hashtag:
                hashtag = Hashtag(name=name)
                db.add(hashtag)
                db.commit()
            post.hashtags.append(hashtag)
    else:
        matches = []


# create post
async def create_post_svc(db: Session, post: PostCreate, user_id: int, file_url: str):
    # check if user_id is valid
    db_post = Post(
        content=post.content,
        media=file_url,
        location=post.location,
        author_id=user_id,
        visibility=post.visibility,
        category_of_content=post.category_of_content,
        media_type=post.media_type,
        thumbnail= post.thumbnail,
        video_length=post.video_length,
    )

    await create_hashtags_svc(db, db_post)

    db.add(db_post)
    db.commit()
    db.refresh(db_post)  # Refresh to get the updated post instance with generated id and relationships
    db_post.update_likes_and_comments_count(db)  # Update likes and comments count for the post

    db.commit()  # Commit after updating the counts
    return db_post


# get user's posts
async def get_user_posts_svc(
    db: Session,
    user_id: int,
    current_user: Optional[User],
    page: int,
    limit: int
) -> dict:
    # Calculate the offset for pagination
    offset = (page - 1) * limit

    # Base query: Fetch posts by the specified user
    posts_query = db.query(Post).filter(Post.author_id == user_id)

    # Apply visibility filters
    if not current_user or current_user.id != user_id:
        # If the current user is not the owner, show only public posts
        posts_query = posts_query.filter(Post.visibility == "public")

    # Block check
    if current_user and current_user.id != user_id:
        blocked = db.query(BlockedUsers).filter(
            ((BlockedUsers.blocker_id == current_user.id) & (BlockedUsers.blocked_id == user_id)) |
            ((BlockedUsers.blocker_id == user_id) & (BlockedUsers.blocked_id == current_user.id))
        ).first()

        if blocked:
            raise HTTPException(status_code=403, detail="Posts from this user are not accessible.")

    # Count total posts after applying visibility filters
    total_count = posts_query.count()

    # Handle case where offset exceeds total count
    if offset >= total_count:
        return {
            "total_count": total_count,
            "page": page,
            "limit": limit,
            "total_pages": (total_count + limit - 1) // limit,
            "data": [],
        }

    # Fetch posts with pagination
    posts = (
        posts_query
        .order_by(desc(Post.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )

    result = []
    for post in posts:
        #Get dynamic attributes like 'username'. 'hashtgas', and check likes/saves
        post_dict = post.__dict__.copy()  # Get all fields dynamically
        # Add dynamic relationships like 'username' (author) and 'hashtags'
        post_dict["username"] = post.author.username if post.author else None
        post_dict["hashtags"] = [hashtag.name for hashtag in post.hashtags] if post.hashtags else []

        # Update likes and comments count dynamically
        post.update_likes_and_comments_count(db)

        # Check if the current user liked or saved the post
        if current_user:
            post_dict["is_liked"] = db.query(Like).filter(
                Like.user_id == current_user.id,
                Like.post_id == post.id
            ).first() is not None
        
     # Check if the user saved the post
            post_dict["is_saved"] = db.query(UserSavedPosts).filter(
                UserSavedPosts.user_id == current_user.id,
                UserSavedPosts.saved_post_id == post.id
            ).first() is not None
        else:
            post_dict["is_liked"] = False
            post_dict["is_saved"] = False

        result.append(post_dict)
        #Return the final paginated result
    return {
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit,
        "data": result,
    }



# get posts from a hashtag
async def get_posts_from_hashtag_svc(
    current_user: User, db: Session, page: int, limit: int, hashtag_name: str
):
    hashtag = db.query(Hashtag).filter_by(name=hashtag_name).first()
    if not hashtag:
        return {"total_count": 0, "page": page, "limit": limit, "total_pages": 0, "data": []}

    offset = (page - 1) * limit

    # Alias for follow relation to check "friends-only" visibility
    FollowerAlias = aliased(Follow)

    base_query = (
        db.query(Post)
        .join(post_hashtags)
        .join(Hashtag)
        .filter(Hashtag.name == hashtag_name)
        .join(User, Post.author_id == User.id)
        .outerjoin(
            FollowerAlias,
            (FollowerAlias.following_id == Post.author_id) & (FollowerAlias.follower_id == current_user.id)
        )
        .filter(
            (Post.visibility == "public") |
            ((Post.visibility == "friends") & (FollowerAlias.follower_id != None)) |
            ((Post.visibility == "private") & (Post.author_id == current_user.id))
        )
    )

    total_count = base_query.count()

    if offset >= total_count:
        return {
            "total_count": total_count,
            "page": page,
            "limit": limit,
            "total_pages": (total_count + limit - 1) // limit,
            "data": [],
        }

    posts = (
        base_query
        .order_by(Post.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    result = []
    for post in posts:
        post_dict = post.__dict__.copy()

        post_dict["username"] = post.author.username if post.author else "Unknown"
        post_dict["hashtags"] = [tag.name for tag in post.hashtags] if post.hashtags else []

        post_dict["is_liked"] = db.query(Like).filter(
            Like.user_id == current_user.id, Like.post_id == post.id
        ).first() is not None

        post_dict["is_saved"] = db.query(UserSavedPosts).filter(
            UserSavedPosts.user_id == current_user.id,
            UserSavedPosts.saved_post_id == post.id,
        ).first() is not None

        post.update_likes_and_comments_count(db)

        result.append(post_dict)

    return {
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit,
        "data": result,
    }


# get random posts for feed
# return latest posts of all users
async def get_random_posts_svc(
    current_user: User, db: Session, page: int, limit: int, hashtag: str = None
):
    total_count = db.query(Post).count()

    offset = (page - 1) * limit
    if offset >= total_count:
        return []

    # 🔒 Get all blocked or blocking users
    blocked_user_ids = set(
        row[0] for row in db.query(BlockedUsers.blocked_id).filter(BlockedUsers.blocker_id == current_user.id)
    ).union(
        row[0] for row in db.query(BlockedUsers.blocker_id).filter(BlockedUsers.blocked_id == current_user.id)
    )

    # Alias for Follow table
    FollowerAlias = aliased(Follow)

    posts_query = (
        db.query(Post, User.username, User.account_type)
        .join(User, Post.author_id == User.id)
        .outerjoin(FollowerAlias, (FollowerAlias.following_id == Post.author_id) & (FollowerAlias.follower_id == current_user.id))  # Check if user follows the author
        .filter(~Post.author_id.in_(blocked_user_ids))
        .filter(Post.visibility != "private")  # ❌ Always exclude 'private' visibility
        .filter(
            (User.account_type != "private")  # ✅ Public accounts
            | (FollowerAlias.follower_id != None)  # ✅ Private accounts → must follow them
            | (Post.author_id == current_user.id)  # ✅ Always show your own posts
        )
        #.order_by(desc(Post.created_at))
    )

    if hashtag:
        posts_query = posts_query.join(post_hashtags).join(Hashtag).filter(Hashtag.name == hashtag)
    '''
    # Apply visibility filters
    posts_query = posts_query.filter(
        (Post.visibility != "private") | (Post.author_id == current_user.id)  # Include private only if it's the user's post
    ).filter(
        (Post.visibility != "friends") | (FollowerAlias.follower_id != None)  # Include friends only if the user follows the author
    )
    '''
    posts_query = posts_query.order_by(desc(Post.created_at))
    total_count = posts_query.count()
    posts = posts_query.offset(offset).limit(limit).all()

    result = []
    for post, username, _ in posts:
        post_dict = post.__dict__.copy()
        post_dict["username"] = username
        hashtags = (
            db.query(Hashtag)
            .join(post_hashtags)
            .filter(post_hashtags.c.post_id == post.id)
            .all()
        )
        post_dict["hashtags"] = [hashtag.name for hashtag in hashtags]
        
        liked_post = db.query(Like).filter(Like.user_id == current_user.id, Like.post_id == post.id).first()
        post_dict["is_liked"] = liked_post is not None

        # Check if the current user has saved the post
        saved_post = db.query(UserSavedPosts).filter(UserSavedPosts.user_id == current_user.id, UserSavedPosts.saved_post_id == post.id).first()
        post_dict["is_saved"] = saved_post is not None
        
        post.update_likes_and_comments_count(db)  # Update likes and comments count for each post
        result.append(post_dict)

    return {
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit,  # To calculate total pages
        "data": result,
    }


# get post by post id
import math

async def get_post_from_post_id_svc(db: Session, current_user: User, post_id: int, page: int = 1, limit: int = 6) -> dict:
    offset = (page - 1) * limit
    
    post_query = (
        db.query(Post)
        .options(
            joinedload(Post.author),
            joinedload(Post.hashtags),
        )
        .filter(Post.id == post_id, Post.visibility == VisibilityEnum.public)
        .first()
    )

    if not post_query:
        return None

    # Fetch total likes count and calculate pagination metadata for likes
    total_likes_count = db.query(func.count(Like.id)).filter(Like.post_id == post_id).scalar()
    total_likes_pages = max(1, math.ceil(total_likes_count / limit))

    # Fetch paginated likes
    likes_query = (
        db.query(Like)
        .options(joinedload(Like.user))
        .filter(Like.post_id == post_id)
        .order_by(desc(Like.created_at))
        .limit(limit)
        .offset(offset)
        .all()
    )

    # Fetch total comments count and calculate pagination metadata for comments
    total_comments_count = db.query(func.count(Comment.id)).filter(Comment.post_id == post_id).scalar()
    total_comments_pages = max(1, math.ceil(total_comments_count / limit))

    # Fetch paginated comments
    comments_query = (
        db.query(Comment)
        .options(joinedload(Comment.user))
        .filter(Comment.post_id == post_id)
        .order_by(desc(Comment.created_at))
        .limit(limit)
        .offset(offset)
        .all()
    )
    
    # Determine is_liked and is_saved for the current user
    is_liked = False
    is_saved = False
    if current_user:
        is_liked = db.query(Like).filter(Like.user_id == current_user.id, Like.post_id == post_id).first() is not None
        is_saved = db.query(UserSavedPosts).filter(UserSavedPosts.user_id == current_user.id, UserSavedPosts.saved_post_id == post_id).first() is not None

    # Construct response with metadata
    post_response = {
        "id": post_query.id,
        "content": post_query.content,
        "media": post_query.media,
        "location": post_query.location,
        "visibility": post_query.visibility.value,
        "author_id": post_query.author_id,
        "username": post_query.author.username,
        "likes_count": post_query.likes_count,
        "comments_count": post_query.comments_count,
        "share_count": post_query.share_count,
        "save_count": post_query.save_count,
        "views_count": post_query.views_count,
        "category_of_content": post_query.category_of_content,
        "media_type": post_query.media_type,
        "report_count": post_query.report_count,
        "created_at": post_query.created_at,
        "hashtags": [tag.name for tag in post_query.hashtags],
        "is_liked": is_liked,
        "is_saved": is_saved,
        
        # Likes metadata and list of likes
        "likes": {
            "metadata": {
                "total_count": total_likes_count,
                "total_pages": total_likes_pages,
                "current_page": page,
                "page": page,
                "limit": limit
            },
            "items": [
                {
                    "user_id": like.user.id,
                    "username": like.user.username,
                    "profile_pic": like.user.profile_pic,
                    "created_at": like.created_at
                }
                for like in likes_query
            ]
        },

        # Comments metadata and list of comments
        "comments": {
            "metadata": {
                "total_count": total_comments_count,
                "total_pages": total_comments_pages,
                "current_page": page,
                "page": page,
                "limit": limit
            },
            "items": [
                {
                    "id": comment.id,
                    "content": comment.content,
                    "created_at": comment.created_at,
                    "user_id": comment.user.id,
                    "username": comment.user.username,
                    "profile_pic": comment.user.profile_pic,
                    "post_id": comment.post_id
                }
                for comment in comments_query
            ]
        }
    }

    return post_response


# delete post svc
async def delete_post_svc(db: Session, post_id: int):
    post = db.query(Post).filter(Post.id == post_id).first()
    db.delete(post)
    db.commit()


# like post
async def like_post_svc(db: Session, post_id: int, username: str):
    # Fetch the post object (not just a dictionary) from the database
    post = db.query(Post).filter(Post.id == post_id).first()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Fetch the user object using the username
    user = db.query(User).filter(User.username == username).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if the user has already liked the post
    existing_like = db.query(Like).filter(Like.post_id == post_id, Like.user_id == user.id).first()

    if existing_like:
        return {"message": "You have already liked this post."}

    # If not liked, add the like
    post.liked_by_users.append(user)
    new_like = Like(post_id=post_id, user_id=user.id)
    db.add(new_like)
    post.likes_count += 1

    # Add like activity
    like_activity = Activity(
        username=post.author.username,
        liked_post_id=post_id,
        username_like=username,
        liked_media=post.media,
    )
    db.add(like_activity)

    db.commit()
    return {"message": "Post liked successfully."}


# unlike post
async def unlike_post_svc(db: Session, post_id: int, username: str):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return False, "Invalid post_id"

    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False, "Invalid username"

    # Check if user liked the post
    if user not in post.liked_by_users:
        return False, "Already not liked"

    # Remove from 'post_likes'
    post.liked_by_users.remove(user)

    # Delete the corresponding 'Like' entry
    existing_like = (
        db.query(Like)
        .filter_by(post_id=post.id, user_id=user.id)
        .first()
    )
    if existing_like:
        db.delete(existing_like)

    # Decrement the likes_count safely
    post.likes_count = max(post.likes_count - 1, 0)

    db.commit()
    return True, "Unliked successfully"


# users who liked post
async def liked_users_post_svc(db: Session, post_id: int) -> list[UserSchema]:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return []
    liked_users = post.liked_by_users
    # return [UserSchema.from_orm(user) for user in liked_users]
    return liked_users


# Commenting on the post
async def comment_on_post_svc(db: Session, post_id: int, user_id: int, content: str):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return False, "invalid post_id"

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False, "invalid user_id"

    # Create the comment
    comment = Comment(content=content, post_id=post_id, user_id=user_id, created_at=datetime.now())
    db.add(comment)
    post.comments_count += 1

    # Add like activity
    comment_activity = Activity(
        username=post.author.username,
        commented_post_id=post_id,
        username_like=user.username,
        liked_media=post.media,
    )
    db.add(comment_activity)
    db.commit()

    return True, "comment added"

async def delete_comments_svc(db: Session, post_id: int, user_id: int, comment_ids: Union[int, list[int]]) -> int:
    # Ensure the post belongs to the current user
    post = db.query(Post).filter(Post.id == post_id, Post.author_id == user_id).first()
    if not post:
        raise Exception("Post not found or you're not the owner")

    # Normalize comment_ids to list
    if isinstance(comment_ids, int):
        comment_ids = [comment_ids]

    comments = db.query(Comment).filter(
        Comment.post_id == post_id,
        Comment.id.in_(comment_ids)
    ).all()

    if not comments:
        raise Exception("No matching comments found")

    for comment in comments:
        db.delete(comment)

    db.commit()
    return len(comments) 


# Get comments for a post
async def get_comments_for_post_svc(db: Session, current_user: User, post_id: int, page: int, limit: int):
    offset = (page - 1) * limit

    # 🔒 Get all users blocked by or blocking current user
    blocked_user_ids = set(
        row[0] for row in db.query(BlockedUsers.blocked_id).filter(BlockedUsers.blocker_id == current_user.id)
    ).union(
        row[0] for row in db.query(BlockedUsers.blocker_id).filter(BlockedUsers.blocked_id == current_user.id)
    )

    # Get total count of comments
    total_count = ( db.query(func.count(Comment.id))
    .filter(Comment.post_id == post_id)
    .filter(~Comment.user_id.in_(blocked_user_ids))
    .scalar()
    )
    total_pages = math.ceil(total_count / limit) if total_count > 0 else 1

    # Get paginated comments
    comments = (
        db.query(Comment)
        .options(joinedload(Comment.user))  # Load related User data
        .filter(Comment.post_id == post_id)
        .filter(~Comment.user_id.in_(blocked_user_ids))  # Exclude blocked users' comments
        .order_by(desc(Comment.created_at))  # Order by latest comments first
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total_count": total_count,
        "total_pages": total_pages,
        "page": page,
        "limit": limit,
        "comments": [
            {
                "comment_id": comment.id,
                "content": comment.content,
                "user_id": comment.user.id,
                "username": comment.user.username,
                "profile_pic": comment.user.profile_pic,
                "created_at": comment.created_at
            }
            for comment in comments
        ]
    }

async def get_likes_for_post_svc(
    db: Session, current_user: User, post_id: int, page: int, limit: int
):
    offset = (page - 1) * limit

    # ✅ First, get the post author_id
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    post_author_id = post.author_id

    # ✅ Get users blocked by OR blocking the post author
    blocked_user_ids = set(
        row[0] for row in db.query(BlockedUsers.blocked_id).filter(BlockedUsers.blocker_id == post_author_id)
    ).union(
        row[0] for row in db.query(BlockedUsers.blocker_id).filter(BlockedUsers.blocked_id == post_author_id)
    )

    # ✅ Filter likes excluding blocked users
    total_count = (
        db.query(func.count(Like.id))
        .filter(Like.post_id == post_id)
        .filter(~Like.user_id.in_(blocked_user_ids))
        .scalar()
    )

    total_pages = math.ceil(total_count / limit) if total_count > 0 else 1

    likes = (
        db.query(Like)
        .options(joinedload(Like.user))
        .filter(Like.post_id == post_id)
        .filter(~Like.user_id.in_(blocked_user_ids))
        .order_by(desc(Like.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total_count": total_count,
        "total_pages": total_pages,
        "page": page,
        "limit": limit,
        "likes": [
            {
                "user_id": like.user.id,
                "username": like.user.username,
                "profile_pic": like.user.profile_pic,
                "created_at": like.created_at
            }
            for like in likes
        ]
    }


async def save_post_svc(db: Session, user_id: int, post_id: int):
    # Check if post is already saved by user
    existing_entry = db.query(UserSavedPosts).filter(
        UserSavedPosts.user_id == user_id, UserSavedPosts.saved_post_id == post_id
    ).first()

    if existing_entry:
        raise HTTPException(status_code=400, detail="Post already saved.")

    # Fetch the post details from the posts table
    post = db.query(Post).filter(Post.id == post_id).first()

    # If the post doesn't exist, raise an error
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")

    # Create a new entry in user_saved_posts table with all post attributes
    saved_post = UserSavedPosts(
        user_id=user_id,
        saved_post_id=post.id,
        content=post.content,
        media=post.media,
        location=post.location,
        created_at=post.created_at,
        likes_count=post.likes_count,
        comments_count=post.comments_count,
        share_count=post.share_count,
        visibility=post.visibility,
    )
    db.add(saved_post)
    if post and post.save_count is not None and post.save_count > 0:
        post.save_count += 1
    db.commit()
    db.refresh(saved_post)

    return {"message": "Post saved successfully"}

async def unsave_post_svc(db: Session, user_id: int, post_id: int):
    # Check if the post is saved by the user
    saved_post = db.query(UserSavedPosts).filter(
        UserSavedPosts.user_id == user_id, UserSavedPosts.saved_post_id == post_id
    ).first()

    if not saved_post:
        raise HTTPException(status_code=404, detail="Post not found in saved list.")

    # Delete the saved post entry
    db.delete(saved_post)
    # Decrement save_count for the related post
    post = db.query(Post).filter(Post.id == post_id).first()
    if post and post.save_count is not None and post.save_count > 0:
        post.save_count -= 1
        db.add(post)
    
    db.commit()

    return {"message": "Post unsaved successfully"}

async def get_saved_posts_svc(db: Session, user_id: int, page: int, limit: int):
    offset = (page - 1) * limit
    # Blocked users: anyone the current user blocked or who blocked them
    blocked_user_ids = set(
        row[0] for row in db.query(BlockedUsers.blocked_id).filter(BlockedUsers.blocker_id == user_id)
    ).union(
        row[0] for row in db.query(BlockedUsers.blocker_id).filter(BlockedUsers.blocked_id == user_id)
    )
    '''
    total_count = (
        db.query(UserSavedPosts)
        .filter(UserSavedPosts.user_id == user_id)
        .count()
    )
    '''
        # Get total count excluding blocked posts
    total_count = (
        db.query(UserSavedPosts)
        .join(Post, UserSavedPosts.saved_post_id == Post.id)
        .filter(UserSavedPosts.user_id == user_id)
        .filter(~Post.author_id.in_(blocked_user_ids))
        .count()
    )
    liked_post_ids = set(
        db.query(Like.post_id)
        .filter(Like.user_id == user_id)
        .all()
    )
    liked_post_ids = {pid[0] for pid in liked_post_ids}

    # Saved post_ids (optional since you're already filtering from saved)
    saved_post_ids = set(
        db.query(UserSavedPosts.saved_post_id)
        .filter(UserSavedPosts.user_id == user_id)
        .all()
    )
    saved_post_ids = {pid[0] for pid in saved_post_ids}

    saved_posts = (
        db.query(
            UserSavedPosts.id.label("saved_post_id"),
            Post.id.label("post_id"),
            Post.content,
            Post.media,
            Post.location,
            Post.author_id,
            Post.created_at,
            Post.likes_count,
            Post.comments_count,
            Post.save_count,
            Post.views_count,
            Post.report_count,
            Post.thumbnail,
            Post.category_of_content,
            Post.media_type,
            Post.share_count,
            Post.visibility,
            User.username,
        )
        .join(Post, UserSavedPosts.saved_post_id == Post.id)
        .join(User, Post.author_id == User.id)
        .filter(UserSavedPosts.user_id == user_id)
        .filter(~Post.author_id.in_(blocked_user_ids))  # ❌ Exclude blocked users' posts
        .order_by(desc(UserSavedPosts.created_at))
        .offset(offset).limit(limit)
        .all()
    )
    
    return {
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit,  # To calculate total pages
        "data": [
            {**{k if k != "post_id" else "id": v for k, v in row._mapping.items()},
            "is_liked": row.post_id in liked_post_ids,
            "is_saved": row.post_id in saved_post_ids,
    }
                  for row in saved_posts],
    }

async def share_post_svc(db: Session, sender_user_id: int, request: SharePostRequest):
    """Shares a post with multiple users, prevents duplicates, and updates share count."""
    print("DEBUG - request data:")
    print("receiver_user_ids =>", request.receiver_user_ids)
    print("post_id =>", request.post_id)
    try:
        # Step 1: Check if the post exists
        post = db.query(Post).filter(Post.id == request.post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")

        shared_count = 0  # Track how many users were newly shared with

        # Step 2: Loop through receiver_user_ids
        for receiver_id in request.receiver_user_ids:
            # Check for duplicate share
            already_shared = db.query(UserSharedPosts).filter_by(
                sender_user_id=sender_user_id,
                receiver_user_id=receiver_id,
                post_id=request.post_id
            ).first()

            if already_shared:
                continue  # Skip if already shared

            # Create new share record
            new_share = UserSharedPosts(
                sender_user_id=sender_user_id,
                receiver_user_id=receiver_id,
                post_id=request.post_id
            )
            db.add(new_share)
            shared_count += 1

        # Step 3: Update post's share count (only increment by newly shared)
        post.share_count += shared_count

        db.commit()
        return {"message": f"Post shared with {shared_count} user(s)"}

    except SQLAlchemyError as e:
        db.rollback()
        raise Exception(f"Database error: {str(e)}")
    
    except Exception as e:
        db.rollback()
        raise Exception(f"Error sharing post: {str(e)}")

async def unsend_share_svc(db: Session, sender_user_id: int, post_id: int, receiver_user_id: int):
    """Removes a share record and updates share_count."""
    # Find the shared post entry
    shared_post = db.query(UserSharedPosts).filter(
        UserSharedPosts.sender_user_id == sender_user_id,
        UserSharedPosts.post_id == post_id,
        UserSharedPosts.receiver_user_id == receiver_user_id
    ).first()

    if not shared_post:
        raise HTTPException(status_code=404, detail="Shared post not found.")

    # Delete the share record
    db.delete(shared_post)

    # Decrease share count of the post
    post = db.query(Post).filter(Post.id == post_id).first()
    if post and post.share_count > 0:
        post.share_count -= 1

    db.commit()

    return {"message": "Share undone successfully."}

async def get_shared_posts_svc(db: Session, user_id: int):
        """Fetches posts that a specific user has shared."""
        return db.query(UserSharedPosts).filter(UserSharedPosts.sender_user_id == user_id).all()
    
async def get_received_posts_svc(db: Session, user_id: int):
        """Fetches posts that a specific user has shared."""
        return db.query(UserSharedPosts).filter(UserSharedPosts.receiver_user_id == user_id).all()

async def serialize_posts(posts, db: Session, current_user: User):
    result = []
    for post in posts:
        post_dict = post.__dict__.copy()

        # Get author username
        username = db.query(User.username).filter(User.id == post.author_id).scalar()
        post_dict["username"] = username

        # Get hashtags
        hashtags = (
            db.query(Hashtag)
            .join(post_hashtags)
            .filter(post_hashtags.c.post_id == post.id)
            .all()
        )
        post_dict["hashtags"] = [tag.name for tag in hashtags]

        # Is liked
        liked = (
            db.query(Like)
            .filter(Like.user_id == current_user.id, Like.post_id == post.id)
            .first()
        )
        post_dict["is_liked"] = liked is not None

        # Is saved
        saved = (
            db.query(UserSavedPosts)
            .filter(UserSavedPosts.user_id == current_user.id, UserSavedPosts.saved_post_id == post.id)
            .first()
        )
        post_dict["is_saved"] = saved is not None

        # Update likes and comment counts
        post.update_likes_and_comments_count(db)

        result.append(post_dict)
    return result

async def get_public_posts_svc(db: Session, current_user: User, page: int, limit: int):
    query = db.query(Post).filter(Post.visibility == "public", Post.author_id == current_user.id).order_by(desc(Post.created_at))
    total_count = query.count()

    posts = query.offset((page - 1) * limit).limit(limit).all()
    data = await serialize_posts(posts, db, current_user)

    return {
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit,
        "data": data,
    }


async def get_private_posts_svc(db: Session, current_user: User, page: int, limit: int):
    query = db.query(Post).filter(Post.author_id == current_user.id, Post.visibility == "private").order_by(desc(Post.created_at))
    total_count = query.count()

    posts = query.offset((page - 1) * limit).limit(limit).all()
    data = await serialize_posts(posts, db, current_user)

    return {
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit,
        "data": data,
    }


async def get_friends_posts_svc(db: Session, current_user: User, page: int, limit: int):
    following_ids = [
        f.following_id for f in db.query(Follow).filter(Follow.follower_id == current_user.id)
    ]

    query = db.query(Post).filter(Post.author_id.in_(following_ids), Post.visibility == "friends").order_by(desc(Post.created_at))
    total_count = query.count()

    posts = query.offset((page - 1) * limit).limit(limit).all()
    data = await serialize_posts(posts, db, current_user)

    return {
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit,
        "data": data,
    }


async def get_posts_by_visibility_svc(db: Session, current_user: User, visibility: str, page: int, limit: int):
    try:
        query = db.query(Post)

        if visibility == "public":
            query = query.filter(Post.visibility == "public").order_by(desc(Post.created_at))

        elif visibility == "private":
            query = query.filter(Post.author_id == current_user.id, Post.visibility == "private").order_by(desc(Post.created_at))

        elif visibility == "friends":
            following_ids = [
                f.following_id for f in db.query(Follow).filter(Follow.follower_id == current_user.id)
            ]
            query = query.filter(Post.author_id.in_(following_ids), Post.visibility == "friends").order_by(desc(Post.created_at))

        else:
            return None

        total_count = query.count()
        posts = query.offset((page - 1) * limit).limit(limit).all()
        data = await serialize_posts(posts, db, current_user)

        return {
            "total_count": total_count,
            "page": page,
            "limit": limit,
            "total_pages": (total_count + limit - 1) // limit,
            "data": data,
        }

    except SQLAlchemyError as e:
        print(f"Database error: {e}")
        return None

async def get_following_posts_svc(db: Session, user_id: int, page: int, limit: int):
    total_count = (
        db.query(Post)
        .join(Follow, Follow.following_id == Post.author_id)
        .filter(Follow.follower_id == user_id)
        .filter((Post.visibility != "private") | (Post.author_id == user_id))  # Exclude private unless it's the user's post
        .count()
    )

    offset = (page - 1) * limit
    if offset >= total_count:
        return {
            "total_count": total_count,
            "page": page,
            "limit": limit,
            "total_pages": (total_count + limit - 1) // limit,
            "data": [],
        }

    posts = (
        db.query(Post, User.username)
        .join(User, Post.author_id == User.id)
        .join(Follow, Follow.following_id == Post.author_id)
        .filter(Follow.follower_id == user_id)
        .filter((Post.visibility != "private") | (Post.author_id == user_id))  # Exclude private unless it's the user's post
        .order_by(desc(Post.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )

    result = []
    for post, username in posts:
        post_dict = post.__dict__.copy()  # Get all fields dynamically
        post_dict["username"] = username
        post_dict["hashtags"] = [hashtag.name for hashtag in post.hashtags] if post.hashtags else []

        # Compute dynamic flags
        post_dict["is_liked"] = db.query(Like).filter(Like.user_id == user_id, Like.post_id == post.id).first() is not None
        post_dict["is_saved"] = db.query(UserSavedPosts).filter(UserSavedPosts.user_id == user_id, UserSavedPosts.saved_post_id== post.id).first() is not None

        result.append(post_dict)

    return {
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit,
        "data": result,
    }  

async def search_hashtags_svc(query: str, db: Session, page: int, limit: int):
    offset = (page - 1) * limit

    total_matching_hashtags = (
        db.query(func.count(func.distinct(Hashtag.id)))
        .join(post_hashtags, Hashtag.id == post_hashtags.c.hashtag_id)
        .join(Post, Post.id == post_hashtags.c.post_id)
        .filter(Hashtag.name.ilike(f"%{query}%"))
        .filter(Post.visibility == VisibilityEnum.public)
        .scalar()
    )
    total_pages = math.ceil(total_matching_hashtags / limit) if total_matching_hashtags > 0 else 0 
    
    hashtags = (
        db.query(
            Hashtag.name,
            func.count(post_hashtags.c.post_id).label("post_count")
        )
        .join(post_hashtags, Hashtag.id == post_hashtags.c.hashtag_id)
        .join(Post, Post.id == post_hashtags.c.post_id)
        .filter(Hashtag.name.ilike(f"%{query}%"))
        .filter(Post.visibility == VisibilityEnum.public)
        .group_by(Hashtag.name)
        .order_by(func.count(post_hashtags.c.post_id).desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return {
        "metadata": {
            "total_items": total_matching_hashtags,
            "total_pages": total_pages,
            "current_page": page,
            "limit": limit                  
            },
        "items": [
            {"hashtag": hashtag.name, "post_count": hashtag.post_count} for hashtag in hashtags
        ]
    }

''' 
async def search_users_svc(query: str, db: Session, current_user: User, page: int, limit: int):
    offset = (page - 1) * limit

    # Total matching users count
    total_count = (
        db.query(User.id)
        .filter(User.username.ilike(f"%{query}%"))
        .count()
    )
    total_pages = max(1, math.ceil(total_count / limit))

    # Get user details along with follower count
    users = (
        db.query(
            User.id,
            User.username,
            User.profile_pic,
            User.name,
            User.bio,
            User.phone_number,
            func.count(Follow.follower_id).label("followers_count")
        )
        .outerjoin(Follow, Follow.following_id == User.id)
        .filter(User.username.ilike(f"%{query}%"))
        .group_by(User.id, User.username, User.profile_pic, User.name, User.bio, User.phone_number)
        .order_by(func.count(Follow.follower_id).desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    # Get all user IDs the current user is following
    following_ids = set(
        row[0] for row in db.query(Follow.following_id)
        .filter(Follow.follower_id == current_user.id)
        .all()
    )

    # ✅ Get all pending follow request target_ids
    requested_ids = set(
        row[0] for row in db.query(FollowRequest.target_id)
        .filter(FollowRequest.requester_id == current_user.id)
        .all()
    )


    return {
        "metadata": {
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "limit": limit
        },
        "items": [
            {
                "user_id": user.id,
                "username": user.username,
                "profile_pic": user.profile_pic,
                "name": user.name,
                "bio": user.bio,
                "phone_number": user.phone_number,
                "followers_count": user.followers_count,
                "is_following": user.id in following_ids,
                "is_requested": user.id in requested_ids, 
                "is_self": user.id == current_user.id
            }
            for user in users
        ]
    }

'''

async def search_users_svc(query: str, db: Session, current_user: User, page: int, limit: int):
    offset = (page - 1) * limit

    # 🔒 Get all blocked or blocking users
    blocked_user_ids = set(
        row[0] for row in db.query(BlockedUsers.blocked_id)
        .filter(BlockedUsers.blocker_id == current_user.id)
    )
    blocked_by_ids = set(
        row[0] for row in db.query(BlockedUsers.blocker_id)
        .filter(BlockedUsers.blocked_id == current_user.id)
    )
    excluded_user_ids = blocked_user_ids.union(blocked_by_ids)

    # Total matching users count (excluding blocked)
    total_count = (
        db.query(User.id)
        .filter(User.username.ilike(f"%{query}%"))
        .filter(~User.id.in_(excluded_user_ids))
        .count()
    )
    total_pages = max(1, math.ceil(total_count / limit))

    users = (
        db.query(
            User.id,
            User.username,
            User.profile_pic,
            User.name,
            User.bio,
            User.phone_number,
            func.count(Follow.follower_id).label("followers_count")
        )
        .outerjoin(Follow, Follow.following_id == User.id)
        .filter(User.username.ilike(f"%{query}%"))
        .filter(~User.id.in_(excluded_user_ids))  # 🔒 enforce block
        .group_by(User.id, User.username, User.profile_pic, User.name, User.bio, User.phone_number)
        .order_by(func.count(Follow.follower_id).desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    following_ids = set(
        row[0] for row in db.query(Follow.following_id)
        .filter(Follow.follower_id == current_user.id)
        .all()
    )
    requested_ids = set(
        row[0] for row in db.query(FollowRequest.target_id)
        .filter(FollowRequest.requester_id == current_user.id)
        .all()
    )
    incoming_request_ids = set(
        row[0] for row in db.query(FollowRequest.requester_id)
        .filter(FollowRequest.target_id == current_user.id)
        .all()
    )

    return {
        "metadata": {
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "limit": limit
        },
        "items": [
            {
                "user_id": user.id,
                "username": user.username,
                "profile_pic": user.profile_pic,
                "name": user.name,
                "bio": user.bio,
                "phone_number": user.phone_number,
                "followers_count": user.followers_count,
                "is_following": user.id in following_ids,
                "is_requested": user.id in requested_ids,
                "is_requested_to_me": user.id in incoming_request_ids,
                "is_self": user.id == current_user.id
            }
            for user in users
        ]
    }


async def get_user_liked_posts_svc(db: Session, user_id: int, page: int, limit: int) -> dict:

    # 🔒 Get all blocked or blocking users
    blocked_user_ids = set(
        row[0] for row in db.query(BlockedUsers.blocked_id).filter(BlockedUsers.blocker_id == user_id)
    ).union(
        row[0] for row in db.query(BlockedUsers.blocker_id).filter(BlockedUsers.blocked_id == user_id)
    )
    # Correct count using post_likes
    total_count = (
        db.query(func.count(Post.id))
        .join(post_likes, Post.id == post_likes.c.post_id)
        .filter(post_likes.c.user_id == user_id)
        .filter(~Post.author_id.in_(blocked_user_ids))
        .scalar()
    )

    offset = (page - 1) * limit
    if offset >= total_count:
        return {
            "total_count": total_count,
            "page": page,
            "limit": limit,
            "total_pages": (total_count + limit - 1) // limit,
            "data": [],
        }

    # Correctly fetch liked posts
    liked_posts = (
        db.query(Post)
        .join(post_likes, Post.id == post_likes.c.post_id)
        .filter(post_likes.c.user_id == user_id)
        .filter(~Post.author_id.in_(blocked_user_ids))
        .order_by(desc(Post.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )

    result = []
    for post in liked_posts:
        post_dict = post.__dict__.copy()

        # Related data
        post_dict["username"] = post.author.username if post.author else None
        post_dict["hashtags"] = [hashtag.name for hashtag in post.hashtags] if post.hashtags else []

        # Update counts
        post.update_likes_and_comments_count(db)

        # Since this is liked posts, this is always true
        post_dict["is_liked"] = True

        # Saved status
        post_dict["is_saved"] = db.query(UserSavedPosts).filter(
            UserSavedPosts.user_id == user_id,
            UserSavedPosts.saved_post_id == post.id
        ).first() is not None

        result.append(post_dict)

    return {
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit,
        "data": result,
    }
