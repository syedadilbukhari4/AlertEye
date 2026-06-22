"""
Advanced smoothing filters for driver monitoring system
Reduces false positives and improves accuracy
"""
import numpy as np
from collections import deque
from typing import List, Optional


class ExponentialMovingAverage:
    """Exponential moving average filter for smooth metric tracking"""
    
    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha
        self.value: Optional[float] = None
    
    def update(self, new_value: float) -> float:
        if self.value is None:
            self.value = new_value
        else:
            self.value = self.alpha * new_value + (1 - self.alpha) * self.value
        return self.value
    
    def get_value(self) -> float:
        return self.value if self.value is not None else 0.0


class MedianFilter:
    """Median filter to remove outliers"""
    
    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        self.values = deque(maxlen=window_size)
    
    def update(self, new_value: float) -> float:
        self.values.append(new_value)
        return float(np.median(list(self.values)))


class HysteresisFilter:
    """Hysteresis filter to prevent rapid state changes"""
    
    def __init__(self, low_thresh: float, high_thresh: float, inverted: bool = False):
        self.low_thresh = low_thresh
        self.high_thresh = high_thresh
        self.state = False
        self.inverted = inverted
    
    def update(self, value: float) -> bool:
        if self.inverted:
            # For EAR: low values = closed eyes (True), high values = open eyes (False)
            if not self.state and value < self.low_thresh:
                self.state = True
            elif self.state and value > self.high_thresh:
                self.state = False
        else:
            # For MAR: high values = yawning (True), low values = normal (False)
            if not self.state and value > self.high_thresh:
                self.state = True
            elif self.state and value < self.low_thresh:
                self.state = False
        return self.state


class ConfidenceTracker:
    """Tracks confidence of detections over time"""
    
    def __init__(self, window_size: int = 10, confidence_thresh: float = 0.7):
        self.window_size = window_size
        self.confidence_thresh = confidence_thresh
        self.detections = deque(maxlen=window_size)
    
    def update(self, detected: bool) -> bool:
        self.detections.append(1.0 if detected else 0.0)
        confidence = sum(self.detections) / len(self.detections)
        return confidence >= self.confidence_thresh


class AdaptiveThreshold:
    """Adaptive threshold that adjusts based on recent history"""
    
    def __init__(self, initial_thresh: float, adaptation_rate: float = 0.01):
        self.base_thresh = initial_thresh
        self.current_thresh = initial_thresh
        self.adaptation_rate = adaptation_rate
        self.recent_values = deque(maxlen=50)
    
    def update(self, value: float) -> tuple[bool, float]:
        self.recent_values.append(value)
        
        if len(self.recent_values) >= 10:
            # Adapt threshold based on recent mean
            recent_mean = np.mean(list(self.recent_values))
            target_thresh = self.base_thresh + (recent_mean - self.base_thresh) * 0.1
            self.current_thresh += (target_thresh - self.current_thresh) * self.adaptation_rate
        
        return value < self.current_thresh, self.current_thresh