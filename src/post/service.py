from sqlalchemy.orm import Session
import re
from sqlalchemy import desc, func, select
from fastapi import HTTPException
from .schemas import PostCreate, Post as PostSchema, Hashtag as HashtagSchema, SharePostRequest
from ..models.post import Post, Hashtag, post_hashtags, Comment, UserSavedPosts, UserSharedPosts, Like
from ..models.user import User, Follow
from ..auth.schemas import User as UserSchema
from ..models.activity import Activity
from sqlalchemy.exc import SQLAlchemyError

# create hashtag from posts' content
# hey #fun
async def create_hashtags_svc(db: Session, post: Post):
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


# create post
async def create_post_svc(db: Session, post: PostCreate, user_id: int, file_url: str):
    # check if user_id is valid
    db_post = Post(
        content=post.content,
        media=file_url,
        location=post.location,
        author_id=user_id,
        visibility=post.visibility,
    )

    await create_hashtags_svc(db, db_post)

    db.add(db_post)
    db.commit()
    db.refresh(db_post)  # Refresh to get the updated post instance with generated id and relationships
    db_post.update_likes_and_comments_count(db)  # Update likes and comments count for the post

    db.commit()  # Commit after updating the counts
    return db_post


# get user's posts
async def get_user_posts_svc(db: Session, user_id: int, page: int, limit: int) -> list[PostSchema]:
    offset = (page - 1) * limit
    total_count = db.query(Post).filter(Post.author_id == user_id).count()
    posts = (
        db.query(Post)
        .filter(Post.author_id == user_id)
        .order_by(desc(Post.created_at))
        .offset(offset).limit(limit)
        .all()
    )
    for post in posts:
        post.update_likes_and_comments_count(db)  # Update likes and comments count for each post
    return {
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit,  # To calculate total pages
        "data": posts
    }


# get posts from a hashtag
async def get_posts_from_hashtag_svc(db: Session, hashtag_name: str):
    hashtag = db.query(Hashtag).filter_by(name=hashtag_name).first()
    if not hashtag:
        return None
    posts = hashtag.posts
    for post in posts:
        post.update_likes_and_comments_count(db)  # Update likes and comments count for each post
    return posts


# get random posts for feed
# return latest posts of all users
async def get_random_posts_svc(
    db: Session, page: int, limit: int, hashtag: str = None
):
    total_count = db.query(Post).count()

    offset = (page - 1) * limit
    if offset >= total_count:
        return []

    posts = db.query(Post, User.username).join(User).order_by(desc(Post.created_at))

    if hashtag:
        posts = posts.join(post_hashtags).join(Hashtag).filter(Hashtag.name == hashtag)

    posts = posts.offset(offset).limit(limit).all()

    result = []
    for post, username in posts:
        post_dict = post.__dict__
        post_dict["username"] = username
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
async def get_post_from_post_id_svc(db: Session, post_id: int) -> PostSchema:
    # Subquery for likes count
    likes_count_subquery = (
        db.query(func.count(Like.id))
        .filter(Like.post_id == Post.id)
        .correlate(Post)
        .scalar_subquery()
    )

    # Subquery for comments count
    comments_count_subquery = (
        db.query(func.count(Comment.id))
        .filter(Comment.post_id == Post.id)
        .correlate(Post)
        .scalar_subquery()
    )

    # Main query to get the post with counts
    post_query = (
        db.query(
            Post,
            likes_count_subquery.label("likes_count"),
            comments_count_subquery.label("comments_count"),
        )
        .filter(Post.id == post_id)
        .first()
    )

    if not post_query:
        return None

    # Unpack results
    post, likes_count, comments_count = post_query

    # Update likes and comments count
    post.likes_count = likes_count
    post.comments_count = comments_count

    return post


# delete post svc
async def delete_post_svc(db: Session, post_id: int):
    post = await get_post_from_post_id_svc(db, post_id)
    db.delete(post)
    db.commit()


# like post
async def like_post_svc(db: Session, post_id: int, username: str):
    post = await get_post_from_post_id_svc(db, post_id)
    if not post:
        return False, "Invalid post_id"

    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False, "Invalid username"

    # Check if like already exists in 'post_likes'
    if user in post.liked_by_users:
        return False, "Already liked"

    # Add entry to 'post_likes'
    post.liked_by_users.append(user)

    # Explicitly add a 'Like' entry in 'likes' table
    like = Like(post_id=post.id, user_id=user.id)
    db.add(like)

    # Increment the likes_count
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
    return True, "Liked successfully"


