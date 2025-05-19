# src/report/views.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..auth.service import get_current_user
from ..models.user import User
from ..models.report import UserAppReport, ReportReason
from .schemas import (
    ReportPostRequest,
    ReportUserRequest,
    ReportCommentRequest,
    ReportIssueRequest,
    ReportReasonResponse,
    ReportPouchRequest,
    ReportPouchCommentRequest
)
from typing import List
from .service import (
    report_post_svc,
    report_user_svc,
    report_comment_svc,
    report_pouch_svc,
    report_pouch_comment_svc,
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

@router.get("/report-reasons", response_model=List[ReportReasonResponse])
async def get_report_reasons(db: Session = Depends(get_db)):
    reasons = db.query(ReportReason).order_by(ReportReason.created_at.desc()).all()
    return reasons

@router.post("/pouch")
async def report_pouch(
    data: ReportPouchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await report_pouch_svc(data.pouch_id, current_user.id, data.reason, data.description, db)


@router.post("/pouch-comment")
async def report_pouch_comment(
    data: ReportPouchCommentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await report_pouch_comment_svc(data.comment_id, current_user.id, data.reason, data.description, db)


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

@router.post("/", status_code=status.HTTP_201_CREATED)
async def report_issue(payload: ReportIssueRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    report = UserAppReport(
        reporting_user_id=current_user.id,
        report_reason=payload.report_reason,
        description=payload.description
    )

    db.add(report)
    db.commit()
    db.refresh(report)

    return {
        "message": "Thank you for your feedback! Our team will review the issue.",
        "report_id": report.id
    }

# @router.get("/chats/by-user/{user_id}", response_model=dict)
# async def get_reported_chats_by_user_route(
#     user_id: int, page: int = 1, limit: int = 10, db: Session = Depends(get_db)
# ):
#     result = await get_reported_chats_by_user_svc(db=db, user_id=user_id, page=page, limit=limit)
#     if not result["data"]:
#         raise HTTPException(status_code=404, detail="No chats reported by this user.")
#     return result