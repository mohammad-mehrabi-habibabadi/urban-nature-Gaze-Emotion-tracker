# File: app/cv/camera_manager.py
# Purpose: Manage webcam access and frame capture.

import cv2
import threading
import time

class CameraManager:
    def __init__(self, src=0):
        self.src = src
        self.cap = cv2.VideoCapture(self.src)
        self.lock = threading.Lock()
        self.running = False
        
    def start(self):
        if not self.cap.isOpened():
            self.cap.open(self.src)
        self.running = True

    def stop(self):
        self.running = False
        if self.cap.isOpened():
            self.cap.release()

    def get_frame(self):
        """
        Reads a frame from the webcam. 
        Returns (ret, frame). 
        """
        with self.lock:
            if self.running and self.cap.isOpened():
                ret, frame = self.cap.read()
                return ret, frame
            return False, None

    def __del__(self):
        self.stop()

# Global instance
camera_manager = CameraManager()
