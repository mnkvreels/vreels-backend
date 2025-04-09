import re
from typing import List, Optional
from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import timedelta
from ..database import get_db
from .schemas import PostCreate, SavePostRequest, SharePostRequest, MediaInteractionRequest
from .service import (
    create_post_svc,
    delete_post_svc,
    create_hashtags_svc,
    get_post_from_post_id_svc,
    get_posts_from_hashtag_svc,
    get_random_posts_svc,
    get_user_posts_svc,
    like_post_svc,
    unlike_post_svc,
    liked_users_post_svc,
    comment_on_post_svc,
    get_comments_for_post_svc,
    get_likes_for_post_svc,
    save_post_svc,
    unsave_post_svc,
    get_saved_posts_svc,
    share_post_svc,
    unsend_share_svc,
    get_shared_posts_svc,
    get_received_posts_svc,
    get_public_posts_svc,
    get_private_posts_svc,
    get_friends_posts_svc,
    get_posts_by_visibility_svc,
    get_following_posts_svc,
    search_hashtags_svc,
    search_users_svc,
    get_user_liked_posts_svc
)
from ..profile.service import get_followers_svc
from ..auth.service import get_current_user, existing_user, get_user_from_user_id, send_notification_to_user, get_user_by_username, optional_current_user
from ..auth.schemas import UserIdRequest
from ..azure_blob import upload_to_azure_blob
from ..models.post import VisibilityEnum, MediaInteraction, Post
from ..models.user import UserDevice, User
from ..notification_service import send_push_notification

router = APIRouter(prefix="/posts", tags=["posts"])

class UserRequest(BaseModel):
    username: str
    
class HashtagRequest(BaseModel):
    hashtag: str

class PostRequest(BaseModel):
    post_id: int

class CommentRequest(BaseModel):
    post_id: int
    content: str
    
# Regex pattern to check if a string is a valid URL
URL_PATTERN = re.compile(r'^(http|https):\/\/[^\s]+$')

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_post(
    visibility: VisibilityEnum = Form(VisibilityEnum.public),
    content: Optional[str] = Form(None),
    file: UploadFile = Form(...),
    location: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = current_user
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="You are not authorized."
        )
    post = PostCreate(content=content, location=location, visibility=visibility)
    file_url = None
    if file:
        try:
            file_url = await upload_to_azure_blob(file,user.username,str(user.id))
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Create the post with the file URL (if any)
    db_post = await create_post_svc(db, post, current_user.id, file_url)

    # Fetch followers of the user
    # followers = await get_followers_svc(db, current_user.id)

    # Send notifications to followers
    # for follow in followers:
    #     # follower_username = follow['username']
    #     follower_user = await get_user_by_username(db, follow.username)

    #     # Send push notification
    #     try:
    #         await send_notification_to_user(
    #         db, 
    #         user_id: follower_user.id
    #         title=f"New Post from {current_user.username}",
    #         message=f"{current_user.username} has posted a new update! Check it out!"
    #     )
    #     except Exception as e:
    #         # Log the error but don't raise it to ensure the post share is still processed
    #         print(f"Failed to send notification: {str(e)}")
    
    return db_post

