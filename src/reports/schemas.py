from pydantic import BaseModel
from datetime import datetime
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

class ReportPouchRequest(BaseModel):
    pouch_id: int
    description: Optional[str] = None
    reason: ReportReasonEnum

class ReportPouchCommentRequest(BaseModel):
    comment_id: int
    description: Optional[str] = None
    reason: ReportReasonEnum

class ReportReasonResponse(BaseModel):
    report_reason_id: int
    report_reason_name: str
    created_at: datetime

    class Config:
        orm_mode = True

class ReportIssueRequest(BaseModel):
    report_reason: ReportEnum
    description: Optional[str]

# class ReportChatRequest(BaseModel):
#     thread_id: str
#     reason: ReportReasonEnum