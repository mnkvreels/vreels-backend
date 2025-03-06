import re
from typing import List
from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..database import get_db
from .schemas import PostCreate, Post
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
)
from ..auth.service import get_current_user, existing_user
from ..auth.schemas import User
from ..azure_blob import upload_to_azure_blob

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

@router.post("/", response_model=Post, status_code=status.HTTP_201_CREATED)
async def create_post(content: str = Form(...), file: UploadFile = Form(...), location: str = Form(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user = current_user
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="You are not authorized."
        )
    post = PostCreate(content=content, location=location)
    file_url = None
    if file:
        try:
            file_url = await upload_to_azure_blob(file)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Create the post with the file URL (if any)
    db_post = await create_post_svc(db, post, current_user.id, file_url)

    return db_post

@router.get("/user", response_model=list[Post])
async def get_current_user_posts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # verify the token
    user = current_user
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="You are not authorized."
        )

    return await get_user_posts_svc(db, user.id)


@router.get("/userposts", response_model=list[Post])
async def get_user_posts(request: UserRequest, db: Session = Depends(get_db)):
    # verify token
    user = await existing_user(db, request.username)

    return await get_user_posts_svc(db, user.id)

# Not working yet
@router.get("/hashtag/")
async def get_posts_from_hashtag(request: HashtagRequest , db: Session = Depends(get_db)):
    return await get_posts_from_hashtag_svc(db, request.hashtag)


@router.get("/feed")
async def get_random_posts(
    page: int = 1, limit: int = 5, hashtag: str = None, db: Session = Depends(get_db)
):
    return await get_random_posts_svc(db, page, limit, hashtag)


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(request: PostRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # verify the token
    user = current_user
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You are not authorized to delete this post.",
        )

    post = await get_post_from_post_id_svc(db, request.post_id)
    if post.author_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You are not authorized to delete this post.",
        )

    await delete_post_svc(db, request.post_id)


@router.post("/like", status_code=status.HTTP_204_NO_CONTENT)
async def like_post(request: PostRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    res, detail = await like_post_svc(db, request.post_id, current_user.username)
    if res == False:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


@router.post("/unlike", status_code=status.HTTP_204_NO_CONTENT)
async def unlike_post(request: PostRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    res, detail = await unlike_post_svc(db, request.post_id, current_user.username)
    if res == False:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


@router.get("/postlikes", response_model=list[User])
async def users_like_post(request: PostRequest, db: Session = Depends(get_db)):
    return await liked_users_post_svc(db, request.post_id)


@router.get("/", response_model=Post)
async def get_post(request: PostRequest, db: Session = Depends(get_db)):
    db_post = await get_post_from_post_id_svc(db, request.post_id)
    if not db_post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid post id"
        )

    return db_post


@router.post("/comment", status_code=status.HTTP_201_CREATED)
async def comment_on_post(request: CommentRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # verify the token
    user = current_user
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="You are not authorized."
        )

    res, detail = await comment_on_post_svc(db, request.post_id, user.id, request.content)
    if not res:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    return {"message": "Comment added successfully"}


@router.get("/postcomments")
async def get_comments_for_post(request: PostRequest, db: Session = Depends(get_db)):
    comments = await get_comments_for_post_svc(db, request.post_id)
    if not comments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No comments found")
    
    return comments
