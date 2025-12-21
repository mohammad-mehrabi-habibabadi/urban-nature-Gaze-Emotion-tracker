# File: app/cv/mediapipe_pipeline.py
# Purpose: Wrap MediaPipe logic for face mesh and feature extraction.

import cv2
import mediapipe as mp
import numpy as np

class MediaPipePipeline:
    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
    def process_frame(self, frame):
        """
        Processes a BGR frame and returns landmarks if a face is detected.
        """
        # Convert to RGB for MediaPipe
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_rgb.flags.writeable = False
        
        results = self.face_mesh.process(frame_rgb)
        
        frame_rgb.flags.writeable = True
        
        if results.multi_face_landmarks:
            # Return the first face's landmarks
            return results.multi_face_landmarks[0]
        return None

# Global instance
mp_pipeline = MediaPipePipeline()
