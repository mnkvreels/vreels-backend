import requests
import tempfile
import os
from moviepy.editor import VideoFileClip


# ✅ STEP 4: Function to get real video duration from URL
def get_video_duration_from_url(video_url: str) -> int:
    try:
        response = requests.get(video_url, stream=True)
        if response.status_code != 200:
            print("❌ Download failed:", response.status_code)
            return 0

        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            tmp_file.write(chunk)
        tmp_file.close()

        clip = VideoFileClip(tmp_file.name)
        duration = int(clip.duration)
        clip.close()

        os.unlink(tmp_file.name)
        return duration
    except Exception as e:
        print("❌ Error getting video duration:", e)
        return 0

# ✅ STEP 1: Import your existing DB connection and Post model
from src.database import SessionLocal  # Adjust if path is different
from src.models import Post            # Make sure Post has media_url and media_type

# ✅ STEP 2: Create DB session
db = SessionLocal()

# ✅ STEP 3: Query one video post from DB
video_post = db.query(Post).filter(
    Post.media_type == "video",
    Post.media.isnot(None),
    Post.media != ''
).first()

video_url = video_post.media
print("🎯 Video URL from DB:", video_url)

if not video_url:
    print("❌ No video URL found in the post.")
    exit()

duration = get_video_duration_from_url(video_url)
print("🎥 Actual Video Duration:", duration, "seconds")
