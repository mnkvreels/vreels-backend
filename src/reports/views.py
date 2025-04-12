# src/report/views.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..auth.service import get_current_user
from ..models.user import User
from .schemas import (
    ReportPostRequest,
    ReportUserRequest,
    ReportCommentRequest
)
from .service import (
    report_post_svc,
    report_user_svc,
    report_comment_svc,
    get_reported_posts_by_user_svc,
    get_reported_users_by_user_svc,
    get_reported_comments_by_user_svc
)

router = APIRouter(prefix="/report", tags=["report"])

@router.post("/post")
async def report_post(data: ReportPostRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await report_post_svc(data.post_id, current_user.id, data.reason, data.description, db)


@router.post("/user")
async def report_user(data: ReportUserRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await report_user_svc(data.user_id, current_user.id, data.reason, data.description, db)


@router.post("/comment")
async def report_comment(data: ReportCommentRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await report_comment_svc(data.comment_id, current_user.id, data.reason, data.description, db)


# @router.post("/chat")
# async def report_chat(data: ReportChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
#     return await report_chat_svc(data.thread_id, current_user.id, data.reason, db)

@router.get("/posts/by-user/{user_id}", response_model=dict)
async def get_reported_posts_by_user_route(
    user_id: int, page: int = 1, limit: int = 10, db: Session = Depends(get_db)
):
    result = await get_reported_posts_by_user_svc(db=db, user_id=user_id, page=page, limit=limit)
    if not result["data"]:
        raise HTTPException(status_code=404, detail="No posts reported by this user.")
    return result


@router.get("/users/by-user/{user_id}", response_model=dict)
async def get_reported_users_by_user_route(
    user_id: int, page: int = 1, limit: int = 10, db: Session = Depends(get_db)
):
    result = await get_reported_users_by_user_svc(db=db, user_id=user_id, page=page, limit=limit)
    if not result["data"]:
        raise HTTPException(status_code=404, detail="No users reported by this user.")
    return result


@router.get("/comments/by-user/{user_id}", response_model=dict)
async def get_reported_comments_by_user_route(
    user_id: int, page: int = 1, limit: int = 10, db: Session = Depends(get_db)
):
    result = await get_reported_comments_by_user_svc(db=db, user_id=user_id, page=page, limit=limit)
    if not result["data"]:
        raise HTTPException(status_code=404, detail="No comments reported by this user.")
    return result


# @router.get("/chats/by-user/{user_id}", response_model=dict)
# async def get_reported_chats_by_user_route(
#     user_id: int, page: int = 1, limit: int = 10, db: Session = Depends(get_db)
# ):
#     result = await get_reported_chats_by_user_svc(db=db, user_id=user_id, page=page, limit=limit)
#     if not result["data"]:
#         raise HTTPException(status_code=404, detail="No chats reported by this user.")
#     return result