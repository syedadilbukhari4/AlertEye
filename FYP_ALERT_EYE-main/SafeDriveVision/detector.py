import time
import threading
from typing import Dict, Generator, Optional
from queue import Queue
import math

import cv2
try:
    import dlib  # type: ignore
except Exception:
    dlib = None

import numpy as np
import torch
from scipy.spatial import distance as dist

# Import smoothing filters with fallback
try:
    from smoothing_filters import ExponentialMovingAverage, MedianFilter, HysteresisFilter, ConfidenceTracker, AdaptiveThreshold
    SMOOTHING_AVAILABLE = False  # Temporarily disabled for debugging
except ImportError:
    print("Warning: Smoothing filters not available, using basic detection")
    SMOOTHING_AVAILABLE = False

try:
    import config
    CONFIG_AVAILABLE = True
except ImportError:
    print("Warning: Config file not available, using default settings")
    CONFIG_AVAILABLE = False

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

        # Frame queue for parallel processing
        # Keep ONLY the most recent frame to avoid latency buildup.
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

        # Use config if available, otherwise use defaults
        if CONFIG_AVAILABLE:
            self._EAR_THRESH = config.EAR_THRESH
            self._EAR_CONSEC_FRAMES = config.EAR_CONSEC_FRAMES
            self._MAR_THRESH = config.MAR_THRESH
            self._YAWN_CONSEC_FRAMES = config.YAWN_CONSEC_FRAMES
            self._PHONE_CONSEC_FRAMES = config.PHONE_CONSEC_FRAMES
            self._NOT_FORWARD_CONSEC_FRAMES = config.NOT_FORWARD_CONSEC_FRAMES
            self._HEAD_TILT_CONSEC_FRAMES = config.HEAD_TILT_CONSEC_FRAMES
            
            self._yolo_interval = config.YOLO_INTERVAL
            self._face_interval = config.FACE_INTERVAL
            self._processing_scale = config.PROCESSING_SCALE
            self._target_output_fps = config.TARGET_OUTPUT_FPS
            self._jpeg_quality = config.JPEG_QUALITY
        else:
            # Default values
            self._EAR_THRESH = 0.27
            self._EAR_CONSEC_FRAMES = 6
            self._MAR_THRESH = 0.52
            self._YAWN_CONSEC_FRAMES = 4
            self._PHONE_CONSEC_FRAMES = 2
            self._NOT_FORWARD_CONSEC_FRAMES = 8
            self._HEAD_TILT_CONSEC_FRAMES = 8
            
            self._yolo_interval = 6
            self._face_interval = 1
            self._processing_scale = 0.7
            self._target_output_fps = 25.0
            self._jpeg_quality = 75

        # 3D model points for head pose
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
        
        # Load YOLO model - use YOLOv5s for better phone detection
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

        # Cached results
        self._cached_detections = {
            'yolo_result': None,
            'faces': [],
            'landmarks': None,
            'timestamp': 0
        }
        
        self._frame_counter = 0
        self._last_output_ts = 0.0

        # Add frame skip counter to prevent buffer buildup
        self._frames_processed = 0
        self._frames_skipped = 0
        
        # Initialize smoothing filters if available
        if SMOOTHING_AVAILABLE:
            # SMOOTHING FILTERS FROM CONFIG OR DEFAULTS
            ear_alpha = config.EAR_SMOOTHING_ALPHA if CONFIG_AVAILABLE else 0.4
            mar_alpha = config.MAR_SMOOTHING_ALPHA if CONFIG_AVAILABLE else 0.3
            median_size = config.MEDIAN_FILTER_SIZE if CONFIG_AVAILABLE else 5
            
            self._ear_filter = ExponentialMovingAverage(alpha=ear_alpha)
            self._mar_filter = ExponentialMovingAverage(alpha=mar_alpha)
            self._ear_median = MedianFilter(window_size=median_size)
            self._mar_median = MedianFilter(window_size=median_size)
            
            # Hysteresis filters
            if CONFIG_AVAILABLE:
                self._eye_hysteresis = HysteresisFilter(
                    low_thresh=config.EAR_HYSTERESIS_LOW, 
                    high_thresh=config.EAR_HYSTERESIS_HIGH,
                    inverted=True  # EAR: low values = closed eyes
                )
                self._yawn_hysteresis = HysteresisFilter(
                    low_thresh=config.MAR_HYSTERESIS_LOW, 
                    high_thresh=config.MAR_HYSTERESIS_HIGH,
                    inverted=False  # MAR: high values = yawning
                )
            else:
                self._eye_hysteresis = HysteresisFilter(low_thresh=0.24, high_thresh=0.30, inverted=True)
                self._yawn_hysteresis = HysteresisFilter(low_thresh=0.47, high_thresh=0.57, inverted=False)
            
            # Confidence trackers
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
            
            # Adaptive thresholds
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
        
        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            raise RuntimeError("Cannot open webcam")
        
        # Camera settings
        camera_width = config.CAMERA_WIDTH if CONFIG_AVAILABLE else 1280
        camera_height = config.CAMERA_HEIGHT if CONFIG_AVAILABLE else 720
        camera_fps = config.CAMERA_FPS if CONFIG_AVAILABLE else 30
        
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap.set(cv2.CAP_PROP_FPS, camera_fps)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)
        self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        
        self._running = True
        
        # Start separate threads
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        
        self._capture_thread.start()
        self._detection_thread.start()

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
        with self._lock:
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
            time.sleep(0.05)
            wait_count += 1

        last_sent: Optional[bytes] = None

        while self._running:
            try:
                with self._lock:
                    jpeg = self._latest_jpeg

                if not jpeg:
                    time.sleep(0.005)
                    continue

                # If producer is slower than consumer, don't spam duplicates
                if jpeg is last_sent:
                    time.sleep(0.005)
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
                time.sleep(0.05)

        logger.info("MJPEG generator stopped (monitor not running)")

    # =============================
    # CAPTURE THREAD (High FPS)
    # =============================
    def _capture_loop(self) -> None:
        """Dedicated thread for camera capture - runs at full speed"""
        while self._running:
            ok, frame = self._cap.read()
            if not ok:
                time.sleep(0.001)
                continue
            
            # Drop stale frame if queue is full, then push newest frame.
            # This prevents "lag after some time" caused by backlog.
            if self._frame_queue.full():
                try:
                    _ = self._frame_queue.get_nowait()
                except Exception:
                    pass
            try:
                self._frame_queue.put_nowait(frame)
            except Exception:
                pass

    # =============================
    # DETECTION THREAD (Processes frames)
    # =============================
    def _detection_loop(self) -> None:
        """Dedicated thread for detection - OPTIMIZED FOR SPEED"""
        import logging
        logger = logging.getLogger(__name__)
        frame_count = 0
        last_log_time = time.time()
        
        while self._running:
            if self._frame_queue.empty():
                time.sleep(0.001)
                continue
            
            frame = self._frame_queue.get()
            self._frame_counter += 1
            frame_count += 1
            
            # Higher target FPS
            now = time.time()
            target_fps = 30.0
            min_dt = 1.0 / target_fps
            
            if (now - self._last_output_ts) < min_dt:
                self._frames_skipped += 1
                continue
                
            self._last_output_ts = now
            self._frames_processed += 1
            
            # Process at 70% scale for speed
            scale = 0.7
            small = cv2.resize(frame, None, fx=scale, fy=scale, 
                             interpolation=cv2.INTER_NEAREST)  # Fastest interpolation
            
            # Process frame
            annotated = self._process_frame_fast(small, frame.shape)
            
            # Fast JPEG encoding
            encode_success, buf = cv2.imencode(".jpg", annotated, [
                int(cv2.IMWRITE_JPEG_QUALITY), 75,
            ])
            
            if encode_success:
                with self._lock:
                    self._latest_jpeg = buf.tobytes()
                    
                # Log stats every 5 seconds
                if now - last_log_time > 5.0:
                    fps = frame_count / 5.0
                    logger.info(f"Processing FPS: {fps:.1f}")
                    frame_count = 0
                    last_log_time = now

    # =============================
    # FAST PROCESSING
    # =============================
    def _process_frame_fast(self, small_frame: np.ndarray, original_shape: tuple) -> np.ndarray:
        """Optimized processing with ALL features enabled"""
        img = small_frame.copy()
        
        # Decide what to run this frame
        run_yolo = (self._frame_counter % self._yolo_interval == 0)
        run_face = (self._frame_counter % self._face_interval == 0)
        
        # Precompute gray once per frame
        gray = None

        # =============================
        # 1) PHONE DETECTION - YOLO MODEL BASED
        # =============================
        phone_detected = False
        
        # Run YOLO detection every N frames
        if run_yolo:
            # Prepare image for YOLO
            yolo_input = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            
            # Run YOLO inference
            with torch.no_grad():
                results = self.model(yolo_input, size=640)  # Use 640 for better detection
            
            # Cache results for next frames
            self._cached_detections['yolo_result'] = results
            self._cached_detections['timestamp'] = time.time()
        else:
            # Use cached results
            results = self._cached_detections['yolo_result']
        
        # Process YOLO results for phone detection
        if results is not None:
            # Get detections as pandas dataframe
            detections = results.pandas().xyxy[0]
            
            # Look for phone (class 67) with low confidence threshold
            phone_detections = detections[
                (detections['class'] == 67) & 
                (detections['confidence'] >= 0.60)
            ]
            
            # Draw bounding boxes for detected phones
            for _, detection in phone_detections.iterrows():
                x1, y1, x2, y2 = int(detection['xmin']), int(detection['ymin']), int(detection['xmax']), int(detection['ymax'])
                conf = detection['confidence']
                
                # Draw box
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 255), 2)
                cv2.putText(img, f"Phone {conf:.2f}", (x1, y1 - 5), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                
                phone_detected = True
            
            # Debug: Show YOLO status
            cv2.putText(img, f"YOLO: {'RUN' if run_yolo else 'CACHED'}", (10, 210), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            cv2.putText(img, f"Phones: {len(phone_detections)}", (10, 230), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        
        # Use confidence tracker if available, otherwise use simple counter
        if SMOOTHING_AVAILABLE:
            phone_alert = self._phone_confidence.update(phone_detected)
        else:
            self._phone_counter = self._phone_counter + 1 if phone_detected else 0
            phone_alert = self._phone_counter >= self._PHONE_CONSEC_FRAMES
            
        self._set_alert("phone_detected", phone_alert)
        
        if self._alerts["phone_detected"]:
            cv2.putText(img, "PUT DOWN PHONE!", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # =============================
        # 2) FACE DETECTION & ANALYSIS
        # =============================
        if self.detector is None or self.predictor is None:
            self._set_alert("eye_closed", False)
            self._set_alert("yawning", False)
            self._set_alert("not_looking_forward", False)
            self._set_alert("head_tilt_alert", False)
            return img
        
        # Run face detection
        if run_face:
            gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
            faces = self.detector(gray, 0)
            self._cached_detections['faces'] = faces
        else:
            faces = self._cached_detections['faces']
        
        # Not looking forward check with confidence tracking if available
        not_forward = len(faces) == 0
        if SMOOTHING_AVAILABLE:
            forward_alert = not self._forward_confidence.update(not not_forward)
        else:
            self._not_forward_counter = self._not_forward_counter + 1 if not_forward else 0
            forward_alert = self._not_forward_counter >= self._NOT_FORWARD_CONSEC_FRAMES
            
        self._set_alert("not_looking_forward", forward_alert)
        
        if self._alerts["not_looking_forward"]:
            cv2.putText(img, "LOOK FORWARD!", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # =============================
        # 3) FACIAL LANDMARKS & METRICS - ALL FEATURES
        # =============================
        eye_closed = False
        yawning = False
        head_tilt_alert = False
        
        if gray is None:
            gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)

        # Process FIRST face with ALL features
        if len(faces) > 0:
            face = faces[0]
            shape = self.predictor(gray, face)
            pts = np.array([(p.x, p.y) for p in shape.parts()], dtype=np.int32)
            
            (x, y, w, h) = (face.left(), face.top(), face.width(), face.height())
            cv2.rectangle(img, (x, y), (x + w, y + h), (255, 0, 0), 2)
            
            # Draw facial landmarks (optional - comment out if too slow)
            for point in pts:
                cv2.circle(img, (point[0], point[1]), 1, (0, 255, 255), -1)
            
            # EYE ASPECT RATIO - WITH OPTIONAL SMOOTHING
            left_eye = pts[36:42]
            right_eye = pts[42:48]
            left_ear = self._eye_aspect_ratio(left_eye)
            right_ear = self._eye_aspect_ratio(right_eye)
            raw_ear = (left_ear + right_ear) / 2.0
            
            # Initialize eye_closed
            eye_closed = False
            
            if SMOOTHING_AVAILABLE:
                # Apply smoothing filters
                smooth_ear = self._ear_filter.update(raw_ear)
                filtered_ear = self._ear_median.update(smooth_ear)
                
                # Use adaptive threshold and hysteresis
                eye_closed_raw, adaptive_thresh = self._adaptive_ear.update(filtered_ear)
                eye_closed = self._eye_hysteresis.update(filtered_ear)
                
                # Display values - RED when EAR is below threshold (eyes closing), GREEN when normal
                ear_color = (0, 0, 255) if filtered_ear < adaptive_thresh else (0, 255, 0)
                cv2.putText(img, f'EAR: {filtered_ear:.3f}', (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, ear_color, 2)
                cv2.putText(img, f'Thresh: {adaptive_thresh:.3f}', (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            else:
                # Simple threshold detection
                filtered_ear = raw_ear
                
                # Debug: Show what's happening
                cv2.putText(img, f'RAW EAR: {raw_ear:.3f}', (10, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # For normal EAR threshold (like 0.27), we check if EAR is LESS than threshold
                # Normal EAR values are 0.2-0.4, lower values indicate closed eyes
                if raw_ear < self._EAR_THRESH:
                    self._eye_counter += 1
                    cv2.putText(img, f'Eye Counter: {self._eye_counter} (CLOSING)', (10, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    if self._eye_counter >= self._EAR_CONSEC_FRAMES:
                        eye_closed = True
                        self._repeat_counter += 1
                else:
                    self._eye_counter = 0
                    cv2.putText(img, f'Eyes OPEN (EAR >= {self._EAR_THRESH:.3f})', (10, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    if not eye_closed:
                        self._repeat_counter = 0
                
                # Color logic: RED when eyes are closing (EAR < threshold), GREEN when normal
                ear_color = (0, 0, 255) if raw_ear < self._EAR_THRESH else (0, 255, 0)
                cv2.putText(img, f'EAR: {filtered_ear:.3f}', (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, ear_color, 2)
                cv2.putText(img, f'Thresh: {self._EAR_THRESH:.3f}', (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            
            # Draw eye contours with color coding
            left_eyeHull = cv2.convexHull(left_eye)
            right_eyeHull = cv2.convexHull(right_eye)
            # RED when drowsy (eye_closed = True), GREEN when normal
            eye_contour_color = (0, 0, 255) if eye_closed else (0, 255, 0)
            cv2.drawContours(img, [left_eyeHull], -1, eye_contour_color, 2)
            cv2.drawContours(img, [right_eyeHull], -1, eye_contour_color, 2)
            
            if eye_closed:
                cv2.putText(img, "DROWSINESS DETECTED!", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            
            # MOUTH ASPECT RATIO - WITH OPTIONAL SMOOTHING
            mouth = pts[48:68]
            mouthHull = cv2.convexHull(mouth)
            raw_mar = self._mouth_aspect_ratio(mouth)
            
            if SMOOTHING_AVAILABLE:
                # Apply smoothing filters
                smooth_mar = self._mar_filter.update(raw_mar)
                filtered_mar = self._mar_median.update(smooth_mar)
                
                # Use hysteresis for yawn detection
                yawning = self._yawn_hysteresis.update(filtered_mar)
            else:
                # Simple threshold detection
                filtered_mar = raw_mar
                if raw_mar > self._MAR_THRESH:
                    self._yawn_counter += 1
                    if self._yawn_counter >= self._YAWN_CONSEC_FRAMES:
                        yawning = True
                else:
                    self._yawn_counter = 0
            
            # Draw mouth contour with color coding
            mouth_color = (0, 0, 255) if yawning else (0, 255, 0)
            cv2.drawContours(img, [mouthHull], -1, mouth_color, 2)
            
            # Display MAR value
            cv2.putText(img, f'MAR: {filtered_mar:.3f}', (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.6, mouth_color, 2)
            
            if yawning:
                cv2.putText(img, "YAWNING DETECTED!", (x, y - 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            
            # HEAD ANGLE - IMPROVED CALCULATION
            eye_left = pts[36]
            eye_right = pts[45]
            nose_tip = pts[33]
            head_angle = self._calculate_head_angle(np.array(eye_left), np.array(eye_right), np.array(nose_tip))
            
            # Display head angle with color coding
            angle_color = (0, 0, 255) if not (70 < head_angle < 115) else (0, 255, 0)
            cv2.putText(img, f'Head: {head_angle:.1f}°', (10, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.6, angle_color, 2)
            
            # HEAD ANGLE - IMPROVED CALCULATION
            eye_left = pts[36]
            eye_right = pts[45]
            nose_tip = pts[33]
            head_angle = self._calculate_head_angle(np.array(eye_left), np.array(eye_right), np.array(nose_tip))
            
            # Display head angle with color coding
            head_angle_min = config.HEAD_ANGLE_MIN if CONFIG_AVAILABLE else 70
            head_angle_max = config.HEAD_ANGLE_MAX if CONFIG_AVAILABLE else 115
            angle_color = (0, 0, 255) if not (head_angle_min < head_angle < head_angle_max) else (0, 255, 0)
            cv2.putText(img, f'Head: {head_angle:.1f}°', (10, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.6, angle_color, 2)
            
            # Head tilt detection
            if not (head_angle_min < head_angle < head_angle_max):
                self._head_tilt_counter += 1
                if self._head_tilt_counter >= self._HEAD_TILT_CONSEC_FRAMES:
                    head_tilt_alert = True
                    alert_msg = config.ALERT_MESSAGES['head_tilt_alert'] if CONFIG_AVAILABLE else "STRAIGHTEN HEAD!"
                    alert_color = config.COLORS['alert'] if CONFIG_AVAILABLE else (0, 0, 255)
                    cv2.putText(img, alert_msg, (x, y - 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, alert_color, 2)
            else:
                self._head_tilt_counter = 0
        
        # Update alerts
        self._set_alert("eye_closed", eye_closed)
        self._set_alert("yawning", yawning)
        self._set_alert("head_tilt_alert", head_tilt_alert)
        
        return img

    # =============================
    # HELPER METHODS
    # =============================
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

    def _set_alert(self, key: str, value: bool) -> None:
        with self._lock:
            self._alerts[key] = bool(value)
            self._alerts["timestamp"] = int(time.time())