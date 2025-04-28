from azure.storage.blob import BlobServiceClient
from datetime import datetime, timezone
import os
from fastapi import UploadFile

from moviepy import VideoFileClip
from PIL import Image
from time import sleep
from io import BytesIO
from typing import Optional
import tempfile

import uuid
import subprocess

import json


# Azure Blob Storage Configuration
AZURE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=vreelsstorage;AccountKey=YkdFdR/UTuWKJnB4nmYJPV+NaqgsP9Vy3LVHIJ2R6m10jWM4v2a141Fh0HA+95BNs5PH6k/OTO2X+AStlUmb6Q==;EndpointSuffix=core.windows.net"
AZURE_IMAGE_CONTAINER = "images"
AZURE_VIDEO_CONTAINER = "videos"

CDN_BASE_URL = "https://vreelspostscdn-fmedgweqdkc6fah5.z01.azurefd.net"

# Initialize BlobServiceClient
blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)

# Define file extensions for images and videos
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"}
VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "wmv", "flv", "webm"}

FFMPEG = os.getenv("FFMPEG_PATH") or r"C:\ffmpeg\ffmpeg-7.1.1-essentials_build\bin\ffmpeg.exe"
FFPROBE = os.getenv("FFPROBE_PATH") or "C:\ffmpeg\ffmpeg-7.1.1-essentials_build\bin\ffprobe.exe"

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
            '''
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
            '''
            clip = VideoFileClip(temp_video.name)
            frame = clip.get_frame(3)
            thumbnail_image = Image.fromarray(frame)
            clip.close()

            # ✅ Save thumbnail to in-memory BytesIO (NOT to temp file)
            thumb_io = BytesIO()
            thumbnail_image.save(thumb_io, format="JPEG", optimize=True, quality=85)
            thumb_io.seek(0)

            # ✅ Upload from memory
            thumb_blob_name = f"{username}/{year}/{month}/{day}/thumbnails/{user_id}_{timestamp_str}.jpg"
            thumb_container_client = blob_service_client.get_container_client(AZURE_IMAGE_CONTAINER)
            thumb_blob_client = thumb_container_client.get_blob_client(thumb_blob_name)

            thumb_blob_client.upload_blob(thumb_io.read(), overwrite=True)


            thumbnail_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{AZURE_IMAGE_CONTAINER}/{thumb_blob_name}"

            #os.remove(temp_thumb.name)
        
        os.remove(temp_video.name)

        return media_url, media_type, thumbnail_url

    except Exception as e:
        raise Exception(f"Error uploading to Azure Blob: {e}")


async def upload_and_compress(file: UploadFile, username: str, user_id: str) -> tuple:
    now = datetime.now(timezone.utc)
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    file_ext = file.filename.split('.')[-1].lower()
    unique_name = f"{user_id}_{timestamp_str}.{file_ext}"

    if file_ext in IMAGE_EXTENSIONS:
        media_type = "image"
        container = AZURE_IMAGE_CONTAINER
        compressed_path = await compress_image(file)
    elif file_ext in VIDEO_EXTENSIONS:
        media_type = "video"
        container = AZURE_VIDEO_CONTAINER
        compressed_path = await compress_video(file)
    else:
        raise ValueError("Unsupported file type")

    # Upload to blob
    blob_path = f"{username}/{now.year}/{now.month}/{now.day}/{unique_name}"
    blob_client = blob_service_client.get_container_client(container).get_blob_client(blob_path)

    with open(compressed_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)

    os.remove(compressed_path)

    media_url = f"{CDN_BASE_URL}/{container}/{blob_path}"
    return media_url, media_type, None

async def compress_image(file: UploadFile) -> str:
    contents = await file.read()
    original_size = len(contents)  # in bytes

    try:
        img = Image.open(BytesIO(contents))
    except Exception as e:
        raise Exception("Invalid image file. " + str(e))

    temp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
    img = img.convert("RGB")
    img.save(temp_path, format="JPEG", optimize=True, quality=85)

    compressed_size = os.path.getsize(temp_path)  # in bytes

    print(f"🧾 Original: {original_size / 1024:.2f} KB | Compressed: {compressed_size / 1024:.2f} KB")
    return temp_path


