# File: aoi_helper.py
# Purpose: Helper logic to calculate gaze intersection with UI elements (AOI Analysis).

# Add padding parameter to enlarge the detection area (fix tracker error)
def get_element_at_gaze(gaze_x, gaze_y, ui_elements, padding=0.10):
    """
    Checks which UI element the gaze point (x, y) is inside.
    padding: confidence margin (default 10 percent)
    """
    if gaze_x is None or gaze_y is None:
        return None
        
    for el in ui_elements:
        # Checking the collision of a point with a rectangle with a border (Expanded Hit Test)
        # enlarging the area on each side by the amount of padding.
        if (el['x'] - padding <= gaze_x <= el['x'] + el['w'] + padding and 
            el['y'] - padding <= gaze_y <= el['y'] + el['h'] + padding):
            return el['name']
            
    return None

def calculate_gaze_distribution(gaze_points, ui_elements):
    """
    Calculates gaze distribution.
    Input: List of viewpoints in a time interval.
    Output: Dictionary containing element name and look duration (based on number of frames).
    """
    distribution = {}
    total_frames = len(gaze_points)
    if total_frames == 0:
        return {}

    # Assumption: Each frame is about 50 milliseconds (20fps)
    frame_duration = 0.05 

    for gx, gy in gaze_points:
        target = get_element_at_gaze(gx, gy, ui_elements)
        
        if target:
            distribution[target] = distribution.get(target, 0) + frame_duration
        else:
            # Looking at the empty space (Background)
            distribution["Nothing/Background"] = distribution.get("Nothing/Background", 0) + frame_duration
            
    return distribution