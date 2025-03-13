from sqlalchemy.orm import Session
import re
from sqlalchemy import desc
from fastapi import HTTPException
from .schemas import PostCreate, Post as PostSchema, Hashtag as HashtagSchema, SharePostRequest
from ..models.post import Post, Hashtag, post_hashtags, Comment, UserSavedPosts, UserSharedPosts
from ..models.user import User
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
    )

    await create_hashtags_svc(db, db_post)

    db.add(db_post)
    db.commit()
    db.refresh(db_post)  # Refresh to get the updated post instance with generated id and relationships
    db_post.update_likes_and_comments_count(db)  # Update likes and comments count for the post

    db.commit()  # Commit after updating the counts
    return db_post


# get user's posts
async def get_user_posts_svc(db: Session, user_id: int) -> list[PostSchema]:
    posts = (
        db.query(Post)
        .filter(Post.author_id == user_id)
        .order_by(desc(Post.created_at))
        .all()
    )
    for post in posts:
        post.update_likes_and_comments_count(db)  # Update likes and comments count for each post
    return posts


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
    db: Session, page: int = 1, limit: int = 10, hashtag: str = None
):
    total_posts = db.query(Post).count()

    offset = (page - 1) * limit
    if offset >= total_posts:
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

    return result


# get post by post id
async def get_post_from_post_id_svc(db: Session, post_id: int) -> PostSchema:
    post = db.query(Post).filter(Post.id == post_id).first()
    if post:
        post.update_likes_and_comments_count(db)  # Update likes and comments count for the post
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
        return False, "invalid post_id"

    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False, "invalid username"

    if user in post.liked_by_users:
        return False, "already liked"

    # increase like count of post
    post.liked_by_users.append(user)
    post.likes_count = len(post.liked_by_users)

    # TO DO activity of like
    like_activity = Activity(
        username=post.author.username,
        liked_post_id=post_id,
        username_like=username,
        liked_media=post.media,
    )
    db.add(like_activity)

    # Update like count for the post
    post.update_likes_and_comments_count(db)

    db.commit()
    return True, "done"


# unlike post
async def unlike_post_svc(db: Session, post_id: int, username: str):
    post = await get_post_from_post_id_svc(db, post_id)
    if not post:
        return False, "invalid post_id"

    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False, "invalid username"

    if not user in post.liked_by_users:
        return False, "already not liked"

    post.liked_by_users.remove(user)
    post.likes_count = len(post.liked_by_users)

    # Update like count for the post
    post.update_likes_and_comments_count(db)

    db.commit()
    return True, "done"


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

async def save_post_svc(db: Session, user_id: int, post_id: int):
    # Check if post is already saved by user
    existing_entry = db.query(UserSavedPosts).filter(
        UserSavedPosts.user_id == user_id, UserSavedPosts.saved_post_id == post_id
    ).first()

    if existing_entry:
        raise HTTPException(status_code=400, detail="Post already saved.")

    # Create a new entry in user_saved_posts table
    saved_post = UserSavedPosts(user_id=user_id, saved_post_id=post_id)
    db.add(saved_post)
    db.commit()
    db.refresh(saved_post)

    return {"message": "Post saved successfully"}

async def get_saved_posts_svc(db: Session, user_id: int):
    return db.query(UserSavedPosts).filter(UserSavedPosts.user_id == user_id).all()

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
                raise ValueError("Post not found")

            db.commit()
            return {"message": "Post shared successfully"}
        
        except SQLAlchemyError as e:
            db.rollback()
            raise Exception(f"Database error: {str(e)}")
        
        except Exception as e:
            db.rollback()
            raise Exception(f"Error sharing post: {str(e)}")
        
async def get_shared_posts_svc(db: Session, user_id: int):
        """Fetches posts that a specific user has shared."""
        return db.query(UserSharedPosts).filter(UserSharedPosts.user_id == user_id).all()