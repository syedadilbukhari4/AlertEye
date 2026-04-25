"""
Configuration file for SafeDriveVision
Adjust these parameters to fine-tune performance and accuracy
"""

# Camera Settings
CAMERA_INDEX = 0
CAMERA_WIDTH = 640  # Reduced from 1280 for faster processing
CAMERA_HEIGHT = 480  # Reduced from 720 for faster processing
CAMERA_FPS = 30

# Model Paths
YOLO_WEIGHTS_PATH = r"F:\AlertEye\SafeDriveVision\weights\yolov5n_fresh.pt"
DLIB_SHAPE_PREDICTOR_PATH = r"./shape_predictor_81_face_landmarks (1).dat"

# Detection Thresholds - OPTIMIZED FOR ACCURACY
EAR_THRESH = 0.27 # Eye Aspect Ratio threshold (lower = more sensitive)
MAR_THRESH = 0.52   # Mouth Aspect Ratio threshold (higher = less sensitive)
PHONE_CONF_THRESH = 0.25  # Phone detection confidence threshold (lowered for better detection)

# Consecutive Frame Requirements - BALANCED FOR ACCURACY
EAR_CONSEC_FRAMES = 6      # Frames needed to confirm drowsiness
YAWN_CONSEC_FRAMES = 4     # Frames needed to confirm yawning
PHONE_CONSEC_FRAMES = 2    # Frames needed to confirm phone
NOT_FORWARD_CONSEC_FRAMES = 8   # Frames needed to confirm not looking forward
HEAD_TILT_CONSEC_FRAMES = 8     # Frames needed to confirm head tilt

# Head Angle Thresholds (degrees)
HEAD_ANGLE_MIN = 70   # Minimum acceptable head angle
HEAD_ANGLE_MAX = 115  # Maximum acceptable head angle

# Performance Settings
YOLO_INTERVAL = 10          # Run YOLO every N frames (less frequent for speed)
FACE_INTERVAL = 2          # Run face detection every N frames (less frequent for speed)
PROCESSING_SCALE = 0.5     # Scale factor for processing (0.5-1.0) - lower is faster
TARGET_OUTPUT_FPS = 25.0   # Target output FPS
JPEG_QUALITY = 60          # JPEG compression quality (1-100) - lower is faster

# Smoothing Filter Settings
EAR_SMOOTHING_ALPHA = 0.4      # EAR exponential smoothing factor
MAR_SMOOTHING_ALPHA = 0.3      # MAR exponential smoothing factor
MEDIAN_FILTER_SIZE = 5         # Median filter window size

# Hysteresis Settings (prevents flickering)
EAR_HYSTERESIS_LOW = 0.24      # Lower threshold for eye closing
EAR_HYSTERESIS_HIGH = 0.30     # Upper threshold for eye opening
MAR_HYSTERESIS_LOW = 0.47      # Lower threshold for yawn end
MAR_HYSTERESIS_HIGH = 0.57     # Upper threshold for yawn start

# Confidence Tracker Settings
PHONE_CONFIDENCE_WINDOW = 8        # Window size for phone detection confidence
PHONE_CONFIDENCE_THRESH = 0.6      # Confidence threshold for phone alert
FORWARD_CONFIDENCE_WINDOW = 12     # Window size for forward looking confidence
FORWARD_CONFIDENCE_THRESH = 0.7    # Confidence threshold for forward alert

# Adaptive Threshold Settings
ADAPTIVE_EAR_RATE = 0.005     # Adaptation rate for EAR threshold
ADAPTIVE_MAR_RATE = 0.005     # Adaptation rate for MAR threshold

# YOLO Settings
YOLO_INPUT_SIZE = 640         # YOLO input size (higher = better detection but slower)
PHONE_CLASS_ID = 67           # COCO class ID for cell phone
REMOTE_CLASS_ID = 75          # COCO class ID for remote (sometimes detected as phone)

# Alert Messages
ALERT_MESSAGES = {
    'eye_closed': 'DROWSINESS DETECTED!',
    'yawning': 'YAWNING DETECTED!',
    'phone_detected': 'PUT DOWN PHONE!',
    'not_looking_forward': 'LOOK FORWARD!',
    'head_tilt_alert': 'STRAIGHTEN HEAD!'
}

# Color Codes (BGR format)
COLORS = {
    'alert': (0, 0, 255),      # Red
    'normal': (0, 255, 0),     # Green
    'warning': (0, 255, 255),  # Yellow
    'info': (255, 255, 0),     # Cyan
}

# Performance Monitoring
ENABLE_PERFORMANCE_LOGGING = True
LOG_INTERVAL_SECONDS = 5.0