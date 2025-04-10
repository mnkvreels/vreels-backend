from sqlalchemy import VARCHAR
from sqlalchemy.orm import Session
from fastapi import HTTPException
from ..models.report import ReportPost, ReportUser, ReportComment
from ..models.post import Comment, Post
from ..models.user import User
from .enums import ReportReasonEnum

async def report_post_svc(post_id: int, reported_by: int, reason: str, db: Session):
    try:
        if reason not in ReportReasonEnum.__members__:
            raise HTTPException(status_code=400, detail=f"Invalid reason: {reason}")
        
        existing_report = db.query(ReportPost).filter(
            ReportPost.post_id == post_id, ReportPost.reported_by == reported_by
        ).first()

        if existing_report:
            raise HTTPException(status_code=400, detail="You have already reported this post.")

        report = ReportPost(post_id=post_id, reported_by=reported_by, reason=reason)
        db.add(report)
        db.commit()
        
        post = db.query(Post).filter(Post.id == post_id).first()
        if post:
            if post.report_count is None:
                post.report_count = 0
            post.report_count += 1

        db.commit()
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error reporting post: {str(e)}")

    return {"message": "Post reported successfully."}


async def report_user_svc(user_id: int, reported_by: int, reason: str, db: Session):
    try:
        if reason not in ReportReasonEnum.__members__:
            raise HTTPException(status_code=400, detail=f"Invalid reason: {reason}")
        
        existing_report = db.query(ReportUser).filter(
            ReportUser.user_id == user_id, ReportUser.reported_by == reported_by
        ).first()

        if existing_report:
            raise HTTPException(status_code=400, detail="You have already reported this user.")
        
        report = ReportUser(user_id=user_id, reported_by=reported_by, reason=reason)
        db.add(report)
        db.commit()
        
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            if user.report_count is None:
                user.report_count = 0
            user.report_count += 1
        
        db.commit()
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error reporting user: {str(e)}")
    
    return {"message": "User reported successfully."}


async def report_comment_svc(comment_id: int, reported_by: int, reason: str, db: Session):
    try:
        if reason not in ReportReasonEnum.__members__:
            raise HTTPException(status_code=400, detail=f"Invalid reason: {reason}")
        
        existing_report = db.query(ReportComment).filter(
            ReportComment.comment_id == comment_id, ReportComment.reported_by == reported_by
        ).first()

        if existing_report:
            raise HTTPException(status_code=400, detail="You have already reported this comment.")
        
        report = ReportComment(comment_id=comment_id, reported_by=reported_by, reason=reason)
        db.add(report)
        
        db.commit()
        comment = db.query(Comment).filter(Comment.id == comment_id).first()
        if comment:
            if comment.report_count is None:
                comment.report_count = 0
            comment.report_count += 1
        
        db.commit()
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error reporting comment: {str(e)}")
    
    return {"message": "Comment reported successfully."}


# async def report_chat_svc(thread_id: str, reported_by: int, reason: str, db: Session):
#     try:
#         existing_report = db.query(ReportChat).filter(
#             ReportChat.thread_id == thread_id, ReportChat.reported_by == reported_by
#         ).first()

#         if existing_report:
#             raise HTTPException(status_code=400, detail="You have already reported this chat.")
        
#         report = ReportChat(thread_id=thread_id, reported_by=reported_by, reason=reason)
#         db.add(report)
#         db.commit()
    
#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=400, detail=f"Error reporting chat: {str(e)}")
    
#     return {"message": "Chat reported successfully."}

async def get_reported_posts_by_user_svc(db: Session, user_id: int, page: int, limit: int):
    offset = (page - 1) * limit
    
    total_count = db.query(ReportPost).filter(ReportPost.reported_by == user_id).count()
    if total_count == 0:
        return {"total_count": 0, "page": page, "limit": limit, "total_pages": 0, "data": []}

    reports = db.query(ReportPost).filter(ReportPost.reported_by == user_id).order_by(ReportPost.created_at).offset(offset).limit(limit).all()

    post_ids = [report.post_id for report in reports]
    posts = db.query(Post).filter(Post.id.in_(post_ids)).all()

    report_dict = {report.post_id: report for report in reports}

    # Combine comment data with corresponding report reasons
    result = []
    for post in posts:
        report = report_dict.get(post.id)
        if report:
            result.append({
                **post.__dict__,
                "reason": report.reason
            })

    return {
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit,
        "data": result
    }


async def get_reported_users_by_user_svc(db: Session, user_id: int, page: int, limit: int):
    offset = (page - 1) * limit
    
    total_count = db.query(ReportUser).filter(ReportUser.reported_by == user_id).count()
    if total_count == 0:
        return {"total_count": 0, "page": page, "limit": limit, "total_pages": 0, "data": []}

    reports = db.query(ReportUser).filter(ReportUser.reported_by == user_id).order_by(ReportUser.created_at).offset(offset).limit(limit).all()

    user_ids = [report.user_id for report in reports]
    users = db.query(User).filter(User.id.in_(user_ids)).all()

    report_dict = {report.user_id: report for report in reports}

    # Combine comment data with corresponding report reasons
    result = []
    for user in users:
        report = report_dict.get(user.id)
        if report:
            result.append({
                **user.__dict__,
                "reason": report.reason
            })

    return {
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit,
        "data": result
    }


async def get_reported_comments_by_user_svc(db: Session, user_id: int, page: int, limit: int):
    offset = (page - 1) * limit
    
    total_count = db.query(ReportComment).filter(ReportComment.reported_by == user_id).count()
    if total_count == 0:
        return {"total_count": 0, "page": page, "limit": limit, "total_pages": 0, "data": []}

    reports = db.query(ReportComment).filter(ReportComment.reported_by == user_id).order_by(ReportComment.created_at).offset(offset).limit(limit).all()

    comment_ids = [report.comment_id for report in reports]
    comments = db.query(Comment).filter(Comment.id.in_(comment_ids)).all()

    report_dict = {report.comment_id: report for report in reports}

    # Combine comment data with corresponding report reasons
    result = []
    for comment in comments:
        report = report_dict.get(comment.id)
        if report:
            result.append({
                **comment.__dict__,
                "reason": report.reason
            })

    return {
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit,
        "data": result
    }


# async def get_reported_chats_by_user_svc(db: Session, user_id: int, page: int, limit: int):
#     offset = (page - 1) * limit
    
#     total_count = db.query(ReportChat).filter(ReportChat.reported_by == user_id).count()
#     if total_count == 0:
#         return {"total_count": 0, "page": page, "limit": limit, "total_pages": 0, "data": []}

#     reports = db.query(ReportChat).filter(ReportChat.reported_by == user_id).offset(offset).limit(limit).all()

#     thread_ids = [report.thread_id for report in reports]
#     chats = db.query(Chat_threads).filter(Chat_threads.thread_id.in_(thread_ids)).all()

#     result = [{
#         **chat.__dict__,
#         "reason": report.reason
#     } for chat, report in zip(chats, reports)]

#     return {
#         "total_count": total_count,
#         "page": page,
#         "limit": limit,
#         "total_pages": (total_count + limit - 1) // limit,
#         "data": result
#     }