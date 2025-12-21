# File: export_data.py
# Purpose: Export raw data to CSV and generate an intelligent narrative analysis report (English).

import sqlite3
import pandas as pd
import json
import os
from datetime import datetime
# --- Import helper module---
import aoi_helper 
# --------------------------------------

# Database Connection
db_path = "experiment.db"
if not os.path.exists(db_path):
    print(f"Error: Database file '{db_path}' not found.")
    exit()

conn = sqlite3.connect(db_path)

def safe_json_loads(val):
    if not val: return {}
    try:
        return json.loads(val)
    except:
        return {}

# --- PART 1: Export Raw CSV Data ---
print("--- Step 1: Exporting Raw Data to CSV ---")

# Export Participants
try:
    df_users = pd.read_sql_query("SELECT * FROM participant", conn)
    df_users.to_csv("data_participants.csv", index=False)
    print(" - Saved 'data_participants.csv'")
except Exception as e:
    print(f" - Warning: Could not export participants ({e})")

# Export Sessions
try:
    df_sessions = pd.read_sql_query("SELECT * FROM session", conn)
    df_sessions.to_csv("data_sessions.csv", index=False)
    print(" - Saved 'data_sessions.csv'")
except Exception as e:
    print(f" - Warning: Could not export sessions ({e})")

# Export Full Events (Optimized)
print(" - Processing Events for CSV (this may take a moment)...")
df_events = pd.read_sql_query("SELECT * FROM event ORDER BY session_id, timestamp", conn)
final_rows = []

for index, row in df_events.iterrows():
    base_data = {
        "event_id": row['id'],
        "session_id": row['session_id'],
        "timestamp": row['timestamp'],
        "event_type": row['event_type']
    }
    
    payload = safe_json_loads(row['payload'])
    
    # Extract Gaze & Status
    if "gaze" in payload and isinstance(payload["gaze"], dict):
        gaze = payload["gaze"]
        base_data["gaze_x"] = gaze.get("x")
        base_data["gaze_y"] = gaze.get("y")
        base_data["gaze_status"] = gaze.get("status", "unknown")
        base_data["distance_cm"] = gaze.get("distance_cm")

    # Extract Emotion
    if "emotion" in payload and isinstance(payload["emotion"], dict):
        emo = payload["emotion"]
        base_data["emotion_label"] = emo.get("label")
        base_data["emotion_conf"] = emo.get("confidence")

    # Extract Context
    if "context" in payload:
        base_data["page_context"] = payload["context"]
        
    # Extract Mouse
    if "x" in payload and "y" in payload and row['event_type'] == 'mouse_move':
         base_data["mouse_x"] = payload["x"]
         base_data["mouse_y"] = payload["y"]
         
    # Extract Interaction (Hover/Click)
    if "target" in payload: base_data["target_type"] = payload["target"]
    if "name" in payload: base_data["target_name"] = payload["name"]
    if "route_name" in payload: base_data["target_name"] = payload["route_name"]

    final_rows.append(base_data)

if final_rows:
    df_final = pd.DataFrame(final_rows)
    # Using utf-8-sig ensures Excel opens it correctly, even if it's all English
    df_final.to_csv("data_events_full.csv", index=False, encoding="utf-8-sig")
    print(f" - Saved 'data_events_full.csv' ({len(final_rows)} rows)")


# --- PART 2: Generate Narrative Analysis Report ---
print("\n--- Step 2: Generating Narrative Analysis Report ---")

report_lines = []
report_lines.append("==================================================")
report_lines.append("       URBAN EXPERIMENT - BEHAVIORAL ANALYSIS     ")
report_lines.append(f"       Generated on: {datetime.now()}")
report_lines.append("==================================================\n")

# Process per session
sessions = pd.read_sql_query("SELECT id, participant_id FROM session", conn)

