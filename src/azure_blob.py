from azure.storage.blob import BlobServiceClient
from datetime import datetime, timezone
import os
from fastapi import UploadFile
from moviepy import VideoFileClip
from PIL import Image
import tempfile
import uuid

# Azure Blob Storage Configuration
AZURE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=vreelsstorage;AccountKey=YkdFdR/UTuWKJnB4nmYJPV+NaqgsP9Vy3LVHIJ2R6m10jWM4v2a141Fh0HA+95BNs5PH6k/OTO2X+AStlUmb6Q==;EndpointSuffix=core.windows.net"
AZURE_IMAGE_CONTAINER = "images"
AZURE_VIDEO_CONTAINER = "videos"

# Initialize BlobServiceClient
blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)

# Define file extensions for images and videos
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"}
VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "wmv", "flv", "webm"}

<<<<<<< Updated upstream
=======
FFMPEG = os.getenv("FFMPEG_PATH") or "/home/site/wwwroot/bin/ffmpeg" or r"C:\ffmpeg\ffmpeg-7.1.1-essentials_build\bin\ffmpeg.exe"


>>>>>>> Stashed changes
async def upload_to_azure_blob(file: UploadFile, username: str, user_id: str) -> tuple:
    now = datetime.now(timezone.utc)
    year, month, day = now.strftime("%Y"), now.strftime("%m"), now.strftime("%d")
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    
    file_extension = file.filename.split(".")[-1].lower()
    unique_filename = f"{user_id}_{timestamp_str}.{file_extension}"
    
    try:
        if file_extension in IMAGE_EXTENSIONS:
            container_name = AZURE_IMAGE_CONTAINER
            media_type = "image"
        elif file_extension in VIDEO_EXTENSIONS:
            container_name = AZURE_VIDEO_CONTAINER
            media_type = "video"
        else:
            raise ValueError("Unsupported file type. Please upload an image or a video.")
        
        container_client = blob_service_client.get_container_client(container_name)
        blob_name = f"{username}/{year}/{month}/{day}/{unique_filename}"
        blob_client = container_client.get_blob_client(blob_name)

        # Save file to temp for further processing
        temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}")
        contents = await file.read()
        temp_video.write(contents)
        temp_video.close()

        # Upload the media
        blob_client.upload_blob(contents, overwrite=True)
        media_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{blob_name}"

        thumbnail_url = None
        if media_type == "video":
            # Generate thumbnail
            clip = VideoFileClip(temp_video.name)
            frame = clip.get_frame(3)  # Get frame at 3 seconds
            thumbnail_image = Image.fromarray(frame)
            temp_thumb = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            thumbnail_image.save(temp_thumb.name)
            clip.close()

            # Upload thumbnail
            thumb_blob_name = f"{username}/{year}/{month}/{day}/thumbnails/{user_id}_{timestamp_str}.jpg"
            thumb_container_client = blob_service_client.get_container_client(AZURE_IMAGE_CONTAINER)
            thumb_blob_client = thumb_container_client.get_blob_client(thumb_blob_name)

            with open(temp_thumb.name, "rb") as thumb_file:
                thumb_blob_client.upload_blob(thumb_file, overwrite=True)

            thumbnail_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{AZURE_IMAGE_CONTAINER}/{thumb_blob_name}"

            os.remove(temp_thumb.name)
        
        os.remove(temp_video.name)

        return media_url, media_type, thumbnail_url

    except Exception as e:
        raise Exception(f"Error uploading to Azure Blob: {e}")
