import argparse
import requests
import pandas as pd
from datetime import datetime, timedelta
import subprocess
import os
import cv2
import numpy as np
import tempfile
import psutil
import time
import glob
import hashlib
import pickle
import json
import shutil

# Twitter API endpoint and headers
api_url = 'https://api.x.com/2/spaces'
headers = {
    'Authorization': 'Bearer YOUR_TWITTER_API_TOKEN'
}

def parse_arguments():
    parser = argparse.ArgumentParser(description="X-Recorder: Record and archive X Spaces")
    parser.add_argument("-t", "--timeframe", type=int, choices=[7, 14, 30, 90, 120], default=7,
                        help="Timeframe in days to search for recordings (default: 7)")
    parser.add_argument("-o", "--output", type=str, default='/mnt/e/AV/Capture/X-Recorder',
                        help="Output directory for saving recordings (default: /mnt/e/AV/Capture/X-Recorder)")
    parser.add_argument("-c", "--cookie", type=str, help="Full path to the X cookie file")
    parser.add_argument("-a", "--access-token", type=str, help="X (Twitter) API access token")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode for verbose output")
    parser.add_argument("-p", "--profile", type=str, help="X profile name(s) to search for spaces (comma-separated if multiple)")
    parser.add_argument("-s", "--space", type=str, help="Direct link to a specific X Space")
    return parser.parse_args()

def get_user_input(args):
    if not args.cookie:
        cookie_path = input("Enter the full path to the X cookie file: ")
    else:
        cookie_path = args.cookie
    return {'cookie_path': cookie_path}

def get_unique_output_path(base_path, base_name, ext):
    counter = 1
    output_path = f'{base_path}/{base_name}{ext}'
    while os.path.exists(output_path):
        output_path = f'{base_path}/{base_name}_{counter}{ext}'
        counter += 1
    return output_path

def check_tmp_for_existing_files(space_id):
    tmp_dir = '/tmp'
    files = glob.glob(f'{tmp_dir}/**/*{space_id}*.m4a', recursive=True) + glob.glob(f'{tmp_dir}/**/*{space_id}*.mp4', recursive=True)
    if files:
        print(f"Found existing file(s) for space ID {space_id}:")
        for file in files:
            print(f"  {file}")
    return files[0] if files else None

def download_space(space_url, output_path, cookie_path, debug):
    space_id = space_url.split('/')[-1]
    existing_file = check_tmp_for_existing_files(space_id)

    if existing_file:
        print(f"Found previously downloaded video at {existing_file}, using it for processing.")
        shutil.copy2(existing_file, output_path)
        return

    print(f"Video not found in /tmp, initiating download...")

    temp_file_path = f'/tmp/X-Space-{space_id}_temp.m4a'

    try:
        # Attempt to download the space using twspace-dl
        command = f'twspace-dl -c "{cookie_path}" -i "{space_url}" -o "{temp_file_path}"'
        if debug:
            print(f"Running command: {command}")
        
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        
        for line in process.stderr:
            if debug:
                print(line, end='')
            if "HTTP error 400 Bad Request" in line:
                if debug:
                    print("Detected HTTP 400 error. Switching to yt-dlp.")
                process.terminate()
                raise subprocess.CalledProcessError(1, command)
        
        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command)
        
        if debug:
            print(f"Successfully downloaded space to {temp_file_path}")
        
        # Copy the downloaded file to the output path
        shutil.copy2(temp_file_path, output_path)
        os.remove(temp_file_path)  # Remove the temporary file after copying
    except subprocess.CalledProcessError:
        try:
            # If twspace-dl fails, attempt to download the space using yt-dlp
            command = f'yt-dlp "{space_url}" --cookies "{cookie_path}" -o "{temp_file_path}"'
            if debug:
                print(f"Running command: {command}")
            subprocess.run(command, shell=True, check=True)
            if debug:
                print(f"Successfully downloaded space using yt-dlp to {temp_file_path}")
            
            # Copy the downloaded file to the output path
            shutil.copy2(temp_file_path, output_path)
            os.remove(temp_file_path)  # Remove the temporary file after copying
        except subprocess.CalledProcessError as e:
            print(f'Error downloading space: {e}')
            raise  # Re-raise the exception to be caught in the main function

def monitor_resources():
    cpu_usage = psutil.cpu_percent()
    mem_usage = psutil.virtual_memory().percent
    return cpu_usage, mem_usage

def detect_aspect_ratio_changes(video_path, threshold=0.1):
    cap = cv2.VideoCapture(video_path)
    aspect_ratios = []
    frame_count = 0
    prev_ratio = None
    orientation_change_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1
        height, width = frame.shape[:2]
        aspect_ratio = width / height
        
        if prev_ratio is None:
            prev_ratio = aspect_ratio
            aspect_ratios.append((frame_count, aspect_ratio))
        elif abs(aspect_ratio - prev_ratio) > threshold:
            # Check if orientation changed (portrait to landscape or vice versa)
            if (prev_ratio < 1 and aspect_ratio > 1) or (prev_ratio > 1 and aspect_ratio < 1):
                orientation_change_count += 1
                aspect_ratios.append((frame_count, aspect_ratio))
                prev_ratio = aspect_ratio
            # If not an orientation change, but still significant, record it
            elif abs(aspect_ratio - prev_ratio) > threshold * 2:
                aspect_ratios.append((frame_count, aspect_ratio))
                prev_ratio = aspect_ratio

    cap.release()
    print(f"Detected {orientation_change_count} orientation changes")
    return aspect_ratios

