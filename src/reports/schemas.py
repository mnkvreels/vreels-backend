from pydantic import BaseModel
from sqlalchemy import VARCHAR
from .enums import ReportReasonEnum

class ReportPostRequest(BaseModel):
    post_id: int
    reason: ReportReasonEnum

class ReportUserRequest(BaseModel):
    user_id: int
    reason: ReportReasonEnum

class ReportCommentRequest(BaseModel):
    comment_id: int
    reason: ReportReasonEnum

# class ReportChatRequest(BaseModel):
#     thread_id: str
#     reason: ReportReasonEnum