# unlike post
async def unlike_post_svc(db: Session, post_id: int, username: str):
    post = await get_post_from_post_id_svc(db, post_id)
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
    post = await get_post_from_post_id_svc(db, post_id)
    if not post:
        return []
    liked_users = post.liked_by_users
    # return [UserSchema.from_orm(user) for user in liked_users]
    return liked_users


# Commenting on the post
async def comment_on_post_svc(db: Session, post_id: int, user_id: int, content: str):
    post = await get_post_from_post_id_svc(db, post_id)
    if not post:
        return False, "invalid post_id"

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False, "invalid user_id"

    # Create the comment
    comment = Comment(content=content, post_id=post_id, user_id=user_id)
    db.add(comment)
    db.commit()

    # Update comment count for the post
    post.update_likes_and_comments_count(db)
    db.commit()

    return True, "comment added"


# Get comments for a post
async def get_comments_for_post_svc(db: Session, post_id: int):
    post = await get_post_from_post_id_svc(db, post_id)
    if not post:
        return []

    comments = db.query(Comment).filter(Comment.post_id == post_id).all()
    return comments

async def get_likes_for_post_svc(db: Session, post_id: int):
    post = await get_post_from_post_id_svc(db, post_id)
    if not post:
        return []

    likes = db.query(Like).filter(Like.post_id == post_id).all()
    return likes

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
    db.commit()

    return {"message": "Post unsaved successfully"}

async def get_saved_posts_svc(db: Session, user_id: int, page: int, limit: int):
    offset = (page - 1) * limit
    total_count = (
        db.query(UserSavedPosts)
        .filter(UserSavedPosts.user_id == user_id)
        .count()
    )
    saved_posts = (
        db.query(
            UserSavedPosts.id.label("saved_post_id"),
            Post.id.label("post_id"),
            Post.content,
            Post.media,
            Post.location,
            Post.created_at,
            Post.likes_count,
            Post.comments_count,
            Post.share_count,
            Post.visibility
        )
        .join(Post, UserSavedPosts.saved_post_id == Post.id)
        .filter(UserSavedPosts.user_id == user_id)
        .order_by(desc(UserSavedPosts.created_at))
        .offset(offset).limit(limit)
        .all()
    )
    
    return {
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit,  # To calculate total pages
        "data": [dict(row._mapping) for row in saved_posts],
    }

async def share_post_svc(db: Session, sender_user_id: int, request: SharePostRequest):
        """Creates a share record and updates share_count."""
        try:
            # Create a share record
            shared_post = UserSharedPosts(
                sender_user_id=sender_user_id,
                receiver_user_id=request.receiver_user_id,
                post_id=request.post_id
            )
            db.add(shared_post)

            # Increment share count of respective post
            post = db.query(Post).filter(Post.id == request.post_id).first()
            if post:
                post.share_count += 1
            else:
                raise HTTPException(status_code=404, detail="Post not found")

            db.commit()
            return {"message": "Post shared successfully"}
        
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

async def get_public_posts_svc(db: Session, user_id: int):
    posts = db.query(Post).filter(Post.author_id == user_id, Post.visibility == "public").all()
    return posts


async def get_private_posts_svc(db: Session, user_id: int):
    posts = db.query(Post).filter(Post.author_id == user_id, Post.visibility == "private").all()
    return posts


async def get_friends_posts_svc(db: Session, user_id: int):
    # Get IDs of followers who follow the current user
    follower_ids = [
        follow.follower_id
        for follow in db.query(Follow).filter(Follow.following_id == user_id).all()
    ]

    # Get posts visible to friends by followers
    posts = (
        db.query(Post)
        .filter(
            Post.author_id.in_(follower_ids),  # Posts created by followers
            Post.visibility == "friends",  # Only 'friends' posts
        )
        .all()
    )
    return posts

async def get_posts_by_visibility_svc(db: Session, user_id: int, visibility: str):
    try:
        # Public posts - visible to everyone
        if visibility == "public":
            posts = db.query(Post).filter(Post.visibility == "public").all()

        # Private posts - visible only to the post author
        elif visibility == "private":
            posts = db.query(Post).filter(
                Post.author_id == user_id, Post.visibility == "private"
            ).all()

        # Friends-only posts - visible to the user's followers
        elif visibility == "friends":
            # Get IDs of followers (users following the current user)
            follower_ids = [
                follow.follower_id
                for follow in db.query(Follow).filter(Follow.following_id == user_id).all()
            ]

            # Get posts visible to followers
            posts = db.query(Post).filter(Post.author_id.in_(follower_ids), Post.visibility == "friends").all()

        # Invalid visibility option
        else:
            return None

        return posts

    except SQLAlchemyError as e:
        print(f"Database error: {e}")
        return None