def split_video_segment(input_path, start_frame, end_frame, aspect_ratio):
    cap = cv2.VideoCapture(input_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    segment_frames = []
    for _ in range(end_frame - start_frame):
        ret, frame = cap.read()
        if not ret:
            break
        segment_frames.append(frame)
    
    cap.release()
    return (segment_frames, aspect_ratio)

def recombine_segments(segments, output_path):
    if not segments:
        return
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = None

    for segment_frames, aspect_ratio in segments:
        if not segment_frames:
            continue
        height, width = segment_frames[0].shape[:2]
        if out is None or out.get(cv2.CAP_PROP_FRAME_WIDTH) != width or out.get(cv2.CAP_PROP_FRAME_HEIGHT) != height:
            if out is not None:
                out.release()
            out = cv2.VideoWriter(output_path, fourcc, 30.0, (width, height))
        
        for frame in segment_frames:
            out.write(frame)

    if out is not None:
        out.release()

def save_checkpoint(segments, output_path):
    checkpoint_path = f"{os.path.splitext(output_path)[0]}_checkpoint.pkl"
    with open(checkpoint_path, 'wb') as f:
        pickle.dump(segments, f)

def load_checkpoint(output_path):
    checkpoint_path = f"{os.path.splitext(output_path)[0]}_checkpoint.pkl"
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, 'rb') as f:
            return pickle.load(f)
    return None

def process_video(input_path, output_path, debug):
    if not os.path.exists(input_path):
        print(f"Error: Input file not found: {input_path}")
        return

    try:
        checkpoint = load_checkpoint(output_path)
        if checkpoint:
            print("Resuming from checkpoint...")
            segments = checkpoint
        else:
            print("Detecting aspect ratio changes...")
            aspect_ratios = detect_aspect_ratio_changes(input_path)
            print(f"Detected {len(aspect_ratios)} aspect ratio changes")

            print("Splitting video into segments...")
            segments = []
            for i, (start, end) in enumerate(zip(aspect_ratios[:-1], aspect_ratios[1:])):
                cpu_usage, mem_usage = monitor_resources()
                if debug:
                    print(f"CPU Usage: {cpu_usage}% | RAM Usage: {mem_usage}%")
                if cpu_usage > 90 or mem_usage > 90:
                    print("High resource usage detected. Saving checkpoint and pausing...")
                    save_checkpoint(segments, output_path)
                    time.sleep(5)  # Wait for 5 seconds before continuing
                segment = split_video_segment(input_path, start[0], end[0], start[1])
                segments.append(segment)
                print(f"Processed segment {i+1}/{len(aspect_ratios)-1}")
                save_checkpoint(segments, output_path)

        print("Recombining segments...")
        recombine_segments(segments, output_path)
        print("Video processing complete!")
        
        checkpoint_path = f"{os.path.splitext(output_path)[0]}_checkpoint.pkl"
        if os.path.exists(checkpoint_path):
            os.remove(checkpoint_path)  # Remove checkpoint after successful processing
            print("Checkpoint file removed.")
        else:
            print("No checkpoint file found to remove.")
    except Exception as e:
        print(f"An error occurred during video processing: {str(e)}")

def get_space_creation_date(space_url, cookie_path):
    try:
        command = f'twspace-dl -c "{cookie_path}" -i "{space_url}" --print-json'
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, command)
        space_info = json.loads(result.stdout)
        created_at = space_info.get('created_at')
        if created_at:
            return datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d")
    except subprocess.CalledProcessError:
        print("Error: twspace-dl not found or failed. Using current date.")
    except json.JSONDecodeError:
        print("Error: Failed to parse twspace-dl output. Using current date.")
    except Exception as e:
        print(f"Error getting space creation date: {e}")
    return datetime.now().strftime("%Y-%m-%d")  # Fallback to current date if extraction fails

def main():
    args = parse_arguments()
    
    if not os.path.exists(args.output):
        os.makedirs(args.output)
    
    user_input = get_user_input(args)
    
    if args.space:
        space_url = args.space
        space_id = space_url.split('/')[-1]
        
        # Get the creation date from the space URL
        creation_date = get_space_creation_date(space_url, user_input['cookie_path'])
        
        base_name = f"{creation_date}-X-Space-#{space_id}"
        output_path = get_unique_output_path(args.output, base_name, ".m4a")
        
        print(f"Downloading X Space from: {space_url}")
        try:
            download_space(space_url, output_path, user_input['cookie_path'], args.debug)
            print("Download complete. Processing video...")
            processed_output_path = get_unique_output_path(args.output, base_name, "_processed.mp4")
            process_video(output_path, processed_output_path, args.debug)
            
            print(f"Original audio file saved to: {os.path.abspath(output_path)}")
            print(f"Processed video file saved to: {os.path.abspath(processed_output_path)}")
        except subprocess.CalledProcessError as e:
            print(f"Error occurred during download: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
    else:
        print("Please provide a direct space link using the -s option.")

if __name__ == "__main__":
    main()