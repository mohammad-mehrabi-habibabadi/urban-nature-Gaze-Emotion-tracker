# File: app/services/emotion_detector.py
# Purpose: Deep Learning based emotion detection with Context-Aware Logic (Focus vs Anger).

from deepface import DeepFace
import cv2
import numpy as np

class EmotionDetector:
    def __init__(self):
        print("Loading DeepFace Emotion Model...")
        # Model warm-up
        try:
            dummy = np.zeros((48, 48, 3), dtype=np.uint8)
            DeepFace.analyze(dummy, actions=['emotion'], enforce_detection=False, silent=True)
            print("✅DeepFace Model Loaded & Ready.")
        except Exception as e:
            print(f"⚠️Model warm-up warning: {e}")

    def detect_emotion(self, frame):
        """
        Emotion detection using DeepFace and applying psychological filters.
        """
        if frame is None:
            return None
            
        try:
            # Image analysis
            results = DeepFace.analyze(
                img_path=frame, 
                actions=['emotion'], 
                enforce_detection=False, 
                detector_backend='opencv', 
                silent=True
            )
            
            if not results:
                return None
                
            result = results[0]
            raw_emotion = result['dominant_emotion']
            confidence = result['emotion'][raw_emotion] # Number between 0 and 100
            
            # --- (Scientific Interpretation Layer) ---
            
            final_label = raw_emotion
            
            # Rule 1: Turn mild anger/sadness into focus
            # When working on a computer, a "focus" face (mild frown) is often mistaken for anger.
            # If the Confidence is below 70%, we consider it "focus".
            if raw_emotion in ["angry"]:
                if confidence < 70.0:
                    final_label = "focus"
                else:
                
                    pass 

            # Rule 2: High-confidence neutral state is "calm/attention"
            if raw_emotion == "neutral":
                # A more accurate name for neutral in this experiment
                pass # We keep it neutral or we can say "calm"

            return {
                "label": final_label, 
                "confidence": float(confidence) / 100.0, # Normalized between 0 and 1
                "raw_emotion": raw_emotion # keeping the raw data for the researcher.
            }
            
        except Exception as e:
            # We ignore errors so that the system does not crash.
            return None

emotion_detector = EmotionDetector()