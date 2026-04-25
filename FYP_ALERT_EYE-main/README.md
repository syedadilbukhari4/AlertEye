# SafeDriveVision - Driver Monitoring System

Real-time driver monitoring system using AI to detect drowsiness, yawning, phone usage, and distraction. Features a Python backend with FastAPI and a Flutter mobile-style UI.

## Features

- **Drowsiness Detection**: Eye Aspect Ratio (EAR) monitoring
- **Yawning Detection**: Mouth Aspect Ratio (MAR) analysis
- **Phone Detection**: YOLOv5-based object detection
- **Distraction Alerts**: Head pose and gaze direction tracking
- **Real-time Video**: MJPEG streaming with overlay annotations
- **Mobile UI**: Flutter app with phone frame simulator
- **Alert System**: Visual and counter-based alert tracking

## System Architecture

```
┌─────────────────┐         HTTP/REST API          ┌──────────────┐
│                 │◄──────────────────────────────►│              │
│  FLUTTER APP    │   GET /mjpeg (video)           │   BACKEND    │
│  (Frontend)     │   GET /alerts (data)           │  (Python)    │
│                 │   GET /health (status)          │              │
└─────────────────┘                                 └──────────────┘
       │                                                    │
       │                                                    │
       ▼                                                    ▼
Mobile UI Display                                    Camera + AI
- Video feed                                         - Face detection
- Alert boxes                                        - YOLO phone detect
- Counters                                           - Alert generation
- Status badge                                       - Video streaming
```

## Prerequisites

### Backend (Python)
- Python 3.11+
- Webcam/Camera
- Windows OS (tested on Windows)

### Frontend (Flutter)
- Flutter SDK 3.0+
- Windows desktop support enabled

## Installation

### 1. Clone Repository
```bash
git clone <repository-url>
cd AlertEye
```

### 2. Setup Python Backend

#### Create Virtual Environment
```bash
python -m venv myenv_311
myenv_311\Scripts\activate
```

#### Install Dependencies
```bash
cd SafeDriveVision
pip install --upgrade pip
pip install -r requirements.txt
```

#### Download Models
```bash
# Download YOLOv5 model
python download_yolov5n.py

# Download dlib face landmarks (if not included)
# Place shape_predictor_81_face_landmarks.dat in SafeDriveVision/
```

### 3. Setup Flutter Frontend

```bash
cd flutter_app
flutter pub get
```

## Running the Application

### Quick Start (2 Terminal Windows Required)

#### Window 1: Start Backend
```bash
cd F:\AlertEye
myenv_311\Scripts\activate
cd SafeDriveVision
uvicorn app:app --host 0.0.0.0 --port 8000 --log-level info
```

**Wait for:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
🚀 SafeDriveVision Backend Started
```

#### Window 2: Start Flutter App
```bash
cd F:\AlertEye\flutter_app
flutter run -d windows
```

**Or use the mobile simulator:**
```bash
.\run_mobile.bat
```

### Verification

#### Test Backend Health
Open browser: `http://localhost:8000/health`

Should return:
```json
{
  "status": "ok",
  "mode": "real-time",
  "version": "2.0",
  "description": "Alerts only - camera handled by client"
}
```

#### Test Video Stream
Open browser: `http://localhost:8000/mjpeg`

Should show live camera feed with detection overlays.

#### Test Alerts API
Open browser: `http://localhost:8000/alerts`

Should return:
```json
{
  "eye_closed": false,
  "yawning": false,
  "phone_detected": false,
  "not_looking_forward": false,
  "head_tilt_alert": false,
  "timestamp": 1234567890
}
```

## Configuration

### Backend Configuration
Edit `SafeDriveVision/config.py`:

```python
# Camera Settings
CAMERA_INDEX = 0          # Change if using external camera
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_FPS = 30

# Detection Thresholds
EAR_THRESH = 0.27         # Eye Aspect Ratio (lower = more sensitive)
MAR_THRESH = 0.52         # Mouth Aspect Ratio (higher = less sensitive)
PHONE_CONF_THRESH = 0.25  # Phone detection confidence

# Consecutive Frame Requirements
EAR_CONSEC_FRAMES = 6     # Frames needed to confirm drowsiness
YAWN_CONSEC_FRAMES = 4    # Frames needed to confirm yawning
PHONE_CONSEC_FRAMES = 2   # Frames needed to confirm phone

# Performance Settings
YOLO_INTERVAL = 3         # Run YOLO every N frames
TARGET_OUTPUT_FPS = 25.0  # Target output FPS
JPEG_QUALITY = 75         # JPEG compression quality
```

### Flutter Configuration
Edit `flutter_app/lib/config/app_config.dart`:

```dart
static const String baseUrl = 'http://localhost:8000';
static const Duration pollingInterval = Duration(milliseconds: 200);
static const Duration connectionTimeout = Duration(seconds: 1);
```

