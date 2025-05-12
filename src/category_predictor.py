import torch
from PIL import Image
import cv2
from pathlib import Path
from transformers import CLIPProcessor, CLIPModel

# Load the CLIP model
clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
clip_model.eval()

# Use GPU if available
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

# File path (change this path to your input file)
#input_path = r"C:\Users\tirum\OneDrive\Desktop\WORK\pexels\videos\video_1154850.mp4" # or .jpg, .png, etc.
#input_file = Path(input_path)

video_extensions = ['.mp4', '.mov', '.avi', '.mkv']
image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']


def predict_category(file_path: str) -> str:
    input_file = Path(file_path)

    if input_file.suffix.lower() in video_extensions:
        return _process_video(input_file)
    elif input_file.suffix.lower() in image_extensions:
        return _process_image(Image.open(input_file).convert("RGB"))
    else:
        raise ValueError("Unsupported file format. Only image or video files are allowed.")

def process_image(image: Image.Image):
    """
    Process a single image with CLIP and print its top predicted category and confidence.
    """
    inputs = clip_processor(text=categories, images=image, return_tensors="pt", padding=True).to(device)
    with torch.no_grad():
        outputs = clip_model(**inputs)
        logits = outputs.logits_per_image
        probs = logits.softmax(dim=1)
    top_idx = probs.argmax().item()
    predicted_category = categories[top_idx]
    confidence = probs[0][top_idx].item()
    print(f"🔵 Image Prediction: {predicted_category} ({confidence * 100:.2f}%)")
    return predicted_category


def process_video(video_file: Path, frame_skip=10, batch_size=16):
    """
    Process a video, extracting frames every `frame_skip` frames, batching them, and producing
    one final prediction by averaging the frame predictions.
    """
    cap = cv2.VideoCapture(str(video_file))
    frame_count = 0
    batched_images = []

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % frame_skip == 0:
            # Convert frame (BGR) to PIL Image (RGB)
            pil_frame = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            batched_images.append(pil_frame)
        frame_count += 1
    cap.release()

    if not batched_images:
        print("No frames were extracted from the video.")
        return RuntimeError("No frames extracyted from video")

    all_probs = []
    for i in range(0, len(batched_images), batch_size):
        batch = batched_images[i:i + batch_size]
        inputs = clip_processor(text=categories, images=batch, return_tensors="pt", padding=True).to(device)
        with torch.no_grad():
            outputs = clip_model(**inputs)
            logits = outputs.logits_per_image
            probs = logits.softmax(dim=1)  # shape: (batch_size, num_categories)
        all_probs.append(probs.cpu())

    all_probs_tensor = torch.cat(all_probs, dim=0)
    avg_probs = torch.mean(all_probs_tensor, dim=0)  # shape: (num_categories,)
    top_idx = torch.argmax(avg_probs).item()
    predicted_category = categories[top_idx]
    confidence = avg_probs[top_idx].item()
    print(f"🎥 Video Final Prediction: {predicted_category} ({confidence * 100:.2f}%)")
    return top_idx