for _, session in sessions.iterrows():
    s_id = session['id']
    p_id = session['participant_id']
    
    # Get participant code
    p_code = conn.execute(f"SELECT code FROM participant WHERE id={p_id}").fetchone()
    p_code = p_code[0] if p_code else "Unknown"
    
    report_lines.append(f"SESSION ID: {s_id} | PARTICIPANT: {p_code}")
    report_lines.append("-" * 40)
    
    # Get events for this session
    s_events = df_events[df_events['session_id'] == s_id].copy()
    
    if s_events.empty:
        report_lines.append("No events recorded for this session.\n")
        continue

    # --- Analysis 1: Distraction (Off-Screen Time) ---
    distraction_count = 0
    distraction_time = 0.0
    last_distraction_start = None
    
    # Analyze tracking data
    tracking_rows = s_events[s_events['event_type'] == 'tracking_data']
    
    for _, row in tracking_rows.iterrows():
        payload = safe_json_loads(row['payload'])
        gaze = payload.get("gaze", {})
        status = gaze.get("status", "on_screen")
        timestamp = datetime.fromisoformat(str(row['timestamp']))
        
        # Check if looking away
        if status in ["off_monitor", "off_browser"]:
            if last_distraction_start is None:
                last_distraction_start = timestamp
        else:
            # Looking back at screen
            if last_distraction_start is not None:
                duration = (timestamp - last_distraction_start).total_seconds()
                # Filter micro-movements (e.g. < 0.1s)
                if duration > 0.1:
                    distraction_time += duration
                    distraction_count += 1
                last_distraction_start = None
                
    report_lines.append(">> ATTENTION & DISTRACTION:")
    report_lines.append(f"   - Frequency: The user looked away from the experiment {distraction_count} times.")
    report_lines.append(f"   - Total Duration: {distraction_time:.2f} seconds looking off-screen/off-browser.\n")

    # --- Analysis 2: Decision Making & Hesitation (Hovers) ---
    report_lines.append(">> INTERACTION FLOW & HESITATION:")
    
    # Filter for interaction events
    interaction_events = s_events[s_events['event_type'].isin(['hover_start', 'hover_end', 'click', 'route_choice'])]
    
    active_hover = None
    emotions_during_hover = []
    
    # Iterate through all events to capture emotion DURING the hover
    for _, row in s_events.iterrows():
        etype = row['event_type']
        payload = safe_json_loads(row['payload'])
        ts = datetime.fromisoformat(str(row['timestamp']))
        
        # 1. While hovering, collect emotions
        if etype == 'tracking_data' and active_hover:
            emo = payload.get("emotion", {}).get("label")
            if emo: emotions_during_hover.append(emo)
            
        # 2. Hover Start
        elif etype == 'hover_start':
            active_hover = {
                "name": payload.get("name", "Unknown"),
                "start": ts,
            }
            emotions_during_hover = []
            
        # 3. Hover End (Calculate Hesitation)
        elif etype == 'hover_end' and active_hover:
            if payload.get("name") == active_hover["name"]:
                duration = (ts - active_hover["start"]).total_seconds()
                
                # Determine dominant emotion during this hover
                dom_emotion = "Neutral"
                if emotions_during_hover:
                    dom_emotion = max(set(emotions_during_hover), key=emotions_during_hover.count)
                
                # Only report significant pauses (> 0.5s)
                if duration > 0.5:
                    report_lines.append(f"   [Hesitation] User paused on '{active_hover['name']}' for {duration:.1f}s.")
                    report_lines.append(f"                Facial Expression: {dom_emotion.upper()}")

                    # --- Analysis of gaze distribution during hover---
                    # 1. Find the last layout saved before this moment
                    layout_events = s_events[
                        (s_events['event_type'] == 'ui_layout') & 
                        (s_events['timestamp'] <= str(row['timestamp']))
                    ]
                    
                    if not layout_events.empty:
                        # Get the latest layout (assuming it's for the current page)
                        last_layout_payload = safe_json_loads(layout_events.iloc[-1]['payload'])
                        ui_elements = last_layout_payload.get('elements', [])

                        # 2. Extracting gaze points in the hover time frame
                        hover_start_str = str(active_hover["start"])
                        hover_end_str = str(row['timestamp'])
                        
                        gaze_rows = s_events[
                            (s_events['event_type'] == 'tracking_data') & 
                            (s_events['timestamp'] >= hover_start_str) &
                            (s_events['timestamp'] <= hover_end_str)
                        ]
                        
                        gaze_points = []
                        for _, gr in gaze_rows.iterrows():
                            gp = safe_json_loads(gr['payload']).get('gaze', {})
                            # Only if user look at the monitor.
                            if gp.get('x') is not None and gp.get('status') == 'on_screen':
                                gaze_points.append((gp['x'], gp['y']))

                        # 3. Calculating gaze distribution
                        dist_stats = aoi_helper.calculate_gaze_distribution(gaze_points, ui_elements)
                        
                        # 4. Report text generation
                        if dist_stats:
                            report_lines.append("                While hovering, user looked at:")
                            for elem_name, time_looked in dist_stats.items():
                                if time_looked > 0.1: # Noise filter
                                    report_lines.append(f"                  - {elem_name}: {time_looked:.2f}s")
                    # -----------------------------------------------
                
                active_hover = None
        
        # 4. Final Decisions
        elif etype == 'click' or etype == 'route_choice':
            target = payload.get("name") or payload.get("route_name")
            target_type = payload.get("target") or "route"
            report_lines.append(f"   ---> [ACTION] Selected {target_type}: '{target}'")
            report_lines.append("")

    report_lines.append("\n" + "="*50 + "\n")

# Write Report to File
with open("analysis_report.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines))

print(f"Success! Generated 'analysis_report.txt'.")
conn.close()