## API Endpoints

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "mode": "real-time",
  "version": "2.0"
}
```

### GET /alerts
Get current alert status.

**Response:**
```json
{
  "eye_closed": boolean,
  "yawning": boolean,
  "phone_detected": boolean,
  "not_looking_forward": boolean,
  "head_tilt_alert": boolean,
  "timestamp": integer
}
```

### GET /mjpeg
MJPEG video stream with detection overlays.

**Response:** Multipart MJPEG stream

## Troubleshooting

### Backend Not Responding
**Symptoms:** Timeout errors, backend stuck

**Solutions:**
1. Stop backend (Ctrl+C)
2. Close apps using camera (Zoom, Teams, etc.)
3. Restart backend
4. Check camera permissions

### Connection Timeout in Flutter
**Symptoms:** "TimeoutException" errors

**Solutions:**
1. Verify backend is running: `http://localhost:8000/health`
2. Check firewall settings
3. Ensure both apps use same port (8000)

### Camera Not Opening
**Symptoms:** "Cannot open webcam" error

**Solutions:**
1. Try different CAMERA_INDEX (0, 1, 2)
2. Close other apps using camera
3. Check camera permissions in Windows Settings

### High CPU Usage
**Solutions:**
1. Reduce CAMERA_FPS in config.py
2. Increase YOLO_INTERVAL (run less frequently)
3. Lower CAMERA_WIDTH/HEIGHT resolution

### Phone Detection Not Working
**Solutions:**
1. Lower PHONE_CONF_THRESH (more sensitive)
2. Ensure YOLOv5 model is downloaded
3. Check lighting conditions

## Project Structure

```
AlertEye/
├── SafeDriveVision/          # Python Backend
│   ├── app.py                # FastAPI application
│   ├── detector.py           # Main detection logic
│   ├── config.py             # Configuration
│   ├── smoothing_filters.py  # Signal processing
│   ├── performance_monitor.py # Performance tracking
│   ├── weights/              # Model weights (gitignored)
│   └── requirements.txt      # Python dependencies
│
├── flutter_app/              # Flutter Frontend
│   ├── lib/
│   │   ├── main.dart         # App entry point
│   │   ├── config/           # App configuration
│   │   ├── models/           # Data models
│   │   ├── screens/          # UI screens
│   │   ├── services/         # Backend service
│   │   └── widgets/          # Reusable widgets
│   ├── pubspec.yaml          # Flutter dependencies
│   └── run_mobile.bat        # Mobile simulator launcher
│
├── myenv_311/                # Python virtual environment (gitignored)
├── .gitignore                # Git ignore rules
├── README.md                 # This file
└── FIXES_SUMMARY.md          # Technical improvements log
```

## Performance Optimizations

- **Multi-threading**: Separate threads for capture and detection
- **Frame Skipping**: YOLO runs every 3 frames, face detection every frame
- **Connection Pooling**: HTTP client reuses connections
- **Smoothing Filters**: EMA, median, and hysteresis filters
- **Adaptive Thresholds**: Dynamic threshold adjustment
- **JPEG Compression**: Optimized quality (75) for streaming

## Technical Details

### Detection Methods

**Drowsiness (EAR)**
- Eye Aspect Ratio < 0.27 for 6 consecutive frames
- Uses dlib 81-point facial landmarks
- Exponential moving average smoothing

**Yawning (MAR)**
- Mouth Aspect Ratio > 0.52 for 4 consecutive frames
- Hysteresis filter prevents flickering

**Phone Detection**
- YOLOv5n model (COCO class 67: cell phone)
- Confidence threshold: 0.25
- Runs every 3 frames for performance

**Distraction**
- Head pose estimation from facial landmarks
- Gaze direction tracking
- 8 consecutive frames for confirmation

### Flutter UI Features

- **Mobile Frame Simulator**: iPhone 14 Pro dimensions (393x852)
- **Real-time Updates**: 200ms polling interval
- **Material Design 3**: Dark theme with color-coded alerts
- **Responsive Layout**: All 6 alert boxes fit without scrolling
- **Smooth Animations**: Pulse effects on active alerts
- **Connection Monitoring**: Visual status indicator

## Development

### Adding New Detection Features

1. Add detection logic in `SafeDriveVision/detector.py`
2. Update alert dictionary in `get_alerts()`
3. Add corresponding UI in `flutter_app/lib/screens/home_screen.dart`
4. Update `AlertData` model if needed

### Modifying UI

Flutter widgets are in `flutter_app/lib/widgets/`:
- `alert_card.dart` - Individual alert boxes
- `mjpeg_view.dart` - Video stream display
- `status_badge.dart` - Connection status indicator

## Known Issues

1. **Backend Startup Delay**: YOLO model loading takes 10-20 seconds
2. **Camera Compatibility**: Some USB cameras may require different indices
3. **Windows Only**: Currently tested only on Windows platform
4. **Single User**: Designed for single driver monitoring

## Future Improvements

- [ ] Multi-platform support (Linux, macOS)
- [ ] Mobile app (Android/iOS)
- [ ] Cloud deployment
- [ ] Historical data logging
- [ ] Configurable alert sounds
- [ ] Multiple camera support
- [ ] Dashboard analytics

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

## Support

For issues and bug reports, see `FIXES_SUMMARY.md` for common problems and solutions.

## Acknowledgments

- YOLOv5 by Ultralytics
- dlib by Davis King
- Flutter framework
- FastAPI framework
