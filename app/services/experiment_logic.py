# File: app/services/experiment_logic.py
# Purpose: High-level logic for managing the experiment flow and background processing.

import threading
import time
import os   
import cv2  
import json
from app.cv.camera_manager import camera_manager
from app.cv.mediapipe_pipeline import mp_pipeline
from app.services.gaze_tracker import gaze_tracker
from app.services.emotion_detector import emotion_detector
from app.db.session import SessionLocal
from app.models.event import Event

class ExperimentLogic:
    def __init__(self):
        self.active_session_id = None
        self.current_stimulus_id = None
        self.current_context = "unknown" 
        self.is_tracking = False
        self.thread = None
        self._stop_event = threading.Event()
        self.latest_data = None 
        
        # --- Video recording variables ---
        self.video_writer = None
        self.record_enabled = False
        if not os.path.exists("recordings"):
            os.makedirs("recordings")
        # --------------------------------

    def start_session(self, session_id, record_video=False): 
        self.active_session_id = session_id
        self.record_enabled = record_video 
        camera_manager.start()
        # tracking immediately after the session begins.
        self.start_tracking()
        
    def stop_session(self):
        self.stop_tracking()
        self.active_session_id = None
        camera_manager.stop()
        
    def set_context(self, context_name, stimulus_id=None):
        """
        Change user position.
        For example: set_context("map") or set_context("stimulus_view", 5)
        """
        self.current_context = context_name
        self.current_stimulus_id = stimulus_id
        
    def start_tracking(self):
        if self.is_tracking:
            return
        self.is_tracking = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._process_loop)
        self.thread.daemon = True
        self.thread.start()
        
    def stop_tracking(self):
        self.is_tracking = False
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None

    def _process_loop(self):
        """Background loop to process frames and log data."""
        db = SessionLocal()
        last_emotion_time = 0
        current_emotion = None
        
        # --- Start recording (if enabled) ---
        if self.record_enabled and self.active_session_id:
            filename = f"recordings/session_{self.active_session_id}.avi"
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self.video_writer = cv2.VideoWriter(filename, fourcc, 20.0, (640, 480))
        # -------------------------------
        
        while self.is_tracking and not self._stop_event.is_set():
            ret, frame = camera_manager.get_frame()
            if ret:
                # --- Writing frames to a file ---
                if self.video_writer:
                    self.video_writer.write(cv2.resize(frame, (640, 480)))
                # --------------------------

                landmarks = mp_pipeline.process_frame(frame)
                if landmarks:
                    # Sending frames and landmarks to a new tracker
                    gaze = gaze_tracker.estimate_gaze(frame, landmarks)
                    
                    now = time.time()
                    if now - last_emotion_time > 0.2: 
                        # Emotion detection (every 0.2 seconds)
                        current_emotion = emotion_detector.detect_emotion(frame)
                        last_emotion_time = now
                    
                    # --- section for live dashboard---
                    #  This variable is read by WebSocket in main.py
                    self.latest_data = {
                        "gaze": gaze,
                        "emotion": current_emotion,
                        "context": self.current_context,
                        "stimulus_id": self.current_stimulus_id
                    }
                    # ---------------------------------------

                    if self.active_session_id:
                        event = Event(
                            session_id=self.active_session_id,
                            event_type="tracking_data",
                            payload={
                                "context": self.current_context,
                                "stimulus_id": self.current_stimulus_id,
                                "gaze": gaze,
                                "emotion": current_emotion
                            }
                        )
                        db.add(event)
                        db.commit()
            
            time.sleep(0.001) 
            
        # --- Final saving of the video file ---
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None
        # -----------------------------

        db.close()

experiment_logic = ExperimentLogic()
