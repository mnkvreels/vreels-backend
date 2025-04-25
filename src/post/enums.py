import enum

class VisibilityEnum(str, enum.Enum):
    public = "public"
    private = "private"
    friends = "friends"

class MediaTypeEnum(str, enum.Enum):
    image = "image"
    video = "video"