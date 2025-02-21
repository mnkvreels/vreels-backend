from sqlalchemy.orm import Session
import re
from sqlalchemy import desc

from .schemas import PostCreate, Post as PostSchema, Hashtag as HashtagSchema
from .models import Post, Hashtag, post_hashtags, Comment
from ..auth.models import User
from ..auth.schemas import User as UserSchema
from ..activity.models import Activity


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
async def create_post_svc(db: Session, post: PostCreate, user_id: int):
    # check if user_id is valid
    db_post = Post(
        content=post.content,
        image=post.image,
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
        liked_post_image=post.image,
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
