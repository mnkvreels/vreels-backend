from azure.storage.blob import BlobServiceClient
import os
from fastapi import UploadFile
import uuid

# Azure Blob Storage Configuration
AZURE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=vreelsstorage;AccountKey=YkdFdR/UTuWKJnB4nmYJPV+NaqgsP9Vy3LVHIJ2R6m10jWM4v2a141Fh0HA+95BNs5PH6k/OTO2X+AStlUmb6Q==;EndpointSuffix=core.windows.net"
AZURE_IMAGE_CONTAINER="images"
AZURE_VIDEO_CONTAINER="videos"

# Initialize BlobServiceClient
blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)

# Define file extensions for images and videos
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"}
VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "wmv", "flv", "webm"}

async def upload_to_azure_blob(file: UploadFile) -> str:
    try:
        # Extract file extension
        file_extension = file.filename.split(".")[-1].lower()

        # Determine the correct container based on file extension
        if file_extension in IMAGE_EXTENSIONS:
            container_name = AZURE_IMAGE_CONTAINER
        elif file_extension in VIDEO_EXTENSIONS:
            container_name = AZURE_VIDEO_CONTAINER
        else:
            raise ValueError("Unsupported file type. Please upload an image or a video.")
        # Get the container client
        container_client = blob_service_client.get_container_client(container_name)

        # Generate a unique file name
        blob_name = f"uploads/{uuid.uuid4()}.{file_extension}"

        # Upload file
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(await file.read(), overwrite=True)

        # Return the file URL
        blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{blob_name}"
        return blob_url
    except Exception as e:
        raise Exception(f"Error uploading to Azure Blob: {e}")
