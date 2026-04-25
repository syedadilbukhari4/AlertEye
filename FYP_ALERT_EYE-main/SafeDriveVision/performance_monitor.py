"""
Performance monitoring script for SafeDriveVision
Run this to monitor FPS, latency, and detection accuracy
"""
import time
import requests
import json
import threading
from collections import deque
import statistics

class PerformanceMonitor:
    def __init__(self, backend_url="http://127.0.0.1:8000"):
        self.backend_url = backend_url
        self.fps_history = deque(maxlen=100)
        self.latency_history = deque(maxlen=100)
        self.alert_history = deque(maxlen=1000)
        self.running = False
        
    def start_monitoring(self):
        self.running = True
        monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        monitor_thread.start()
        
    def stop_monitoring(self):
        self.running = False
        
    def _monitor_loop(self):
        last_time = time.time()
        frame_count = 0
        
        while self.running:
            try:
                # Measure API latency
                start_time = time.time()
                response = requests.get(f"{self.backend_url}/alerts", timeout=1.0)
                latency = (time.time() - start_time) * 1000  # ms
                
                if response.status_code == 200:
                    self.latency_history.append(latency)
                    alerts = response.json()
                    self.alert_history.append(alerts)
                    
                    frame_count += 1
                    current_time = time.time()
                    
                    # Calculate FPS every second
                    if current_time - last_time >= 1.0:
                        fps = frame_count / (current_time - last_time)
                        self.fps_history.append(fps)
                        
                        # Print stats
                        self._print_stats(fps, latency)
                        
                        frame_count = 0
                        last_time = current_time
                        
            except Exception as e:
                print(f"Monitor error: {e}")
                
            time.sleep(0.1)  # 10Hz monitoring
            
    def _print_stats(self, current_fps, current_latency):
        if len(self.fps_history) > 0 and len(self.latency_history) > 0:
            avg_fps = statistics.mean(self.fps_history)
            avg_latency = statistics.mean(self.latency_history)
            max_latency = max(self.latency_history)
            
            # Count recent alerts
            recent_alerts = list(self.alert_history)[-60:]  # Last 60 samples
            alert_counts = {
                'eye_closed': sum(1 for a in recent_alerts if a.get('eye_closed', False)),
                'yawning': sum(1 for a in recent_alerts if a.get('yawning', False)),
                'phone_detected': sum(1 for a in recent_alerts if a.get('phone_detected', False)),
                'not_looking_forward': sum(1 for a in recent_alerts if a.get('not_looking_forward', False)),
                'head_tilt_alert': sum(1 for a in recent_alerts if a.get('head_tilt_alert', False)),
            }
            
            print(f"\n=== Performance Stats ===")
            print(f"FPS: {current_fps:.1f} (avg: {avg_fps:.1f})")
            print(f"Latency: {current_latency:.1f}ms (avg: {avg_latency:.1f}ms, max: {max_latency:.1f}ms)")
            print(f"Recent Alerts (last 6s): {alert_counts}")
            print("=" * 25)

if __name__ == "__main__":
    monitor = PerformanceMonitor()
    print("Starting performance monitoring...")
    print("Press Ctrl+C to stop")
    
    try:
        monitor.start_monitoring()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping monitor...")
        monitor.stop_monitoring()