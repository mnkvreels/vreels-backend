from sqlalchemy import VARCHAR
from sqlalchemy.orm import Session
from fastapi import HTTPException
from ..models.report import ReportPost, ReportUser, ReportComment, ReportReason, ReportPouch, ReportPouchComment
from ..models.post import Comment, Post, Pouch, PouchComment
from ..models.user import User
from .enums import ReportReasonEnum

async def report_post_svc(post_id: int, reported_by: int, reason: str, description: str, db: Session):
    try:
        # Check if the post exists
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=400, detail="Post does not exist.")
        
        existing_report = db.query(ReportPost).filter(
            ReportPost.post_id == post_id,
            ReportPost.reported_by == reported_by
        ).first()
        if existing_report:
            raise HTTPException(status_code=400, detail="You have already reported this post.")

        # Check if the reason exists, if not raise an exception
        report_reason = db.query(ReportReason).filter(ReportReason.report_reason_name == reason).first()
        if not report_reason:
            raise HTTPException(status_code=400, detail="Invalid report reason.")

        # Insert report
        report = ReportPost(
            post_id=post_id,
            reported_by=reported_by,
            report_reason_id=report_reason.report_reason_id,
            report_reason=report_reason.report_reason_name,
            description=description
        )
        db.add(report)
        post = db.query(Post).filter(Post.id == post_id).first()
        if post:
            post.report_count = (post.report_count or 0) + 1

        db.commit()

    except HTTPException as e:  # Catch HTTPException separately
        raise e  # Re-raise the HTTPException with the specific message
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error reporting post: {str(e)}")

    return {"message": "Post reported successfully."}


async def report_user_svc(user_id: int, reported_by: int, reason: str,  description: str, db: Session):
    try:
        # Check if the user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=400, detail="User does not exist.")
        
        existing_report = db.query(ReportUser).filter(
            ReportUser.user_id == user_id,
            ReportUser.reported_by == reported_by
        ).first()
        if existing_report:
            raise HTTPException(status_code=400, detail="You have already reported this user.")

        # Check if the reason exists, if not raise an exception
        report_reason = db.query(ReportReason).filter(ReportReason.report_reason_name.ilike(reason)).first()
        if not report_reason:
            raise HTTPException(status_code=400, detail="Invalid report reason.")

        # Insert report
        report = ReportUser(
            user_id=user_id,
            reported_by=reported_by,
            report_reason_id=report_reason.report_reason_id,
            report_reason=report_reason.report_reason_name,
            description=description
        )
        db.add(report)
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.report_count = (user.report_count or 0) + 1
        
        db.commit()
    
    except HTTPException as e:  # Catch HTTPException separately
        raise e  # Re-raise the HTTPException with the specific message
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error reporting user: {str(e)}")
    
    return {"message": "User reported successfully."}


async def report_comment_svc(comment_id: int, reported_by: int, reason: str,  description: str, db: Session):
    try:
        # Check if the comment exists
        comment = db.query(Comment).filter(Comment.id == comment_id).first()
        if not comment:
            raise HTTPException(status_code=400, detail="Comment does not exist.")

        existing_report = db.query(ReportComment).filter(
            ReportComment.comment_id == comment_id,
            ReportComment.reported_by == reported_by
        ).first()

        if existing_report:
            raise HTTPException(status_code=400, detail="You have already reported this comment.")

        # Check if the reason exists, if not raise an exception
        report_reason = db.query(ReportReason).filter(ReportReason.report_reason_name.ilike(reason)).first()
        if not report_reason:
            raise HTTPException(status_code=400, detail="Invalid report reason.")

        # Insert report
        report = ReportComment(
            comment_id=comment_id,
            reported_by=reported_by,
            report_reason_id=report_reason.report_reason_id,
            report_reason=report_reason.report_reason_name,
            description=description
        )
        db.add(report)
        
        comment = db.query(Comment).filter(Comment.id == comment_id).first()
        if comment:
            comment.report_count = (comment.report_count or 0) + 1
        db.commit()
    
    except HTTPException as e:  # Catch HTTPException separately
        raise e  # Re-raise the HTTPException with the specific message
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

async def report_pouch_svc(pouch_id: int, reported_by: int, reason: str, description: str, db: Session):
    try:
        pouch = db.query(Pouch).filter(Pouch.id == pouch_id).first()
        if not pouch:
            raise HTTPException(status_code=400, detail="Pouch does not exist.")
        
        existing_report = db.query(ReportPouch).filter_by(pouch_id=pouch_id, reported_by=reported_by).first()
        if existing_report:
            raise HTTPException(status_code=400, detail="You have already reported this pouch.")

        report_reason = db.query(ReportReason).filter(ReportReason.report_reason_name.ilike(reason)).first()
        if not report_reason:
            raise HTTPException(status_code=400, detail="Invalid report reason.")

        report = ReportPouch(
            pouch_id=pouch_id,
            reported_by=reported_by,
            report_reason_id=report_reason.report_reason_id,
            report_reason=report_reason.report_reason_name,
            description=description
        )
        db.add(report)

        pouch.report_count = (pouch.report_count or 0) + 1

        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error reporting pouch: {str(e)}")

    return {"message": "Pouch reported successfully."}

async def report_pouch_comment_svc(comment_id: int, reported_by: int, reason: str, description: str, db: Session):
    try:
        comment = db.query(PouchComment).filter(PouchComment.id == comment_id).first()
        if not comment:
            raise HTTPException(status_code=400, detail="Comment does not exist.")

        existing_report = db.query(ReportPouchComment).filter_by(comment_id=comment_id, reported_by=reported_by).first()
        if existing_report:
            raise HTTPException(status_code=400, detail="You have already reported this comment.")

        report_reason = db.query(ReportReason).filter(ReportReason.report_reason_name.ilike(reason)).first()
        if not report_reason:
            raise HTTPException(status_code=400, detail="Invalid report reason.")

        report = ReportPouchComment(
            comment_id=comment_id,
            reported_by=reported_by,
            report_reason_id=report_reason.report_reason_id,
            report_reason=report_reason.report_reason_name,
            description=description
        )
        db.add(report)

        comment.report_count = (comment.report_count or 0) + 1

        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error reporting pouch comment: {str(e)}")

    return {"message": "Pouch comment reported successfully."}
