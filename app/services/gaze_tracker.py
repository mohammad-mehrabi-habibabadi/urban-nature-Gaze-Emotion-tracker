# File: app/services/gaze_tracker.py
# Purpose: State-of-the-art Gaze Estimation (L2CS-Net) with 3D Ray Casting & Off-Screen Detection.

import torch
import torch.nn as nn
import torch.optim as optim  # <-- Added for calibration network training
import torchvision
from torchvision import transforms
import numpy as np
import os
import math

# --- 1. L2CS-Net model architecture ---
class L2CS(nn.Module):
    def __init__(self, block, layers, num_bins):
        super(L2CS, self).__init__()
        self.inplanes = 64
        self.conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.layer1 = self._make_layer(block, 64, layers[0])
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2)
        self.layer3 = self._make_layer(block, 256, layers[2], stride=2)
        self.layer4 = self._make_layer(block, 512, layers[3], stride=2)
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))

        self.fc_yaw_gaze = nn.Linear(512 * block.expansion, num_bins)
        self.fc_pitch_gaze = nn.Linear(512 * block.expansion, num_bins)

    def _make_layer(self, block, planes, blocks, stride=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(self.inplanes, planes * block.expansion, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(planes * block.expansion),
            )
        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample))
        self.inplanes = planes * block.expansion
        for _ in range(1, blocks):
            layers.append(block(self.inplanes, planes))
        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        x = self.avgpool(x)
        x = x.view(x.size(0), -1)
        pre_yaw = self.fc_yaw_gaze(x)
        pre_pitch = self.fc_pitch_gaze(x)
        return pre_yaw, pre_pitch


# --- Polynomial Regression Model ---
class PolynomialCalibrator:
    def __init__(self):
        self.coeffs_x = None
        self.coeffs_y = None
        
    def fit(self, inputs, targets):
        # inputs: list of points (x_geo, y_geo)
        # targets: List of true points (x_true, y_true)
        # Convert input to a polynomial matrix of degree 2 (x, y, x^2, y^2, xy, 1)
        A = []
        for x, y in inputs:
            A.append([x**2, y**2, x*y, x, y, 1])
        A = np.array(A)
        
        target_x = np.array([t[0] for t in targets])
        target_y = np.array([t[1] for t in targets])
        
        # Solving the Least Squares Equation
        # This method finds the best possible curve to pass through 14 points.
        self.coeffs_x, _, _, _ = np.linalg.lstsq(A, target_x, rcond=None)
        self.coeffs_y, _, _, _ = np.linalg.lstsq(A, target_y, rcond=None)
        
    def predict(self, x, y):
        if self.coeffs_x is None: return x, y
        # Applying the calculated coefficients to the new point
        features = np.array([x**2, y**2, x*y, x, y, 1])
        new_x = np.dot(features, self.coeffs_x)
        new_y = np.dot(features, self.coeffs_y)
        return new_x, new_y