async def compress_video(file: UploadFile) -> str:
    """Optimized video compression with proper file handling."""
    # Create temp files with unique names
    raw_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    compressed_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    
    # Write the uploaded file content
    content = await file.read()
    with open(raw_path, "wb") as f:
        f.write(content)
    
    original_size = os.path.getsize(raw_path)
    print(f"📦 Original video size: {original_size / (1024*1024):.2f} MB") 

    try:
        # First pass - video only (faster)
        subprocess.run([
            FFMPEG, "-y",
            "-i", raw_path,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "30",
            "-movflags", "+faststart",
            "-threads", "4",
            "-x264-params", "ref=1:bframes=0",
            "-an",  # No audio in first pass
            compressed_path
        ], check=True)

        # Second pass - add audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
            final_path = temp_file.name
        
        subprocess.run([
            FFMPEG, "-y",
            "-i", compressed_path,  # Compressed video
            "-i", raw_path,         # Original audio
            "-c:v", "copy",         # Copy compressed video
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            final_path
        ], check=True)

        
        # Get final compressed size
        final_size = os.path.getsize(final_path)
        print(f"✅ Final compressed size: {final_size / (1024*1024):.2f} MB")
        print(f"🔽 Final compression ratio: {final_size/original_size:.2%}")
        print(f"💾 Space saved: {(original_size - final_size) / (1024*1024):.2f} MB")

        # Clean up intermediate files
        os.remove(compressed_path)
        os.remove(raw_path)

        return final_path

    except subprocess.CalledProcessError as e:
        # Clean up any remaining files on error
        for path in [raw_path, compressed_path, final_path]:
            if path and os.path.exists(path):
                os.remove(path)
        raise Exception(f"Video compression failed: {str(e)}")


'''
async def compress_video(file: UploadFile) -> str:
    """Optimized video compression with conditional audio muxing, no file locking issues."""
    raw_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    compressed_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    final_path: Optional[str] = None

    try:
        # Save uploaded file to disk
        content = await file.read()
        with open(raw_path, "wb") as f:
            f.write(content)

        original_size = os.path.getsize(raw_path)
        print(f"📦 Original video size: {original_size / (1024*1024):.2f} MB")

        # First pass: compress video only (no audio)
        subprocess.run([
            FFMPEG, "-y",
            "-i", raw_path,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "30",
            "-movflags", "+faststart",
            "-threads", "4",
            "-x264-params", "ref=1:bframes=0",
            "-an",
            compressed_path
        ], check=True)

        # 🔥 New: Check for audio presence safely
        has_audio = has_audio_stream_ffmpeg(raw_path)

        if has_audio:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
                final_path = temp_file.name

            subprocess.run([
                FFMPEG, "-y",
                "-i", compressed_path,
                "-i", raw_path,
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                final_path
            ], check=True)

            os.remove(compressed_path)
        else:
            print("⚠️ No audio stream detected. Using video-only output.")
            final_path = compressed_path

        final_size = os.path.getsize(final_path)
        print(f"✅ Final compressed size: {final_size / (1024*1024):.2f} MB")
        print(f"🔽 Final compression ratio: {final_size/original_size:.2%}")
        print(f"💾 Space saved: {(original_size - final_size) / (1024*1024):.2f} MB")

        return final_path

    except subprocess.CalledProcessError as e:
        print("❌ FFmpeg failed:", e)
        raise Exception(f"Video compression failed: {str(e)}")

    finally:
        for path in [raw_path, compressed_path]:
            if os.path.exists(path):
                os.remove(path)


def has_audio_stream_ffmpeg(file_path: str) -> bool:
    """Use ffmpeg to check for audio stream without locking file."""
    try:
        result = subprocess.run([
            FFMPEG, "-i", file_path,
            "-map", "0:a:0", "-f", "null", "-"
        ], capture_output=True, text=True)
        if "matches no streams" in result.stderr.lower():
            return False
        return True
    except Exception as e:
        print(f"⚠️ Audio stream check failed: {e}")
        return False
'''