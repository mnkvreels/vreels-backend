from pydantic import BaseModel
from sqlalchemy import VARCHAR
from .enums import ReportReasonEnum, ReportEnum
from typing import Optional

class ReportPostRequest(BaseModel):
    post_id: int
    description: Optional[str] = None
    reason: ReportReasonEnum

class ReportUserRequest(BaseModel):
    user_id: int
    description: Optional[str] = None
    reason: ReportReasonEnum

class ReportCommentRequest(BaseModel):
    comment_id: int
    description: Optional[str] = None
    reason: ReportReasonEnum

class ReportIssueRequest(BaseModel):
    report_reason: ReportEnum
    description: Optional[str]

# class ReportChatRequest(BaseModel):
#     thread_id: str
#     reason: ReportReasonEnum