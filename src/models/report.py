from sqlalchemy import Column, Integer, ForeignKey, DateTime, UniqueConstraint, String, Enum
from sqlalchemy.sql import func
from src.database import Base
from ..reports.enums import ReportReasonEnum

class ReportPost(Base):
    __tablename__ = "report_posts"
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    reported_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reason = Column(Enum(ReportReasonEnum), nullable=False, default=ReportReasonEnum.other)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("post_id", "reported_by", name="uix_post_report"),)


class ReportUser(Base):
    __tablename__ = "report_users"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reported_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reason = Column(Enum(ReportReasonEnum), nullable=False, default=ReportReasonEnum.other)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "reported_by", name="uix_user_report"),)


class ReportComment(Base):
    __tablename__ = "report_comments"
    id = Column(Integer, primary_key=True)
    comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=False)
    reported_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reason = Column(Enum(ReportReasonEnum), nullable=False, default=ReportReasonEnum.other)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("comment_id", "reported_by", name="uix_comment_report"),)


# class ReportChat(Base):
#     __tablename__ = "report_chats"
#     id = Column(Integer, primary_key=True)
#     thread_id = Column(String(255), ForeignKey("chat_threads.thread_id", ondelete="CASCADE"), nullable=False)
#     reported_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
#     reason = Column(ReportReasonEnum, nullable=False, default=ReportReasonEnum.other, server_default="other")
#     created_at = Column(DateTime(timezone=True), server_default=func.now())

#     __table_args__ = (UniqueConstraint("thread_id", "reported_by", name="uix_chat_report"),)