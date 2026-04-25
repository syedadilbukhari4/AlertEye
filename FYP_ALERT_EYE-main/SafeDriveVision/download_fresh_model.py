"""
Download a fresh YOLOv5n model
"""
import torch
import os

def download_yolov5n():
    print("Downloading fresh YOLOv5n model...")
    try:
        # Download YOLOv5n model
        model = torch.hub.load('ultralytics/yolov5', 'yolov5n', pretrained=True, force_reload=True)
        
        # Save to weights directory
        weights_dir = "weights"
        os.makedirs(weights_dir, exist_ok=True)
        
        model_path = os.path.join(weights_dir, "yolov5n_fresh.pt")
        torch.save(model.state_dict(), model_path)
        
        print(f"Model saved to: {model_path}")
        print("Model download completed successfully!")
        
        return model_path
        
    except Exception as e:
        print(f"Error downloading model: {e}")
        return None

if __name__ == "__main__":
    download_yolov5n()