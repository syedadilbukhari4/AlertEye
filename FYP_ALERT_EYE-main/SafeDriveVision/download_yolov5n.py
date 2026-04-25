
import torch

# Download YOLOv5 nano model (much faster than medium)
model = torch.hub.load('ultralytics/yolov5', 'yolov5n', pretrained=True)

# Save it
torch.save(model.state_dict(), 'weights/yolov5n.pt')
print("✅ YOLOv5 Nano model downloaded successfully!")
print("📁 Saved to: weights/yolov5n.pt")