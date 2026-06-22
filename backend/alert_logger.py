"""
Alert Logger - Tracks all alert events with timestamps for debugging
"""
import logging
from datetime import datetime
from pathlib import Path

class AlertLogger:
    def __init__(self, log_file="alert_log.txt"):
        self.log_file = Path(log_file)
        self.logger = logging.getLogger("AlertLogger")
        self.logger.setLevel(logging.INFO)
        
        # File handler
        fh = logging.FileHandler(self.log_file, mode='w')  # Overwrite on each run
        fh.setLevel(logging.INFO)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
        
        self.logger.info("=" * 80)
        self.logger.info("ALERT LOGGER STARTED")
        self.logger.info("=" * 80)
        
        # Track previous state to detect changes
        self.prev_state = {
            'eye_closed': False,
            'yawning': False,
            'phone_detected': False,
            'not_looking_forward': False,
            'head_tilt_alert': False
        }
    
    def log_alert_change(self, alert_data):
        """Log when alert state changes"""
        changes = []
        
        for key in self.prev_state:
            if key in alert_data:
                current = alert_data[key]
                previous = self.prev_state[key]
                
                if current != previous:
                    status = "ACTIVE" if current else "CLEARED"
                    changes.append(f"{key.upper()}: {status}")
                    self.prev_state[key] = current
        
        if changes:
            self.logger.info(f"🚨 ALERT CHANGE: {' | '.join(changes)}")
    
    def log_detection_metrics(self, ear, mar, phone_count, face_detected, head_angle):
        """Log detection metrics periodically"""
        self.logger.debug(
            f"📊 EAR={ear:.3f} | MAR={mar:.3f} | Phone={phone_count} | "
            f"Face={face_detected} | HeadAngle={head_angle:.1f}"
        )
    
    def log_info(self, message):
        """Log general information"""
        self.logger.info(message)
    
    def log_error(self, message):
        """Log errors"""
        self.logger.error(message)
