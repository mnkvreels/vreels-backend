import os
import re
from io import BytesIO
from typing import List, Optional
from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import timedelta
from ..database import get_db
from .schemas import PostCreate, SavePostRequest, SharePostRequest, MediaInteractionRequest, PostUpdate, CommentDeleteRequest, PostResponse, SeedPexelsRequest
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
    get_user_liked_posts_svc,
    delete_comments_svc

)
from ..profile.service import get_followers_svc
from ..auth.service import get_current_user, existing_user, get_user_from_user_id, send_notification_to_user, get_user_by_username, optional_current_user
from ..auth.schemas import UserIdRequest
from ..azure_blob import upload_to_azure_blob, upload_and_compress
from ..models.post import VisibilityEnum, MediaInteraction, Post
from ..models.user import UserDevice, User
from ..notification_service import send_push_notification


import httpx
from tempfile import NamedTemporaryFile
import mimetypes
from urllib.parse import urlparse

PEXELS_API_KEY = "1XwEXrdgodXtFlyqoC9Eq6asvqvC3whLOQpRclWrWkZFWSSCjBObf0ir"
PEXELS_HEADERS = {"Authorization": PEXELS_API_KEY}
PEXELS_IMAGE_URL = "https://api.pexels.com/v1/search?query=kids&per_page=15"
PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search?query=spring&per_page=15"

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

@router.post("/", status_code=status.HTTP_200_OK, response_model=PostResponse)
async def create_post(
    visibility: VisibilityEnum = Form(VisibilityEnum.public),
    content: Optional[str] = Form(None),
    file: UploadFile = Form(...),
    location: Optional[str] = Form(None),
    category_of_content: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = current_user
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="You are not authorized."
        )
    file_url = None
    if file:
        try:
            file_url, media_type, thumbnail_url = await upload_and_compress(file,user.username,str(user.id))
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        
    post = PostCreate(
        content=content,
        location=location,
        visibility=visibility,
        category_of_content=category_of_content,
        media_type=media_type,
        thumbnail=thumbnail_url
    )

    # Create the post with the file URL (if any)
    return await create_post_svc(db, post, current_user.id, file_url)

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