@router.get("/user")
async def get_current_user_posts(page: int, limit: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # verify the token
    user = current_user
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
    posts = await get_user_posts_svc(db, user.id, current_user, page, limit)
    return posts


@router.get("/userposts")
async def get_user_posts_by_username(page: int, limit: int, request: UserRequest, db: Session = Depends(get_db), current_user: Optional[User] =Depends(optional_current_user)):
    # verify token
    user = await existing_user(db, request.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
    posts = await get_user_posts_svc(db, user.id, current_user, page, limit)
    return posts

@router.post("/savepost", status_code=status.HTTP_201_CREATED)
async def save_post(request: SavePostRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return await save_post_svc(db, current_user.id, request.post_id)

@router.post("/unsavepost", status_code=status.HTTP_201_CREATED)
async def unsave_post(request: SavePostRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return await unsave_post_svc(db, current_user.id, request.post_id)

@router.get("/savedposts", status_code=status.HTTP_200_OK)
async def get_saved_posts(page: int, limit: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    user = current_user
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="You are not authorized."
        )
    saved_posts = await get_saved_posts_svc(db, user.id, page, limit)
    return saved_posts

@router.post("/sharepost")
async def share_post(request: SharePostRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    sender_user_id = current_user.id
    try:
        # Process post sharing logic
        res = await share_post_svc(db, sender_user_id, request)

        # Get all devices of the receiver
        receiver_devices = db.query(UserDevice).filter(UserDevice.user_id == request.receiver_user_id).all()

        for device in receiver_devices:
            if device.notify_share:
                try:
                    await send_push_notification(
                        device_token=device.device_token,
                        platform=device.platform,
                        title="🔁 New Post Shared!",
                        message=f"{current_user.username} shared a post with you."
                    )
                except Exception as e:
                    print(f"Failed to notify device {device.device_id}: {e}")

        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/undoshare", status_code=status.HTTP_200_OK)
async def undo_share(
    request: SharePostRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        res = await unsend_share_svc(
            db, 
            sender_user_id=current_user.id, 
            post_id=request.post_id, 
            receiver_user_id=request.receiver_user_id
        )
        return res
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sharedposts")
async def get_shared_posts(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return await get_shared_posts_svc(db, current_user.id)

@router.get("/receivedposts")
async def get_received_posts(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return await get_received_posts_svc(db, current_user.id)

@router.get("/hashtag")
async def get_posts_from_hashtag(
    request: HashtagRequest,  # Request body
    page: int,  
    limit: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # Get current logged-in user
):
    hashtag_name = request.hashtag  # Extract the hashtag name from the request body
    return await get_posts_from_hashtag_svc(current_user, db, page, limit, hashtag_name)



@router.get("/feed")
async def get_random_posts(
    page: int, limit: int, hashtag: str = None, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    return await get_random_posts_svc(current_user, db, page, limit, hashtag)


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(request: PostRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # verify the token
    user = current_user
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You are not authorized to delete this post.",
        )

    post = await get_post_from_post_id_svc(db, user, request.post_id)
    if post and post["author_id"] != user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You are not authorized to delete this post.",
        )

    await delete_post_svc(db, request.post_id)


@router.post("/like", status_code=status.HTTP_200_OK)
async def like_post(request: PostRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Perform the like action
    res = await like_post_svc(db, request.post_id, current_user.username)
    
    # Get the post and notify the post owner (if it's not the liker themselves)
    post = await get_post_from_post_id_svc(db, current_user, request.post_id)
    
    if post and post["author_id"] != current_user.id:
        # Get all devices of the post owner
        receiver_devices = db.query(UserDevice).filter(UserDevice.user_id == post["author_id"]).all()

        for device in receiver_devices:
            if device.notify_likes:
                try:
                    await send_push_notification(
                        device_token=device.device_token,
                        platform=device.platform,
                        title="❤️ New Like on Your Post!",
                        message=f"{current_user.username} liked your post.",
                    )
                except Exception as e:
                    print(f"Notification failed for device {device.device_id}: {e}")

    return {"message": "Liked the post"}

@router.post("/unlike", status_code=status.HTTP_200_OK)
async def unlike_post(request: PostRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    res, detail = await unlike_post_svc(db, request.post_id, current_user.username)
    if res == False:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    return {"message": "Unliked the post"}

@router.get("/postlikes")
async def get_likes_for_post(page: int, limit: int, request: PostRequest, db: Session = Depends(get_db)):
    likes = await get_likes_for_post_svc(db, request.post_id, page, limit)
    if not likes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No likes found")
    
    return likes
 
@router.get("/", status_code=status.HTTP_200_OK)
async def get_post(request: PostRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_post = await get_post_from_post_id_svc(db, current_user, request.post_id)
    if not db_post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid post id"
        )

    return db_post


@router.post("/comment", status_code=status.HTTP_201_CREATED)
async def comment_on_post(
    request: CommentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify token
    user = current_user
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="You are not authorized."
        )

    res, detail = await comment_on_post_svc(db, request.post_id, user.id, request.content)
    if not res:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    # Notify post owner (if not commenting on own post)
    post = await get_post_from_post_id_svc(db, user, request.post_id)
    if post and post["author_id"] != current_user.id:
        # Fetch devices of post owner where notify_comments = True
        devices_to_notify = db.query(UserDevice).filter(
            UserDevice.user_id == post["author_id"],
            UserDevice.notify_comments == True
        ).all()

        for device in devices_to_notify:
            if device.device_token and device.platform:
                try:
                    await send_push_notification(
                        device_token=device.device_token,
                        platform=device.platform,
                        title="💬 New Comment on Your Post!",
                        message=f"{current_user.username} commented: {request.content}"
                    )
                except Exception as e:
                    print(f"Notification send failed for device {device.device_id}: {e}")

    return {"message": "Comment added successfully"}


@router.get("/postcomments")
async def get_comments_for_post(
    page: int,
    limit: int,
    request: PostRequest, 
    db: Session = Depends(get_db)
):
    comments = await get_comments_for_post_svc(db, request.post_id, page, limit)
    if not comments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No comments found")
    
    return comments


# Get public posts
@router.get("/public", status_code=status.HTTP_200_OK)
async def get_public_posts(db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    posts = await get_public_posts_svc(db,current_user.id)
    if not posts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No public posts found."
        )
    return posts

# Get private posts (only visible to uuser)
@router.get("/private", status_code=status.HTTP_200_OK)
async def get_private_posts(db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    posts = await get_private_posts_svc(db, current_user.id)
    if not posts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No private posts found."
        )
    return posts

# get visible only to friends posts
@router.get("/friends", status_code=status.HTTP_200_OK)
async def get_friends_posts(db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    posts = await get_friends_posts_svc(db, current_user.id)

    if not posts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No friends' posts found."
        )

    return posts

# get posts by visibility
@router.get("/posts", status_code=status.HTTP_200_OK)
async def get_posts_by_visibility(visibility: VisibilityEnum, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    posts = await get_posts_by_visibility_svc(db, current_user.id, visibility)

    if not posts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {visibility} posts found.",
        )

    return posts

#get following users posts
@router.get("/followingposts")
async def get_following_posts(
    page: int , limit: int , db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return await get_following_posts_svc(db, user.id, page, limit)

@router.get("/search/hashtags")
async def search_hashtags(page: int,limit: int, query: str, db: Session = Depends(get_db)):
    return await search_hashtags_svc(query, db, page, limit)

@router.get("/search/users")
async def search_users(page: int ,limit: int, query: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await search_users_svc(query, db, current_user,page,limit)

@router.get("/user/liked-posts")
async def get_current_user_liked_posts(
    page: int,
    limit: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # verify the token
    user = current_user
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You are not authorized."
        )
    posts = await get_user_liked_posts_svc(db, user.id, page, limit)
    return posts

@router.post("/log-media-interactions")
async def log_interaction(interaction: MediaInteractionRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Logs user's media interaction (watched/skipped).
    """
    media_log = MediaInteraction(
        user_id=current_user.id,
        post_id=interaction.post_id,
        watched_time=timedelta(seconds=interaction.watched_time),
        # skipped=interaction.skipped,
        # completed=interaction.completed
    )
    
    db.add(media_log)
    db.commit()
    return {"message": "Interaction logged successfully"}

@router.get("/media-interactions/post/{post_id}")
async def get_media_interactions_by_post_id(post_id: int, db: Session = Depends(get_db)):
    # Query the database for the post
    post = db.query(Post).filter(Post.id == post_id).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Query for media interactions for the given post
    interactions = db.query(MediaInteraction).filter(MediaInteraction.post_id == post_id).all()

    if not interactions:
        raise HTTPException(status_code=404, detail="No interactions found for this post")

    return interactions

@router.get("/media-interactions/user/{user_id}")
async def get_media_interactions_by_user_id(user_id: int, db: Session = Depends(get_db)):
    # Query the database for the user
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Query for media interactions for the given user
    interactions = db.query(MediaInteraction).filter(MediaInteraction.user_id == user_id).all()

    if not interactions:
        raise HTTPException(status_code=404, detail="No interactions found for this user")

    return interactions
