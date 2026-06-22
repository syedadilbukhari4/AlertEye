import time
import threading
from typing import Dict, Generator, Optional
from queue import Queue
import math

import cv2
try:
    import dlib 
except Exception:
    dlib = None

import numpy as np
import torch
from scipy.spatial import distance as dist


try:
    from smoothing_filters import ExponentialMovingAverage, MedianFilter, HysteresisFilter, ConfidenceTracker, AdaptiveThreshold
    SMOOTHING_AVAILABLE = False  
except ImportError:
    print("Warning: Smoothing filters not available, using basic detection")
    SMOOTHING_AVAILABLE = False

try:
    import config
    CONFIG_AVAILABLE = True
except ImportError:
    print("Warning: Config file not available, using default settings")
    CONFIG_AVAILABLE = False

try:
    from alert_logger import AlertLogger
    LOGGER_AVAILABLE = True
except ImportError:
    print("Warning: Alert logger not available")
    LOGGER_AVAILABLE = False

import warnings

warnings.filterwarnings(
    "ignore",
    message=r".*torch\.cuda\.amp\.autocast.*deprecated.*",
    category=FutureWarning,
)

class DriverMonitor:
    """Ultra-optimized version with multi-threading"""

    def __init__(
        self,
        camera_index: int = 0,
        yolo_weights_path: str = None,
        dlib_shape_predictor_path: str = r"./shape_predictor_81_face_landmarks (1).dat",
        phone_class_id: int = 67,
        phone_conf_thresh: float = 0.35,
    ):
        self.camera_index = camera_index
        self.yolo_weights_path = yolo_weights_path
        self.dlib_shape_predictor_path = dlib_shape_predictor_path
        self.phone_class_id = phone_class_id
        self.phone_conf_thresh = phone_conf_thresh

        self._cap: Optional[cv2.VideoCapture] = None
        self._capture_thread: Optional[threading.Thread] = None
        self._detection_thread: Optional[threading.Thread] = None
        self._running = False

        self._frame_queue = Queue(maxsize=1)
        
        self._lock = threading.Lock()
        self._latest_jpeg: Optional[bytes] = None
        self._latest_display_frame: Optional[np.ndarray] = None
        
        self._alerts: Dict[str, object] = {
            "eye_closed": False,
            "yawning": False,
            "phone_detected": False,
            "not_looking_forward": False,
            "head_tilt_alert": False,
            "timestamp": int(time.time()),
        }

        # Counters
        self._eye_counter = 0
        self._yawn_counter = 0
        self._phone_counter = 0
        self._not_forward_counter = 0
        self._head_tilt_counter = 0
        self._repeat_counter = 0
        
        # Track last valid head tilt to handle brief face detection failures
        self._last_head_tilt_angle = 0.0
        self._frames_since_face_detected = 0

        if CONFIG_AVAILABLE:
            self._EAR_THRESH = config.EAR_THRESH
            self._EAR_CONSEC_FRAMES = config.EAR_CONSEC_FRAMES
            self._MAR_THRESH = config.MAR_THRESH
            self._YAWN_CONSEC_FRAMES = config.YAWN_CONSEC_FRAMES
            self._PHONE_CONSEC_FRAMES = config.PHONE_CONSEC_FRAMES
            self._NOT_FORWARD_CONSEC_FRAMES = config.NOT_FORWARD_CONSEC_FRAMES
            self._HEAD_TILT_CONSEC_FRAMES = config.HEAD_TILT_CONSEC_FRAMES
            self._HEAD_TILT_THRESHOLD = config.HEAD_TILT_THRESHOLD
            
            self._yolo_interval = config.YOLO_INTERVAL
            self._face_interval = config.FACE_INTERVAL
            self._processing_scale = config.PROCESSING_SCALE
            self._target_output_fps = config.TARGET_OUTPUT_FPS
            self._jpeg_quality = config.JPEG_QUALITY
        else:
           
            self._EAR_THRESH = 0.27
            self._EAR_CONSEC_FRAMES = 6
            self._MAR_THRESH = 0.52
            self._YAWN_CONSEC_FRAMES = 4
            self._PHONE_CONSEC_FRAMES = 2
            self._NOT_FORWARD_CONSEC_FRAMES = 8
            self._HEAD_TILT_CONSEC_FRAMES = 3
            self._HEAD_TILT_THRESHOLD = 13
            
            self._yolo_interval = 6
            self._face_interval = 1
            self._processing_scale = 0.7
            self._target_output_fps = 25.0
            self._jpeg_quality = 75

       
        self.model_points = np.array([
            (0.0, 0.0, 0.0),
            (-30.0, -125.0, -30.0),
            (30.0, -125.0, -30.0),
            (-60.0, -70.0, -60.0),
            (60.0, -70.0, -60.0),
            (0.0, -330.0, -65.0)
        ])

        # Load models
        self.detector = None
        self.predictor = None
        if dlib is not None:
            try:
                self.detector = dlib.get_frontal_face_detector()
                self.predictor = dlib.shape_predictor(self.dlib_shape_predictor_path)
            except:
                print("Warning: dlib models not found")

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        try:
            print("Loading YOLOv5s model for better phone detection...")
            self.model = torch.hub.load("ultralytics/yolov5", "yolov5s", pretrained=True, force_reload=False)
            self.model.to(self.device)
            self.model.eval()
            print("YOLOv5s model loaded successfully")
        except Exception as e:
            print(f"Error loading YOLOv5s model: {e}")
            raise RuntimeError("Failed to load YOLO model") from e
        
        # Warm up model
        dummy = torch.zeros((1, 3, 640, 640)).to(self.device)
        with torch.no_grad():
            _ = self.model(dummy)
        
        # Initialize alert logger
        if LOGGER_AVAILABLE:
            self.alert_logger = AlertLogger("alert_log.txt")
            self.alert_logger.log_info("✅ DriverMonitor initialized with alert logging")
        else:
            self.alert_logger = None

        self._cached_detections = {
            'yolo_result': None,
            'faces': [],
            'landmarks': None,
            'timestamp': 0
        }
        
        self._frame_counter = 0
        self._last_output_ts = 0.0
        self._frames_processed = 0
        self._frames_skipped = 0
           
        if SMOOTHING_AVAILABLE:
         
            ear_alpha = config.EAR_SMOOTHING_ALPHA if CONFIG_AVAILABLE else 0.4
            mar_alpha = config.MAR_SMOOTHING_ALPHA if CONFIG_AVAILABLE else 0.3
            median_size = config.MEDIAN_FILTER_SIZE if CONFIG_AVAILABLE else 5
            
            self._ear_filter = ExponentialMovingAverage(alpha=ear_alpha)
            self._mar_filter = ExponentialMovingAverage(alpha=mar_alpha)
            self._ear_median = MedianFilter(window_size=median_size)
            self._mar_median = MedianFilter(window_size=median_size)
            
         
            if CONFIG_AVAILABLE:
                self._eye_hysteresis = HysteresisFilter(
                    low_thresh=config.EAR_HYSTERESIS_LOW, 
                    high_thresh=config.EAR_HYSTERESIS_HIGH,
                    inverted=True 
                )
                self._yawn_hysteresis = HysteresisFilter(
                    low_thresh=config.MAR_HYSTERESIS_LOW, 
                    high_thresh=config.MAR_HYSTERESIS_HIGH,
                    inverted=False  # MAR: high values = yawning
                )
            else:
                self._eye_hysteresis = HysteresisFilter(low_thresh=0.24, high_thresh=0.30, inverted=True)
                self._yawn_hysteresis = HysteresisFilter(low_thresh=0.47, high_thresh=0.57, inverted=False)
            
          
            if CONFIG_AVAILABLE:
                self._phone_confidence = ConfidenceTracker(
                    window_size=config.PHONE_CONFIDENCE_WINDOW, 
                    confidence_thresh=config.PHONE_CONFIDENCE_THRESH
                )
                self._forward_confidence = ConfidenceTracker(
                    window_size=config.FORWARD_CONFIDENCE_WINDOW, 
                    confidence_thresh=config.FORWARD_CONFIDENCE_THRESH
                )
            else:
                self._phone_confidence = ConfidenceTracker(window_size=8, confidence_thresh=0.6)
                self._forward_confidence = ConfidenceTracker(window_size=12, confidence_thresh=0.7)
            
           
            if CONFIG_AVAILABLE:
                self._adaptive_ear = AdaptiveThreshold(
                    initial_thresh=config.EAR_THRESH, 
                    adaptation_rate=config.ADAPTIVE_EAR_RATE
                )
                self._adaptive_mar = AdaptiveThreshold(
                    initial_thresh=config.MAR_THRESH, 
                    adaptation_rate=config.ADAPTIVE_MAR_RATE
                )
            else:
                self._adaptive_ear = AdaptiveThreshold(initial_thresh=0.27, adaptation_rate=0.005)
                self._adaptive_mar = AdaptiveThreshold(initial_thresh=0.52, adaptation_rate=0.005)

    def start(self) -> None:
        if self._running:
            return
        
        print("=" * 60)
        print("🎥 CAMERA INITIALIZATION DIAGNOSTICS")
        print("=" * 60)
        
        # Try to open camera with detailed error reporting
        print(f"📹 Attempting to open camera index: {self.camera_index}")
        self._cap = cv2.VideoCapture(self.camera_index)
        
        if not self._cap.isOpened():
            print("❌ CAMERA ACCESS FAILED!")
            print("\n🔍 DIAGNOSTIC INFORMATION:")
            print("-" * 60)
            
            # Check if camera exists
            print("1. Checking camera availability...")
            test_cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not test_cap.isOpened():
                print("   ❌ Camera device not found or in use by another application")
                print("   💡 Possible reasons:")
                print("      - Google Meet/Zoom/Skype is using the camera")
                print("      - Camera driver issue")
                print("      - Camera disconnected")
                print("      - Insufficient permissions")
            else:
                print("   ✅ Camera device exists but access denied")
                print("   💡 Most likely: Another application has exclusive lock")
                test_cap.release()
            
            # Check running processes that might use camera
            print("\n2. Checking for applications using camera...")
            try:
                import psutil
                camera_apps = ['chrome.exe', 'msedge.exe', 'firefox.exe', 'zoom.exe', 
                              'skype.exe', 'teams.exe', 'obs64.exe', 'obs32.exe']
                running_camera_apps = []
                for proc in psutil.process_iter(['name']):
                    if proc.info['name'].lower() in [app.lower() for app in camera_apps]:
                        running_camera_apps.append(proc.info['name'])
                
                if running_camera_apps:
                    print(f"   ⚠️  Found applications that may be using camera:")
                    for app in set(running_camera_apps):
                        print(f"      - {app}")
                else:
                    print("   ℹ️  No common camera applications detected")
            except ImportError:
                print("   ℹ️  Install 'psutil' for process detection: pip install psutil")
            except Exception as e:
                print(f"   ⚠️  Could not check processes: {e}")
            
            # Check camera properties
            print("\n3. Camera backend information...")
            print(f"   OpenCV version: {cv2.__version__}")
            print(f"   Video backend: {self._cap.getBackendName()}")
            
            # Try alternative backends
            print("\n4. Trying alternative camera backends...")
            backends = [
                (cv2.CAP_DSHOW, "DirectShow (Windows)"),
                (cv2.CAP_MSMF, "Media Foundation (Windows)"),
                (cv2.CAP_ANY, "Auto-detect")
            ]
            
            for backend, name in backends:
                test = cv2.VideoCapture(self.camera_index, backend)
                status = "✅ Available" if test.isOpened() else "❌ Failed"
                print(f"   {name}: {status}")
                test.release()
            
            print("\n" + "=" * 60)
            print("❌ CAMERA INITIALIZATION FAILED")
            print("=" * 60)
            print("\n📋 RECOMMENDED ACTIONS:")
            print("1. Close Google Meet/Zoom/Skype/Teams")
            print("2. Close browser tabs using camera")
            print("3. Restart the application")
            print("4. Check Windows Camera Privacy Settings")
            print("5. Try a different camera index (0, 1, 2)")
            print("\n" + "=" * 60)
            
            raise RuntimeError(
                "Cannot open webcam - Camera is likely being used by another application "
                "(Google Meet, Zoom, Skype, etc.). Please close other applications and try again."
            )
        
        # Camera opened successfully
        print("✅ Camera opened successfully!")
        print(f"   Backend: {self._cap.getBackendName()}")
        
        # Get camera properties
        actual_width = self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_height = self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        actual_fps = self._cap.get(cv2.CAP_PROP_FPS)
        
        print(f"   Current resolution: {int(actual_width)}x{int(actual_height)}")
        print(f"   Current FPS: {int(actual_fps)}")
   
        camera_width = config.CAMERA_WIDTH if CONFIG_AVAILABLE else 1280
        camera_height = config.CAMERA_HEIGHT if CONFIG_AVAILABLE else 720
        camera_fps = config.CAMERA_FPS if CONFIG_AVAILABLE else 30
        
        print(f"\n📐 Configuring camera settings...")
        print(f"   Target resolution: {camera_width}x{camera_height}")
        print(f"   Target FPS: {camera_fps}")
        
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap.set(cv2.CAP_PROP_FPS, camera_fps)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)
        self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        
        # Verify settings applied
        final_width = self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        final_height = self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        final_fps = self._cap.get(cv2.CAP_PROP_FPS)
        
        print(f"   Applied resolution: {int(final_width)}x{int(final_height)}")
        print(f"   Applied FPS: {int(final_fps)}")
        
        if final_width != camera_width or final_height != camera_height:
            print(f"   ⚠️  Resolution mismatch - camera may not support requested resolution")
        
        print("=" * 60)
        print("✅ CAMERA INITIALIZATION COMPLETE")
        print("=" * 60)
        
        self._running = True
        
       
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        
        self._capture_thread.start()
        self._detection_thread.start()
        
        print("🚀 Detection threads started successfully\n")

    def stop(self) -> None:
        if not self._running:
            return
        
        self._running = False
        
        if self._capture_thread is not None:
            self._capture_thread.join(timeout=2.0)
        if self._detection_thread is not None:
            self._detection_thread.join(timeout=2.0)
        if self._cap is not None:
            self._cap.release()

    def get_alerts(self) -> Dict[str, object]:
      
        return dict(self._alerts)

    def get_latest_frame(self) -> Optional[bytes]:
        with self._lock:
            return self._latest_jpeg

    def mjpeg_generator(self) -> Generator[bytes, None, None]:
        """MJPEG generator (low-latency, Content-Length, no forced sleep)."""
        import logging
        logger = logging.getLogger(__name__)

        wait_count = 0
        while self._latest_jpeg is None and wait_count < 100:
            time.sleep(0.01)  
            wait_count += 1

        last_sent: Optional[bytes] = None

        while self._running:
            try:
                with self._lock:
                    jpeg = self._latest_jpeg

                if not jpeg:
                    time.sleep(0.001)  
                    continue

      
                if jpeg is last_sent:
                    time.sleep(0.001)  
                    continue
                last_sent = jpeg

                headers = (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii")
                )
                yield headers + jpeg + b"\r\n"

            except GeneratorExit:
                logger.info("MJPEG client disconnected gracefully")
                return
            except Exception as e:
                logger.error(f"Error in MJPEG generator: {e}")
                time.sleep(0.01)  

        logger.info("MJPEG generator stopped (monitor not running)")

    def _capture_loop(self) -> None:
        while self._running:
            ok, frame = self._cap.read()
            if not ok:
                time.sleep(0.001)
                continue
            
            if self._frame_queue.full():
                try:
                    _ = self._frame_queue.get_nowait()
                except Exception:
                    pass
            try:
                self._frame_queue.put_nowait(frame)
            except Exception:
                pass
    def _detection_loop(self) -> None:
        """Dedicated thread for detection - OPTIMIZED FOR SPEED"""
        import logging
        logger = logging.getLogger(__name__)
        frame_count = 0
        last_log_time = time.time()
        last_alert_log_time = time.time()
        
        while self._running:
            if self._frame_queue.empty():
                time.sleep(0.001)
                continue
            
            frame = self._frame_queue.get()
            self._frame_counter += 1
            frame_count += 1
            
            now = time.time()
            target_fps = 30.0 
            min_dt = 1.0 / target_fps
            
            if (now - self._last_output_ts) < min_dt:
                self._frames_skipped += 1
                continue
                
            self._last_output_ts = now
            self._frames_processed += 1
            
          
            scale = 0.9  
            small = cv2.resize(frame, None, fx=scale, fy=scale, 
                             interpolation=cv2.INTER_NEAREST) 
           
            annotated = self._process_frame_fast(small, frame.shape)
            
            
            encode_success, buf = cv2.imencode(".jpg", annotated, [
                int(cv2.IMWRITE_JPEG_QUALITY), 55, 
                int(cv2.IMWRITE_JPEG_OPTIMIZE), 0,
                int(cv2.IMWRITE_JPEG_PROGRESSIVE), 0,  
            ])
            
            if encode_success:
                with self._lock:
                    self._latest_jpeg = buf.tobytes()
                    
                if now - last_log_time > 5.0:
                    fps = frame_count / 5.0
                    logger.info(f"Processing FPS: {fps:.1f}")
                    frame_count = 0
                    last_log_time = now
                
                # Log alert status every 10 seconds
                if now - last_alert_log_time > 10.0:
                    alerts = self.get_alerts()
                    active = [k.upper() for k, v in alerts.items() if isinstance(v, bool) and v]
                    if active:
                        print(f"📊 ACTIVE ALERTS: {', '.join(active)}")
                    else:
                        print(f"✅ NO ACTIVE ALERTS")
                    last_alert_log_time = now

  
    def _process_frame_fast(self, small_frame: np.ndarray, original_shape: tuple) -> np.ndarray:
        """Optimized processing with ALL features enabled"""
        img = small_frame.copy()

        run_yolo = (self._frame_counter % self._yolo_interval == 0)
        run_face = (self._frame_counter % self._face_interval == 0)
        
      
        gray = None


        phone_detected = False
        
        if run_yolo:
            
            yolo_input = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            
            with torch.no_grad():
                results = self.model(yolo_input, size=320)  
            
        
            self._cached_detections['yolo_result'] = results
            self._cached_detections['timestamp'] = time.time()
        else:
           
            results = self._cached_detections['yolo_result']
        
        if results is not None:

            detections = results.pandas().xyxy[0]
            
            phone_detections = detections[
                (detections['class'] == 67) & 
                (detections['confidence'] >= 0.32)  # Balanced threshold
            ]
            
         
            for _, detection in phone_detections.iterrows():
                x1, y1, x2, y2 = int(detection['xmin']), int(detection['ymin']), int(detection['xmax']), int(detection['ymax'])
                conf = detection['confidence']
                
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 255), 1)
                cv2.putText(img, f"Phone {conf:.2f}", (x1, y1 - 3), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 255), 1)
                
                phone_detected = True
                
                # Log phone detection
                if self._frame_counter % 30 == 0:
                    print(f"📱 PHONE DETECTED: Confidence={conf:.2f}, Box=({x1},{y1})-({x2},{y2})")
            
            cv2.putText(img, f"YOLO: {'RUN' if run_yolo else 'CACHED'}", (5, 140), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 0), 1)
            cv2.putText(img, f"Phones: {len(phone_detections)}", (5, 150), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 0), 1)
        
        if SMOOTHING_AVAILABLE:
            phone_alert = self._phone_confidence.update(phone_detected)
        else:
            # Instant clear when phone removed
            if phone_detected:
                self._phone_counter = self._PHONE_CONSEC_FRAMES  # Instant trigger
            else:
                self._phone_counter = 0  # Instant clear
            phone_alert = self._phone_counter >= self._PHONE_CONSEC_FRAMES
            
        self._set_alert("phone_detected", phone_alert)
        
        if self._alerts["phone_detected"]:
            cv2.putText(img, "PUT DOWN PHONE!", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        

        if self.detector is None or self.predictor is None:
            self._set_alert("eye_closed", False)
            self._set_alert("yawning", False)
            self._set_alert("not_looking_forward", False)
            self._set_alert("head_tilt_alert", False)
            return img
        

        if run_face:
            gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
            # Increase dlib detection sensitivity: 0 = default, 1 = more sensitive (slower)
            faces = self.detector(gray, 1)  # Changed from 0 to 1 for better detection
            self._cached_detections['faces'] = faces
        else:
            faces = self._cached_detections['faces']
        
        # Display frame info on screen
        cv2.putText(img, f"Faces: {len(faces)}", (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0) if len(faces) > 0 else (0, 0, 255), 1)
        cv2.putText(img, f"Frame: {self._frame_counter}", (5, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)
        
        # TEMPORARILY DISABLED - Look Forward detection
        # not_forward = len(faces) == 0
        # if SMOOTHING_AVAILABLE:
        #     forward_alert = not self._forward_confidence.update(not not_forward)
        # else:
        #     self._not_forward_counter = self._not_forward_counter + 1 if not_forward else 0
        #     forward_alert = self._not_forward_counter >= self._NOT_FORWARD_CONSEC_FRAMES
        #     
        # self._set_alert("not_looking_forward", forward_alert)
        # 
        # if self._alerts["not_looking_forward"]:
        #     cv2.putText(img, "LOOK FORWARD!", (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        # Force not_looking_forward to False (disabled)
        self._set_alert("not_looking_forward", False)
        
      
        eye_closed = False
        yawning = False
        head_tilt_alert = False
        
        if gray is None:
            gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)


        if len(faces) > 0:
            self._frames_since_face_detected = 0  # Reset counter
            face = faces[0]
            shape = self.predictor(gray, face)
            pts = np.array([(p.x, p.y) for p in shape.parts()], dtype=np.int32)
            
            (x, y, w, h) = (face.left(), face.top(), face.width(), face.height())
            cv2.rectangle(img, (x, y), (x + w, y + h), (255, 0, 0), 2)
            
            
            for point in pts:
                cv2.circle(img, (point[0], point[1]), 1, (0, 255, 255), -1)
            
            left_eye = pts[36:42]
            right_eye = pts[42:48]
            left_ear = self._eye_aspect_ratio(left_eye)
            right_ear = self._eye_aspect_ratio(right_eye)
            raw_ear = (left_ear + right_ear) / 2.0
            
            # Initialize eye_closed
            eye_closed = False
            
            if SMOOTHING_AVAILABLE:
          
                smooth_ear = self._ear_filter.update(raw_ear)
                filtered_ear = self._ear_median.update(smooth_ear)
                
                # Use adaptive threshold and hysteresis
                eye_closed_raw, adaptive_thresh = self._adaptive_ear.update(filtered_ear)
                eye_closed = self._eye_hysteresis.update(filtered_ear)
                
              
                ear_color = (0, 0, 255) if filtered_ear < adaptive_thresh else (0, 255, 0)
                cv2.putText(img, f'EAR: {filtered_ear:.2f}', (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.4, ear_color, 1)
                cv2.putText(img, f'Thr: {adaptive_thresh:.2f}', (10, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 0), 1)
            else:
                # Simple threshold detection
                filtered_ear = raw_ear
                

                if raw_ear < self._EAR_THRESH:
                    self._eye_counter += 1
                    cv2.putText(img, f'Eye: {self._eye_counter} CLOSING', (10, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)
                    if self._eye_counter >= self._EAR_CONSEC_FRAMES:
                        eye_closed = True
                        self._repeat_counter += 1
                else:
                    self._eye_counter = 0
                    cv2.putText(img, f'Eyes OPEN', (10, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1)
                    if not eye_closed:
                        self._repeat_counter = 0
                
                ear_color = (0, 0, 255) if raw_ear < self._EAR_THRESH else (0, 255, 0)
                cv2.putText(img, f'EAR: {filtered_ear:.2f}', (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.4, ear_color, 1)
                cv2.putText(img, f'Thr: {self._EAR_THRESH:.2f}', (10, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 0), 1)
            
   
            left_eyeHull = cv2.convexHull(left_eye)
            right_eyeHull = cv2.convexHull(right_eye)
  
            eye_contour_color = (0, 0, 255) if eye_closed else (0, 255, 0)
            cv2.drawContours(img, [left_eyeHull], -1, eye_contour_color, 2)
            cv2.drawContours(img, [right_eyeHull], -1, eye_contour_color, 2)
            
            if eye_closed:
                cv2.putText(img, "DROWSY!", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
            
            mouth = pts[48:68]
            mouthHull = cv2.convexHull(mouth)
            raw_mar = self._mouth_aspect_ratio(mouth)
            
            if SMOOTHING_AVAILABLE:
                
                smooth_mar = self._mar_filter.update(raw_mar)
                filtered_mar = self._mar_median.update(smooth_mar)
                
             
                yawning = self._yawn_hysteresis.update(filtered_mar)
            else:
               
                filtered_mar = raw_mar
                if raw_mar > self._MAR_THRESH:
                    self._yawn_counter += 1
                    if self._yawn_counter >= self._YAWN_CONSEC_FRAMES:
                        yawning = True
                else:
                    self._yawn_counter = 0
            
            mouth_color = (0, 0, 255) if yawning else (0, 255, 0)
            cv2.drawContours(img, [mouthHull], -1, mouth_color, 2)
            
            # Display MAR value
            mouth_color = (0, 0, 255) if filtered_mar > self._MAR_THRESH else (0, 255, 0)
            cv2.putText(img, f'MAR: {filtered_mar:.2f}', (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.4, mouth_color, 1)
            
            if yawning:
                cv2.putText(img, "YAWN!", (x, y - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            
           
            # Get 6 key facial landmarks for 3D head pose estimation
            image_points = np.array([
                (pts[30][0], pts[30][1]),     # Nose tip
                (pts[8][0], pts[8][1]),       # Chin
                (pts[36][0], pts[36][1]),     # Left eye left corner
                (pts[45][0], pts[45][1]),     # Right eye right corner
                (pts[48][0], pts[48][1]),     # Left mouth corner
                (pts[54][0], pts[54][1])      # Right mouth corner
            ], dtype="double")
            
            # Camera matrix
            size = img.shape
            focal_length = size[1]
            center = (size[1] / 2, size[0] / 2)
            camera_matrix = np.array(
                [[focal_length, 0, center[0]],
                 [0, focal_length, center[1]],
                 [0, 0, 1]], dtype="double"
            )
            dist_coeffs = np.zeros((4, 1))
            
            # Solve PnP to get rotation vector
            (success, rotation_vector, translation_vector) = cv2.solvePnP(
                self.model_points, image_points, camera_matrix, dist_coeffs, 
                flags=cv2.SOLVEPNP_ITERATIVE
            )
            
            # Convert rotation vector to rotation matrix
            rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
            
            # Get Euler angles (pitch, yaw, roll)
            sy = np.sqrt(rotation_matrix[0, 0] * rotation_matrix[0, 0] + rotation_matrix[1, 0] * rotation_matrix[1, 0])
            singular = sy < 1e-6
            
            if not singular:
                pitch = np.arctan2(rotation_matrix[2, 1], rotation_matrix[2, 2])
                yaw = np.arctan2(-rotation_matrix[2, 0], sy)
                roll = np.arctan2(rotation_matrix[1, 0], rotation_matrix[0, 0])
            else:
                pitch = np.arctan2(-rotation_matrix[1, 2], rotation_matrix[1, 1])
                yaw = np.arctan2(-rotation_matrix[2, 0], sy)
                roll = 0
            
            # Convert to degrees
            pitch_deg = np.degrees(pitch)
            yaw_deg = np.degrees(yaw)
            roll_deg = np.degrees(roll)
            
            self._last_head_tilt_angle = roll_deg  # Store roll for when face not detected
            
            # Display head pose angles
            angle_color = (0, 0, 255) if abs(roll_deg) > self._HEAD_TILT_THRESHOLD else (0, 255, 0)
            cv2.putText(img, f'Roll: {roll_deg:.0f}', (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.4, angle_color, 1)
            
            # Head tilt detection: Alert if roll > 30 degrees
            if abs(roll_deg) > self._HEAD_TILT_THRESHOLD:
                self._head_tilt_counter += 1
                if self._head_tilt_counter >= self._HEAD_TILT_CONSEC_FRAMES:
                    head_tilt_alert = True
            else:
                self._head_tilt_counter = 0
            
            # Log head tilt angle for debugging (every 3 seconds)
            if self._frame_counter % 90 == 0:
                print(f"HEAD POSE: Roll={roll_deg:.1f}° | Threshold={self._HEAD_TILT_THRESHOLD}° | Counter: {self._head_tilt_counter}/{self._HEAD_TILT_CONSEC_FRAMES} | Alert: {head_tilt_alert}")
                if head_tilt_alert:
                    print(f"⚠️ HEAD TILT ALERT ACTIVE! Roll: {roll_deg:.1f}°")
        else:
            # NO FACE DETECTED - This could mean head is tilted too much
            self._frames_since_face_detected += 1
            
            # Alert when face not detected for consecutive frames (likely due to extreme tilt)
            if self._frames_since_face_detected >= self._HEAD_TILT_CONSEC_FRAMES:
                head_tilt_alert = True
                if self._frame_counter % 90 == 0:
                    print(f"⚠️ HEAD TILT ALERT: No face detected for {self._frames_since_face_detected} frames (likely extreme tilt)")
            
            if self._frame_counter % 90 == 0 and not head_tilt_alert:
                print(f"❌ NO FACE DETECTED ({self._frames_since_face_detected} frames) - Waiting for {self._HEAD_TILT_CONSEC_FRAMES} frames to alert")
        

        self._set_alert("eye_closed", eye_closed)
        self._set_alert("yawning", yawning)
        self._set_alert("head_tilt_alert", head_tilt_alert)
        
        return img

  
    @staticmethod
    def _eye_aspect_ratio(eye: np.ndarray) -> float:
        A = dist.euclidean(eye[1], eye[5])
        B = dist.euclidean(eye[2], eye[4])
        C = dist.euclidean(eye[0], eye[3])
        return (A + B) / (2.0 * C + 1e-6)

    @staticmethod
    def _mouth_aspect_ratio(mouth: np.ndarray) -> float:
        A = dist.euclidean(mouth[2], mouth[10])
        B = dist.euclidean(mouth[4], mouth[8])
        C = dist.euclidean(mouth[0], mouth[6])
        return (A + B) / (2.0 * C + 1e-6)

    @staticmethod
    def _calculate_head_angle(eye_left, eye_right, nose_tip):
        eye_center = (eye_left + eye_right) / 2
        vector_nose = nose_tip - eye_center
        vector_horizontal = (eye_right - eye_left)
        vector_horizontal[1] = 0
        vector_nose_normalized = vector_nose / (np.linalg.norm(vector_nose) + 1e-6)
        vector_horizontal_normalized = vector_horizontal / (np.linalg.norm(vector_horizontal) + 1e-6)
        angle_rad = np.arccos(np.clip(np.dot(vector_nose_normalized, vector_horizontal_normalized), -1.0, 1.0))
        return np.degrees(angle_rad)
    
    @staticmethod
    def _calculate_eye_roll_angle(eye_left, eye_right):
        """
        Calculate head roll (tilt) angle based on eye alignment.
        Returns angle in degrees:
        - 0° = eyes perfectly horizontal (no tilt)
        - Positive = head tilted right
        - Negative = head tilted left
        Normal driving: -15° to +15° (allows checking mirrors)
        Alert threshold: >25° (extreme tilt)
        """
        # Calculate the angle of the line connecting the eyes
        delta_y = eye_right[1] - eye_left[1]
        delta_x = eye_right[0] - eye_left[0]
        angle_rad = np.arctan2(delta_y, delta_x)
        angle_deg = np.degrees(angle_rad)
        return angle_deg

    def _set_alert(self, key: str, value: bool) -> None:
        with self._lock:
            old_value = self._alerts.get(key, False)
            self._alerts[key] = bool(value)
            self._alerts["timestamp"] = int(time.time())
            
            # Log alert changes for debugging
            if old_value != value:
                status = "🔴 TRIGGERED" if value else "🟢 CLEARED"
                print(f"[ALERT] {key.upper()}: {status}")
                
                if self.alert_logger:
                    try:
                        self.alert_logger.log_info(f"🚨 {key.upper()}: {status}")
                    except:
                        pass