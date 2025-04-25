import enum

class ReportReasonEnum(str, enum.Enum):
    spam = "spam"
    abuse = "abuse"
    nudity = "nudity"
    hate_speech = "hate_speech"
    misinformation = "misinformation"
    harassment = "harassment"
    other = "other"
    
class ReportEnum(str, enum.Enum):
    BUG = "Bug"
    OTHER = "Other"