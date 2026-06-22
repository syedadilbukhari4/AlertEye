# 🚗 AlertEye - Real-Time Driver Monitoring System

**Version 2.0 (Final)** | Python + FastAPI + YOLOv5 + dlib + Flutter

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green.svg)](https://fastapi.tiangolo.com/)
[![Flutter](https://img.shields.io/badge/Flutter-3.0%2B-blue.svg)](https://flutter.dev/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> Real-time driver safety system using computer vision and deep learning. Detects drowsiness, yawning, phone usage, and dangerous head tilts via webcam with **<400ms latency**.

---

## 📋 Table of Contents
- [✨ Features](#-features)
- [🏗️ Architecture](#️-architecture)
- [📁 File Structure](#-file-structure)
- [⚙️ Setup](#️-setup)
- [🚀 Running](#-running)
- [📡 API Endpoints](#-api-endpoints)
- [⚙️ Configuration](#️-configuration)
- [🔬 Detection Details](#-detection-details)
- [📱 Flutter UI Layout](#-flutter-ui-layout)
- [⚡ Performance Tuning](#-performance-tuning)
- [🔧 Troubleshooting](#-troubleshooting)
- [🧹 Cleanup History](#-cleanup-history)

---

## ✨ Features

| Detection | Method | Threshold | Latency |
|-----------|--------|-----------|---------|
| **Drowsiness** | Eye Aspect Ratio (EAR) via dlib 81-point landmarks | EAR < 0.24 for 3 frames | ~100ms |
| **Yawning** | Mouth Aspect Ratio (MAR) | MAR > 0.52 for 2 frames | ~66ms |
| **Phone Use** | YOLOv5s object detection (COCO class 67) | Confidence > 32%, every 30 frames | Instant |
| **Head Tilt** | 3D pose estimation via cv2.solvePnP | Roll > 30° for 5 frames, or face lost 5 frames | ~160ms |

All alerts are streamed to a Flutter UI with live MJPEG video feed and audio alerts.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────┐          ┌─────────────────────────────────────┐
│        Flutter App (Frontend)       │          │       Python Backend (FastAPI)      │
│                                     │          │                                     │
│   poll /alerts (200ms)  ────────────┼─────────▶│       DriverMonitor (threaded)      │
│                                     │          │                                     │
│   MJPEG stream          ────────────┼─────────▶│   camera -> Queue -> detect -> encode│
│                                     │          │                                     │
│   audio alerts          ◀───────────┼──────────│     alert states (thread-safe lock)  │
└─────────────────────────────────────┘          └─────────────────────────────────────┘
```

### Backend Threading Model
1. **Capture thread** — reads camera frames into `Queue(maxsize=1)`
2. **Detection thread** — processes frames: YOLO (every 30 frames), dlib face (every 6 frames), compute EAR/MAR/head pose
3. **Alert state** — protected by `threading.Lock()`, read by FastAPI endpoints

---

## 📁 File Structure

```
AlertEye/
├── backend/                                    # Python backend
│   ├── app.py                                  # FastAPI server (3 endpoints)
│   ├── detector.py                             # DriverMonitor class (core detection)
│   ├── config.py                               # All tunable thresholds & settings
│   ├── smoothing_filters.py                    # EMA, Median, Hysteresis, AdaptiveThreshold
│   ├── alert_logger.py                         # File-based alert logging
│   ├── requirements.txt                        # Python dependencies
│   └── shape_predictor_81_face_landmarks.dat   # dlib 81-point model
│
├── flutter_app/                                # Flutter frontend
│   ├── lib/
│   │   ├── main.dart                           # App entry point
│   │   ├── screens/
│   │   │   └── home_screen.dart                # Main UI
│   │   ├── services/
│   │   │   ├── backend_service.dart            # REST polling (200ms)
│   │   │   └── audio_service.dart              # Audio player with rate limiting
│   │   ├── models/
│   │   │   └── alert_model.dart                # AlertData model
│   │   ├── widgets/
│   │   │   ├── status_badge.dart               # Connected/Disconnected pill
│   │   │   └── simple_mjpeg_view.dart          # MJPEG parser
│   │   └── utils/
│   │       └── flutter_logger.dart             # File-based logging
│   ├── assets/sounds/                          # Audio alert files
│   └── pubspec.yaml                            # Flutter dependencies
│
├── 1_START_BACKEND.bat                         # Launches backend
├── 2_START_FLUTTER.bat                         # Launches Flutter
├── stop_running_proc.bat                       # Kills all processes
└── .gitignore
```

---

## ⚙️ Setup

### 1. Python Backend
```bash
cd backend
pip install -r requirements.txt
```

**dlib on Windows** — No official wheel for Python 3.14. Use pre-compiled:
```bash
# For Python 3.14
pip install https://github.com/z-mahmud22/Dlib_Windows_Python3.x/raw/main/dlib-20.0.99-cp314-cp314-win_amd64.whl

# For Python 3.11
pip install https://github.com/z-mahmud22/Dlib_Windows_Python3.x/raw/main/dlib-19.24.1-cp311-cp311-win_amd64.whl
```

### 2. Flutter Frontend
```bash
cd flutter_app
flutter pub get
```

---

## 🚀 Running

### Terminal 1 — Backend
```bash
1_START_BACKEND.bat
# Or manually: cd backend && python app.py
```
Starts on `http://localhost:8000`

### Terminal 2 — Flutter
```bash
2_START_FLUTTER.bat
# Or manually: cd flutter_app && flutter run -d windows
```

### Stop Everything
```bash
stop_running_proc.bat
```

---

## 📡 API Endpoints

| Endpoint | Method | Response | Frequency |
|----------|--------|----------|-----------|
| `/alerts` | GET | `{"eye_closed": bool, "yawning": bool, "phone_detected": bool, "head_tilt_alert": bool, "timestamp": int}` | Every 200ms |
| `/health` | GET | `{"status": "ok", "version": "2.0", ...}` | Every 10s |
| `/mjpeg` | GET | MJPEG stream with debug overlays | Continuous |

---

## ⚙️ Configuration

All settings live in `backend/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `CAMERA_WIDTH` | 480 | Camera resolution width |
| `CAMERA_HEIGHT` | 360 | Camera resolution height |
| `EAR_THRESH` | 0.24 | Eye Aspect Ratio threshold (lower = more sensitive) |
| `EAR_CONSEC_FRAMES` | 3 | Frames before drowsy alert |
| `MAR_THRESH` | 0.52 | Mouth Aspect Ratio threshold |
| `YAWN_CONSEC_FRAMES` | 2 | Frames before yawn alert |
| `HEAD_TILT_THRESHOLD` | 30 | Roll angle in degrees |
| `HEAD_TILT_CONSEC_FRAMES` | 5 | Frames before tilt alert |
| `PHONE_CONF_THRESH` | 0.32 | YOLO confidence for phone |
| `YOLO_INTERVAL` | 30 | Run YOLO every N frames |
| `FACE_INTERVAL` | 6 | Run dlib every N frames |
| `JPEG_QUALITY` | 55 | MJPEG stream quality (0–100) |

### Smoothing Filters (`smoothing_filters.py`)
- `ExponentialMovingAverage` — smooths raw EAR/MAR values
- `MedianFilter` — removes outliers
- `HysteresisFilter` — dual-threshold prevents flickering
- `ConfidenceTracker` — sliding window for phone detection
- `AdaptiveThreshold` — adjusts EAR/MAR threshold based on recent values

---

## 🔬 Detection Details

### Drowsiness (EAR)
81-point dlib landmarks → eye landmarks (36–41 left, 42–47 right) → `(||p2-p6|| + ||p3-p5||) / (2*||p1-p4||)`

**Pipeline:** `raw EAR → EMA → Median → Hysteresis → bool`

### Yawning (MAR)
Mouth landmarks (48–68) → `(||p2-p10|| + ||p4-p8||) / (2*||p1-p6||)`

### Phone Detection (YOLOv5s)
COCO class 67 (cell phone) with confidence > 0.32. Runs every 30 frames (~1s). Triggers instantly on detection, clears instantly on removal.

### Head Tilt (3D Pose)
6 facial landmarks → `cv2.solvePnP` → rotation matrix → Euler angles (roll). Dual strategy:
- Roll > 30° for 5 frames → alert
- No face detected for 5 frames → alert (extreme tilt)

---

## 📱 Flutter UI Layout

```
┌─────────────────────────────────────────────────┐
│  🚗 AlertEye                        [🟢 status] │
├─────────────────────────────────────────────────┤
│                                                 │
│              Live Video Feed                    │
│              (MJPEG Stream)                     │
│                                                 │
├─────────────────────────────────────────────────┤
│           ⚠️ Status Indicator                   │
│           (Safe / ALERT!)                       │
├──────────┬──────────┬──────────┬────────────────┤
│ 😴 Drowsy│ 😮 Yawn  │ 📱 Phone │ 🤯 Tilt        │
├──────────┴──────────┴──────────┴────────────────┤
│   📊 Stats: Eye / Yawn / Phone / Tilt           │
└─────────────────────────────────────────────────┘
```

**Color Legend:**
- 🔴 **Red** — Drowsy, Phone (critical)
- 🟠 **Orange** — Yawn, Head Tilt (warning)
- 🟢 **Green** — Safe

**Features:**
- Pulsing status bar when alert is active
- Audio alerts with 8s cooldown per sound

---

## ⚡ Performance Tuning

### Higher FPS (lower quality)
```python
CAMERA_WIDTH = 320
CAMERA_HEIGHT = 240
YOLO_INTERVAL = 60
JPEG_QUALITY = 40
```

### Better Accuracy (lower FPS)
```python
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
YOLO_INTERVAL = 20
JPEG_QUALITY = 75
```

---

## 🔧 Troubleshooting

### Backend

| Problem | Fix |
|---------|-----|
| Camera not opening | Close Zoom/Meet/Teams; check camera index |
| Low FPS | Increase `YOLO_INTERVAL`, lower resolution |
| YOLO loading error | `pip install ultralytics pandas seaborn` |
| dlib import error | Install pre-compiled wheel (see Setup) |

### Flutter

| Problem | Fix |
|---------|-----|
| Connection failed | Ensure backend is running on `localhost:8000` |
| No alerts showing | Check backend terminal for debug output |
| App crashes on launch | Check FlutterLogger output file |

### Detection

| Problem | Fix |
|---------|-----|
| False drowsiness alerts | Lower `EAR_THRESH` (try 0.20), increase `EAR_CONSEC_FRAMES` |
| Missed phone detection | Lower `PHONE_CONF_THRESH` (try 0.25), reduce `YOLO_INTERVAL` |
| Head tilt too sensitive | Increase `HEAD_TILT_THRESHOLD` (try 35–40°), increase consec frames |

---

## 🧹 Cleanup History

Legacy SafeDriveVision code removed in June 2026 cleanup:

- ✅ SafeDriveVision.py / v0 (old monolithic versions)
- ✅ Entire TDDFA 3D face alignment pipeline (FaceBoxes, bfm, Sim3DR, models, utils, configs, Caffe)
- ✅ Unused weight files (models loaded fresh via torch.hub)
- ✅ Unused audio files (Flutter handles all audio)
- ✅ Dead Flutter code (alert_card.dart, app_config.dart, unused sounds)

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.

---

## 📧 Contact

Syed Adil Bukhari — syedadilbukhari4444@gmail.com

Project Link: [https://github.com/syedadilbukhari4/AlertEye](https://github.com/syedadilbukhari4/AlertEye)

---

## 🙏 Acknowledgments

- [YOLOv5](https://github.com/ultralytics/yolov5) — Object detection
- [dlib](http://dlib.net/) — Facial landmark detection
- [FastAPI](https://fastapi.tiangolo.com/) — Backend framework
- [Flutter](https://flutter.dev/) — Frontend framework
