import os
import torch
from PIL import Image
import cv2
from pathlib import Path
from transformers import CLIPProcessor, CLIPModel
from azure.storage.blob import BlobServiceClient
#from dotenv import load_dotenv

AZURE_CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING","DefaultEndpointsProtocol=https;AccountName=vreelsstorage;AccountKey=YkdFdR/UTuWKJnB4nmYJPV+NaqgsP9Vy3LVHIJ2R6m10jWM4v2a141Fh0HA+95BNs5PH6k/OTO2X+AStlUmb6Q==;EndpointSuffix=core.windows.net")
MODEL_CONTAINER = "category-prediction-models"
MODEL_PREFIX = "Model_test"  # Folder name in the blob container
LOCAL_MODEL_DIR = Path("/tmp/clip-model")  # App Service supports /tmp for writes
LOCAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Required files in the model
REQUIRED_FILES = [
    "config.json",
    "pytorch_model.bin",
    "preprocessor_config.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "merges.txt",
    "vocab.json"
]

# ✅ Setup blob service
blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(MODEL_CONTAINER)

# ✅ Download if not already cached
for file_name in REQUIRED_FILES:
    blob_path = f"{MODEL_PREFIX}/{file_name}"  # Full path in blob
    local_path = LOCAL_MODEL_DIR / file_name

    if not local_path.exists():
        print(f"⬇️ Downloading: {blob_path}")
        blob_client = container_client.get_blob_client(blob_path)
        with open(local_path, "wb") as f:
            f.write(blob_client.download_blob().readall())

# ✅ Load CLIP model
clip_model = CLIPModel.from_pretrained(str(LOCAL_MODEL_DIR)).eval()
clip_processor = CLIPProcessor.from_pretrained(str(LOCAL_MODEL_DIR))


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
clip_model.to(device)

categories = [
    "person", "Group of people","Fashion & Style", "Food & Cooking", "Fitness & Sports", "Travel & Nature",
    "Animals & Pets", "Technology & Gadgets", "Art & Design", "Music & Dance",
    "Movies & TV Shows", "Gaming", "News & Current Events", "Business & Finance",
    "Self-care & Wellness", "Health & Medical", "Education & Learning", "DIY & Crafts",
    "Beauty & Makeup", "Automobiles & Vehicles", "Home Decor & Architecture",
    "Parenting & Family", "Comedy & Memes", "Inspiration & Quotes", "Politics & Activism",
    "History & Culture", "Relationships & Dating", "Photography & Videography",
    "Luxury & Lifestyle", "Events & Celebrations"
]

def predict_category_image(image_path: Path) -> str:
    image = Image.open(str(image_path)).convert("RGB")
    inputs = clip_processor(text=categories, images=image, return_tensors="pt", padding=True).to(device)
    with torch.no_grad():
        outputs = clip_model(**inputs)
        probs = outputs.logits_per_image.softmax(dim=1)
    return categories[probs.argmax().item()]

def predict_category_video(video_path: Path, frame_skip: int = 10, batch_size: int = 8) -> str:
    cap = cv2.VideoCapture(str(video_path))
    frames = []
    frame_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if frame_count % frame_skip == 0:
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            frames.append(image)
        frame_count += 1
    cap.release()

    if not frames:
        return "Unknown"

    all_probs = []
    for i in range(0, len(frames), batch_size):
        batch = frames[i:i + batch_size]
        inputs = clip_processor(text=categories, images=batch, return_tensors="pt", padding=True).to(device)
        with torch.no_grad():
            outputs = clip_model(**inputs)
            probs = outputs.logits_per_image.softmax(dim=1)
        all_probs.append(probs.cpu())

    avg_probs = torch.cat(all_probs).mean(dim=0)
    return categories[torch.argmax(avg_probs).item()]