# --- 2. Smart gaze tracker ---
class GazeTracker:
    def __init__(self):
        # Device selection
        if torch.cuda.is_available():
            self.device = torch.device('cuda')
            print(f"✅ GazeTracker running on GPU: {torch.cuda.get_device_name(0)}")
        else:
            self.device = torch.device('cpu')
            print("⚠️ GazeTracker running on CPU (Expect slowness)")

        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_path = os.path.join(current_dir, "L2CSNet_gaze360.pkl")

        # Load the L2CS-Net model
        try:
            self.model = L2CS(torchvision.models.resnet.Bottleneck, [3, 4, 6, 3], 90)
            if os.path.exists(self.model_path):
                saved_state_dict = torch.load(self.model_path, map_location=self.device)
                self.model.load_state_dict(saved_state_dict, strict=False)
                self.model.to(self.device)
                self.model.eval()
                print("✅L2CS-Net Model Loaded Successfully.")
            else:
                print(f"⚠️Error: Model file not found at {self.model_path}")
                self.model = None
        except Exception as e:
            print(f"⚠️ERROR loading Gaze Model: {e}")
            self.model = None

        # Preprocessing for model input
        self.transformations = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize(448),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])

        self.softmax = nn.Softmax(dim=1)
        self.idx_tensor = torch.FloatTensor([i for i in range(90)]).to(self.device)

        # --- Calibration Settings ---
        self.calib_model = PolynomialCalibrator() # Using a mathematical model instead of a neural one
       
        self.is_calibrated = False
        self.calibration_data = []  # Save pairs (raw, target)
        self.raw_gaze_buffer = []   # Buffer for averaging calibration data
        # -------------------------

        #  smoothing
        self.prev_x, self.prev_y = 0.5, 0.5

        # Screen and window settings
        self.screen_config = {
            "screen_w": 1920, "screen_h": 1080,
            "window_w": 1920, "window_h": 1080,
            "window_x": 0, "window_y": 0
        }

        # Physical parameters
        self.monitor_inches = 17.3   # Default
        self.camera_pos = "top"      # top / bottom / left / right

        # Adjustable parameters for calibration
        self.VERTICAL_GAIN = 1.0      # Remove manual manipulation (leave it to AI)
        self.HORIZONTAL_GAIN = 1.0    # Remove manual manipulation
        self.PITCH_DOWN_BIAS = 0.0    # Remove bias
        self.FOV_FACTOR = 0.5         # Average standard lenses
        self.SMOOTH_ALPHA = 0.6       # Laggier but smoother

    # ---------------------------
    # Exterior settings
    # ---------------------------
    def update_screen_config(self, config: dict):
        if config:
            self.screen_config.update(config)

    def set_monitor_size(self, inches: float):
        if inches and inches > 0:
            self.monitor_inches = float(inches)
            print(f"🖥️ Monitor size set to: {self.monitor_inches} inches")

    def set_camera_pos(self, pos: str):
        """Adjust the physical position of the camera on the monitor: top / bottom / left / right"""
        if pos in ["top", "bottom", "left", "right"]:
            self.camera_pos = pos
            print(f"📷 Camera position set to: {self.camera_pos}")

    # --- Calibration methods ---
    def reset_calibration(self):
        self.is_calibrated = False
        self.calibration_data = []
        self.calib_model = PolynomialCalibrator() # Reset mathematical model
        print("🔄 Calibration reset.")

    def store_calibration_point(self, target_x, target_y):
        """Save current gaze point (Raw) as training data for target (Target)"""
        # Increased minimum data required to 10 frames to ensure average quality
        if len(self.raw_gaze_buffer) < 10:
            print("⚠️ Not enough gaze data to store calibration point.")
            return False
        
        # Buffer: (x_geo, y_geo, pitch, yaw)
        buffer_arr = np.array(self.raw_gaze_buffer)
        means = np.mean(buffer_arr, axis=0) 

        # Mathematical model input: only calculated geometric coordinates
        input_geo = [means[0], means[1]] 
        
        # Target: Real page coordinates
        target_true = [target_x, target_y]

        # Save data pair: (Input, Target)
        self.calibration_data.append((input_geo, target_true))
        
        print(f"➕ Calib Point Added.")
        return True
        print(f"➕ Calib Point: Raw(X:{means[0]:.2f}, Y:{means[1]:.2f}, D:{means[2]:.0f}, Head:{means[3]:.2f}) -> Target({target_x}, {target_y})")
        return True

    def train_calibration(self):
        """Calculating the coefficient matrix for polynomial regression"""
        if len(self.calibration_data) < 5:
            print("⚠️ Not enough points for Polynomial Regression (Need at least 5).")
            return False

        # Extracting inputs and outputs from list
        inputs = [d[0] for d in self.calibration_data] # [(x,y), ...]
        targets = [d[1] for d in self.calibration_data] # [(tx,ty), ...]

        try:
            self.calib_model.fit(inputs, targets)
            self.is_calibrated = True
            print(f"✅ Polynomial Calibration Calculated Successfully with {len(inputs)} points.")
            return True
        except Exception as e:
            print(f"❌ Calibration Failed: {e}")
            return False
    # -------------------------

    # ---------------------------
    # Auxiliary functions
    # ---------------------------
    def _get_distance_cm(self, landmarks, frame_width: int) -> float:
        """Estimating the user's distance from the camera based on the distance between the two eyes (MediaPipe FaceMesh indices 33, 263)."""
        left_eye = landmarks.landmark[33]
        right_eye = landmarks.landmark[263]

        dist_pixels = math.sqrt(
            (left_eye.x - right_eye.x) ** 2 + (left_eye.y - right_eye.y) ** 2
        ) * frame_width

        focal_length = 650.0  # Typical webcam approximation
        avg_interpupillary_dist_cm = 6.3

        if dist_pixels <= 0:
            return 0.0

        distance_cm = (avg_interpupillary_dist_cm * focal_length) / dist_pixels
        return distance_cm

    def _get_face_crop(self, frame, landmarks):
        """Cut out a face from an image based on all facial landmarks"""
        h, w, _ = frame.shape
        xs = [lm.x for lm in landmarks.landmark]
        ys = [lm.y for lm in landmarks.landmark]

        x_min, x_max = int(min(xs) * w), int(max(xs) * w)
        y_min, y_max = int(min(ys) * h), int(max(ys) * h)

        pad_x = int((x_max - x_min) * 0.1)
        pad_y = int((y_max - y_min) * 0.1)

        return frame[
            max(0, y_min - pad_y):min(h, y_max + pad_y),
            max(0, x_min - pad_x):min(w, x_max + pad_x)
        ]

    # --- AI: yaw/pitch prediction ---
    def _predict_head_pose(self, frame, landmarks):
        """Running the L2CS-Net model and converting yaw/pitch (to radians) with Gain Correction"""
        try:
            face_img = self._get_face_crop(frame, landmarks)
            if face_img is None or face_img.size == 0:
                return None, None

            img = self.transformations(face_img).unsqueeze(0).to(self.device)

            with torch.no_grad():
                gaze_yaw, gaze_pitch = self.model(img)
                pitch_pred = self.softmax(gaze_pitch)
                yaw_pred = self.softmax(gaze_yaw)

                pitch_raw = (torch.sum(pitch_pred[0] * self.idx_tensor) * 4 - 180).item() * np.pi / 180.0
                yaw_raw = (torch.sum(yaw_pred[0] * self.idx_tensor) * 4 - 180).item() * np.pi / 180.0

                # Gain Correction
                pitch = pitch_raw * self.VERTICAL_GAIN
                yaw = yaw_raw * self.HORIZONTAL_GAIN

                # Strengthening downward gaze
                if pitch < 0:
                    pitch -= self.PITCH_DOWN_BIAS

                return yaw, pitch

        except Exception as e:
            print(f"[GazeTracker] AI Error: {e}")
            return None, None

    # --- Geometry: Ray Casting ---
    def _project_ray_to_screen(self, yaw, pitch, landmarks, distance_cm):
        """
        Convert yaw/pitch + distance + face position to normalized coordinates (0..1, 0..1) on the monitor
        Using 3D Ray Casting.
        """

        # 1. Physical dimensions of the monitor based on diagonal and resolution
        scr_w_px = self.screen_config['screen_w']
        scr_h_px = self.screen_config['screen_h']

        diag_cm = self.monitor_inches * 2.54

        aspect_w = scr_w_px if scr_w_px > 0 else 16
        aspect_h = scr_h_px if scr_h_px > 0 else 9

        k = diag_cm / math.sqrt(aspect_w ** 2 + aspect_h ** 2)
        screen_width_cm = aspect_w * k
        screen_height_cm = aspect_h * k

        # 2. 3D eye position (approximate head translation)
        left_eye = landmarks.landmark[33]
        right_eye = landmarks.landmark[263]
        face_x_norm = (left_eye.x + right_eye.x) / 2.0
        face_y_norm = (left_eye.y + right_eye.y) / 2.0

        # Convert from image normal coordinates to centimeters (relative to the center of the lens)
        eye_pos_x = (face_x_norm - 0.5) * distance_cm * self.FOV_FACTOR * 2.0
        eye_pos_y = (face_y_norm - 0.5) * distance_cm * self.FOV_FACTOR * 2.0
        eye_pos_z = distance_cm

        # 3. Look vector based on yaw/pitch
        # If you see that left/right or up/down is reversed, switch the signs.
        vec_x = np.sin(yaw)
        vec_y = -np.sin(pitch)
        vec_z = -np.cos(yaw) * np.cos(pitch)

        if abs(vec_z) < 1e-3:
            vec_z = -1e-3  # Prevent division by zero

        # 4. Intersection of the gaze line with the Z=0 plane (monitor)
        t = -eye_pos_z / vec_z
        if t <= 0:
            # Looking in the opposite direction of the page (e.g., up or behind the head)
            return None, None

        hit_x = eye_pos_x + t * vec_x
        hit_y = eye_pos_y + t * vec_y

        # 5. Considering the camera position on the monitor
        bezel_cm = 2.0  # Approximate margin

        if self.camera_pos == "top":
            # Top middle camera – monitor below it
            screen_left = -screen_width_cm / 2.0
            screen_top = bezel_cm
        elif self.camera_pos == "bottom":
            # Camera in the bottom middle – monitor above it
            screen_left = -screen_width_cm / 2.0
            screen_top = -bezel_cm - screen_height_cm
        elif self.camera_pos == "left":
            # Camera middle left – monitor right
            screen_left = bezel_cm
            screen_top = -screen_height_cm / 2.0
        elif self.camera_pos == "right":
            # Middle right camera – left monitor
            screen_left = -bezel_cm - screen_width_cm
            screen_top = -screen_height_cm / 2.0
            # Add horizontal/vertical offset if you want.
        else:
            # Default: top
            screen_left = -screen_width_cm / 2.0
            screen_top = bezel_cm

        # 6. Convert hit_x/hit_y to normalized coordinates (0..1)
        x = (hit_x - screen_left) / screen_width_cm
        y = (hit_y - screen_top) / screen_height_cm

        return x, y

    # --- Main function: Orchestration ---
    def estimate_gaze(self, frame, landmarks):
        """
        Input:
            frame: BGR frame from OpenCV
            landmarks: MediaPipe FaceMesh output for the same face
        Output:
            dict:
                x, y: normalized gaze coordinates (0..1, 0..1)
                status: on_screen / off_monitor / off_browser
                distance_cm: user distance from camera
        """
        if self.model is None or landmarks is None:
            return None

        h, w, _ = frame.shape
        distance_cm = self._get_distance_cm(landmarks, w)

        # Eliminate outliers: too close or too far
        if distance_cm < 30 or distance_cm > 150:
            return None

        # 1. Yaw/pitch prediction
        yaw, pitch = self._predict_head_pose(frame, landmarks)
        if yaw is None or pitch is None:
            return None

        # 2. Convert to page coordinates
        x, y = self._project_ray_to_screen(yaw, pitch, landmarks, distance_cm)
        
        ## --- Buffering for calibration ---
        if x is not None and y is not None:
            # Save (GeoX, GeoY, Pitch, Yaw) - Remove spacing for simplicity
            self.raw_gaze_buffer.append((x, y, pitch, yaw))
            if len(self.raw_gaze_buffer) > 15: 
                self.raw_gaze_buffer.pop(0)
        # -------------------------------
        
        # Save the initial geometric value.
        geo_x, geo_y = x, y

        if x is None or y is None:
            status = "off_monitor"
            return {
                "x": self.prev_x,
                "y": self.prev_y,
                "status": status,
                "distance_cm": round(distance_cm, 1)
            }

        # 3. Apply calibration (method: Polynomial Mapping)
        if self.is_calibrated and x is not None:
            # The mathematical model directly maps geometric coordinates (incorrect) to plane coordinates (correct).
            x, y = self.calib_model.predict(geo_x, geo_y)

            # Clipping - We leave the range a little wider so that the edge points are not clipped.
            x = max(-0.1, min(1.1, x))
            y = max(-0.1, min(1.1, y))
         
                
               

        # 4. Smoothing
        alpha = self.SMOOTH_ALPHA
        self.prev_x = (1 - alpha) * self.prev_x + alpha * x
        self.prev_y = (1 - alpha) * self.prev_y + alpha * y
        final_x, final_y = self.prev_x, self.prev_y

        # 4. On/off screen and on/off browser status
        status = "on_screen"
        if final_x < 0.0 or final_x > 1.0 or final_y < 0.0 or final_y > 1.0:
            status = "off_monitor"
        else:
            pixel_x = final_x * self.screen_config['screen_w']
            pixel_y = final_y * self.screen_config['screen_h']

            wx = self.screen_config['window_x']
            wy = self.screen_config['window_y']
            ww = self.screen_config['window_w']
            wh = self.screen_config['window_h']

            if not (wx <= pixel_x <= wx + ww and wy <= pixel_y <= wy + wh):
                status = "off_browser"

        return {
            "x": final_x,
            "y": final_y,
            "status": status,
            "distance_cm": round(distance_cm, 1)
        }


gaze_tracker = GazeTracker()