@router.patch("/edit/{post_id}", status_code=status.HTTP_200_OK)
async def edit_post(
    post_id: int,
    updates: PostUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.query(Post).filter(Post.id == post_id, Post.author_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found or not yours")

    for key, value in updates.dict(exclude_unset=True).items():
        setattr(post, key, value)

    db.commit()
    db.refresh(post)
    return post

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
        receiver_devices = db.query(UserDevice).filter(UserDevice.user_id.in_(tuple(request.receiver_user_ids))).all()

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

@router.delete("/delete", status_code=status.HTTP_200_OK)
async def delete_comments(
    request: CommentDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = current_user
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You are not authorized to delete comments.",
        )

    post = await get_post_from_post_id_svc(db, user, request.post_id)
    if post and post["author_id"] != user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You are not authorized to delete comments on this post.",
        )

    try:
        deleted_count= await delete_comments_svc(db, request.post_id, user.id, request.comment_ids)
        return  {"message": f"Deleted {deleted_count} comment(s) successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

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
async def get_public_posts(page: int, limit: int, db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    posts = await get_public_posts_svc(db, current_user, page, limit)
    if not posts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No public posts found."
        )
    return posts

# Get private posts (only visible to uuser)
@router.get("/private", status_code=status.HTTP_200_OK)
async def get_private_posts(page: int, limit: int, db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    posts = await get_private_posts_svc(db, current_user, page, limit)
    if not posts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No private posts found."
        )
    return posts

# get visible only to friends posts
@router.get("/friends", status_code=status.HTTP_200_OK)
async def get_friends_posts(page: int, limit: int, db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    posts = await get_friends_posts_svc(db, current_user, page, limit)

    if not posts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No friends' posts found."
        )

    return posts

# get posts by visibility
@router.get("/posts", status_code=status.HTTP_200_OK)
async def get_posts_by_visibility(page: int, limit: int, visibility: VisibilityEnum, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    posts = await get_posts_by_visibility_svc(db, current_user, visibility, page, limit)

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
async def log_interaction(
    interaction: MediaInteractionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    post = db.query(Post).filter(Post.id == interaction.post_id).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    """
    Logs user's media interaction (watched/skipped).
    """
    media_log = MediaInteraction(
        user_id=current_user.id,
        post_id=interaction.post_id,
        watched_time=interaction.watched_time,
        media_type=interaction.media_type,
        video_length=interaction.video_length
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



async def download_file(url: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        if resp.status_code == 200:
            tmp = NamedTemporaryFile(delete=False)
            tmp.write(resp.content)
            tmp.close()
            return tmp.name
        else:
            raise Exception(f"Failed to download from {url}")

'''
@router.post("/dev/seed-pexels-posts", tags=["dev-utils"])
async def seed_pexels_posts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    async with httpx.AsyncClient() as client:
        image_resp = await client.get(PEXELS_IMAGE_URL, headers=PEXELS_HEADERS)
        video_resp = await client.get(PEXELS_VIDEO_URL, headers=PEXELS_HEADERS)

        images = image_resp.json().get("photos", [])
        videos = video_resp.json().get("videos", [])

        results = []

        for image in images:
            try:
                img_url = image["src"]["large"]
                local_path = await download_file(img_url)

                # ✅ Extract clean file extension
                parsed_url = urlparse(img_url)
                file_name = os.path.basename(parsed_url.path)
                file_ext = file_name.split(".")[-1].lower()

                # ✅ Check against allowed image extensions
                if file_ext not in {"jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"}:
                    raise ValueError("Unsupported file type. Please upload an image or a video.")

                mime_type, _ = mimetypes.guess_type(img_url)

                with open(local_path, "rb") as file_data:
                    upload_file = UploadFile(
                        filename=f"pexels_img.{file_ext}",
                        file=file_data,
                        content_type=mime_type or "application/octet-stream"
                    )
                    azure_url, media_type, thumbnail_url = await upload_to_azure_blob(upload_file, current_user.username, str(current_user.id))

                post = PostCreate(
                    content=f"📸 Auto post from Pexels: {image.get('url')}",
                    location="Test Location",
                    visibility=VisibilityEnum.public
                )
                created_post = await create_post_svc(db, post, current_user.id, azure_url)
                results.append({"type": "image", "id": created_post.id, "url": azure_url})

                os.remove(local_path)
            except Exception as e:
                results.append({"error": f"Error uploading image: {str(e)}"})

        for video in videos:
            try:
                vid_url = video["video_files"][0]["link"]
                local_path = await download_file(vid_url)

                file_ext = vid_url.split(".")[-1].split("?")[0].lower()
                mime_type, _ = mimetypes.guess_type(vid_url)

                with open(local_path, "rb") as file_data:
                    upload_file = UploadFile(
                        filename=f"pexels_vid.{file_ext}",
                        file=file_data,
                        content_type=mime_type or "application/octet-stream"
                    )
                    azure_url, media_type, thumbnail_url = await upload_to_azure_blob(upload_file, current_user.username, str(current_user.id))

                post = PostCreate(
                    content=f"🎥 Auto post from Pexels: {video.get('url')}",
                    location="Test Location",
                    visibility=VisibilityEnum.public,
                    thumbnail=thumbnail_url
                )
                created_post = await create_post_svc(db, post, current_user.id, azure_url)
                results.append({"type": "video", "id": created_post.id, "url": azure_url})

                os.remove(local_path)
            except Exception as e:
                results.append({"error": f"Error uploading video: {str(e)}"})

    return {"posts_created": results}
'''

@router.post("/dev/seed-pexels-posts", tags=["dev-utils"])
async def seed_pexels_posts(
    payload: SeedPexelsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    results = []
    async with httpx.AsyncClient() as client:
        if payload.include_images:
            image_url = f"https://api.pexels.com/v1/search?query={payload.category}&per_page={payload.count}"
            image_resp = await client.get(image_url, headers=PEXELS_HEADERS)
            images = image_resp.json().get("photos", [])

            for image in images:
                try:
                    img_url = image["src"]["large"]
                    local_path = await download_file(img_url)

                    parsed_url = urlparse(img_url)
                    file_ext = os.path.basename(parsed_url.path).split(".")[-1].lower()

                    if file_ext not in {"jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"}:
                        raise ValueError("Unsupported file type.")

                    mime_type, _ = mimetypes.guess_type(img_url)

                    with open(local_path, "rb") as file_data:
                        upload_file = UploadFile(
                            filename=f"pexels_img.{file_ext}",
                            file=file_data,
                            content_type=mime_type or "application/octet-stream"
                        )
                        azure_url, media_type, thumbnail_url = await upload_and_compress(upload_file, current_user.username, str(current_user.id))

                    post = PostCreate(
                        content=f"📸 Auto post from Pexels: {image.get('url')}",
                        location="Test Location",
                        visibility=VisibilityEnum.public
                    )
                    created_post = await create_post_svc(db, post, current_user.id, azure_url)
                    results.append({"type": "image", "id": created_post.id, "url": azure_url})

                    os.remove(local_path)
                except Exception as e:
                    results.append({"error": f"Image upload failed: {str(e)}"})

        if payload.include_videos:
            video_url = f"https://api.pexels.com/videos/search?query={payload.category}&per_page={payload.count}"
            video_resp = await client.get(video_url, headers=PEXELS_HEADERS)
            videos = video_resp.json().get("videos", [])

            for video in videos:
                try:
                    vid_url = video["video_files"][0]["link"]
                    local_path = await download_file(vid_url)

                    file_ext = vid_url.split(".")[-1].split("?")[0].lower()
                    mime_type, _ = mimetypes.guess_type(vid_url)
                    '''
                    with open(local_path, "rb") as file_data:
                        upload_file = UploadFile(
                            filename=f"pexels_vid.{file_ext}",
                            file=file_data,
                            content_type=mime_type or "application/octet-stream"
                        )
                        azure_url, media_type, thumbnail_url = await upload_to_azure_blob(upload_file, current_user.username, str(current_user.id))
                    '''
                    # ✅ Read video into memory (BytesIO)
                    with open(local_path, "rb") as file_data:
                        file_bytes = file_data.read()

                    upload_file = UploadFile(
                        filename=f"pexels_vid.{file_ext}",
                        file=BytesIO(file_bytes),
                        content_type=mime_type or "application/octet-stream"
                    )

                    azure_url, media_type, thumbnail_url = await upload_and_compress(
                        upload_file, current_user.username, str(current_user.id)
                    )
                    post = PostCreate(
                        content=f"🎥 Auto post from Pexels: {video.get('url')}",
                        location="Test Location",
                        visibility=VisibilityEnum.public,
                        thumbnail=thumbnail_url
                    )
                    created_post = await create_post_svc(db, post, current_user.id, azure_url)
                    results.append({"type": "video", "id": created_post.id, "url": azure_url})

                    os.remove(local_path)
                except Exception as e:
                    results.append({"error": f"Video upload failed: {str(e)}"})

    return {"posts_created": results}

