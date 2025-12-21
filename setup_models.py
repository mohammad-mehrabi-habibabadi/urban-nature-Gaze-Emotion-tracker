import os
import gdown

def setup_model():
    """
    Downloads the pre-trained L2CS-Net model weights from Google Drive.
    Checks if the file already exists to avoid redundant downloads.
    """
    
    # Google Drive File ID
    file_id = '1t5b4OpduQkGVrONq_xEpaBwwFma7PS48'
    
    # Direct download URL for gdown
    url = f'https://drive.google.com/uc?id={file_id}'
    
    # Destination path relative to the script location
    output_path = 'app/services/L2CSNet_gaze360.pkl'
    
    # 1. Check if the model file already exists
    if os.path.exists(output_path):
        print(f"[INFO] Model file already exists at: {output_path}")
        print("[INFO] Skipping download.")
        return

    # 2. Ensure the directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    print(f"[INFO] Downloading L2CS-Net model weights to: {output_path}...")
    
    try:
        # 3. Download the file using gdown (handles Google Drive security tokens automatically)
        # quiet=False shows the progress bar
        # fuzzy=True helps extract the ID even if the URL format varies slightly
        gdown.download(url, output_path, quiet=False, fuzzy=True)
        print("\n[SUCCESS] Download complete!")
        
    except Exception as e:
        print(f"\n[ERROR] Failed to download model: {e}")

if __name__ == "__main__":
    setup_model()