
# Camera Settings - BALANCED FOR QUALITY AND SPEED
CAMERA_INDEX = 0
CAMERA_WIDTH = 480  # Increased back for better quality
CAMERA_HEIGHT = 360  # Increased back for better quality
CAMERA_FPS = 30

# Model Paths
YOLO_WEIGHTS_PATH = r"F:\AlertEye\SafeDriveVision\weights\yolov5n_fresh.pt"
DLIB_SHAPE_PREDICTOR_PATH = r"./shape_predictor_81_face_landmarks (1).dat"

# Detection Thresholds - OPTIMIZED FOR ACCURACY
EAR_THRESH = 0.24 # Eye Aspect Ratio threshold (lower = more sensitive, increased from 0.27)
MAR_THRESH = 0.52   # Mouth Aspect Ratio threshold (higher = less sensitive)
PHONE_CONF_THRESH = 0.32  # Phone detection confidence threshold (balanced for accuracy vs false positives)

# Consecutive Frame Requirements - OPTIMIZED FOR FAST RESPONSE
EAR_CONSEC_FRAMES = 3      # Frames needed to confirm drowsiness
YAWN_CONSEC_FRAMES = 2     # Frames needed to confirm yawning
PHONE_CONSEC_FRAMES = 1    # Frames needed to confirm phone - instant detection
NOT_FORWARD_CONSEC_FRAMES = 12   # Frames needed to confirm not looking forward (increased - less sensitive)
HEAD_TILT_CONSEC_FRAMES = 3      # Frames needed to confirm head tilt (0.1 sec @ 30fps) - FAST RESPONSE

# Head Tilt Thresholds (degrees) - Based on 3D head pose roll angle
HEAD_TILT_THRESHOLD = 30   # Degrees of head roll before alert (balanced for real driving)
HEAD_TILT_CONSEC_FRAMES = 5     # Frames needed to confirm head tilt (0.16 sec @ 30fps)

# Performance Settings - OPTIMIZED FOR 25+ FPS WITH FAST ALERTS
YOLO_INTERVAL = 30          # Run YOLO every N frames (balanced for phone detection)
FACE_INTERVAL = 6          # Run face detection every N frames (balanced)
PROCESSING_SCALE = 0.9     # Minimal resizing for speed
TARGET_OUTPUT_FPS = 30.0   # Target output FPS
JPEG_QUALITY = 55          # Lower quality for faster encoding

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
YOLO_INPUT_SIZE = 416         # YOLO input size (higher = better detection but slower)
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


ENABLE_PERFORMANCE_LOGGING = True
LOG_INTERVAL_SECONDS = 5.0