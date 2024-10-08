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
import re
import logging

DEFAULT_DOWNLOAD_DIR = '/mnt/e/AV/Capture/X-Recorder/'

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Twitter API endpoint and headers
api_url = 'https://api.x.com/2/spaces'
headers = {
    'Authorization': 'Bearer YOUR_TWITTER_API_TOKEN'
}

def parse_arguments():
    parser = argparse.ArgumentParser(description="X-Recorder: Record and archive X Spaces")
    parser.add_argument("-t", "--timeframe", type=int, choices=[7, 14, 30, 90, 120], default=7,
                        help="Timeframe in days to search for recordings (default: 7)")
    parser.add_argument("-o", "--output", type=str, default=DEFAULT_DOWNLOAD_DIR,
                        help=f"Output directory for saving recordings (default: {DEFAULT_DOWNLOAD_DIR})")
    parser.add_argument("-c", "--cookie", type=str, help="Full path to the X cookie file")
    parser.add_argument("-a", "--access-token", type=str, help="X (Twitter) API access token")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode for verbose output")
    parser.add_argument("-p", "--profile", type=str, help="X profile name(s) to search for spaces (comma-separated if multiple)")
    parser.add_argument("-s", "--space", type=str, help="Direct link to a specific X Space")
    parser.add_argument("--tool", type=str, choices=['auto', 'twspace_dl', 'yt-dlp'], default='auto',
                        help="Force a specific download tool (default: auto)")
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
        logging.info(f"Found existing file(s) for space ID {space_id}:")
        for file in files:
            logging.info(f"  {file}")
    return files[0] if files else None

def save_to_tmp(temp_file_path, output_path):
    try:
        if os.path.exists(temp_file_path):
            shutil.copy2(temp_file_path, output_path)
            os.remove(temp_file_path)
        else:
            raise FileNotFoundError(f"Downloaded file not found at {temp_file_path}")
    except FileNotFoundError as e:
        logging.error(f"Error saving file to /tmp: {e}")
        raise

def download_space(space_url, output_path, cookie_path, debug, tool='auto'):
    space_id = space_url.split('/')[-1]
    existing_file = check_tmp_for_existing_files(space_id)

    if existing_file:
        logging.info(f"Found previously downloaded video at {existing_file}, using it for processing.")
        shutil.copy2(existing_file, output_path)
        return False

    logging.info(f"Video not found in /tmp, initiating download...")

    temp_file_path = f'/tmp/X-Space-{space_id}_temp.m4a'

    if tool == 'auto' or tool == 'twspace_dl':
        try:
            command = f'twspace_dl -c "{cookie_path}" -i "{space_url}" -o "{temp_file_path}"'
            if debug:
                logging.debug(f"Running command: {command}")
            
            subprocess.run(command, shell=True, check=True)
            
            if debug:
                logging.debug(f"Successfully downloaded space to {temp_file_path}")
            
            save_to_tmp(temp_file_path, output_path)
            return False
        except subprocess.CalledProcessError:
            if tool == 'twspace_dl':
                logging.error(f'Error downloading space with twspace_dl')
                raise
            logging.warning("twspace_dl failed. Falling back to yt-dlp.")

    if tool == 'auto' or tool == 'yt-dlp':
        try:
            command = f'yt-dlp "{space_url}" --cookies "{cookie_path}" -o "{temp_file_path}"'
            if debug:
                logging.debug(f"Running command: {command}")
            subprocess.run(command, shell=True, check=True)
            if debug:
                logging.debug(f"Successfully downloaded space using yt-dlp to {temp_file_path}")
            
            save_to_tmp(temp_file_path, output_path)
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f'Error downloading space with yt-dlp: {e}')
            raise

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
            if (prev_ratio < 1 and aspect_ratio > 1) or (prev_ratio > 1 and aspect_ratio < 1):
                orientation_change_count += 1
                aspect_ratios.append((frame_count, aspect_ratio))
                prev_ratio = aspect_ratio
            elif abs(aspect_ratio - prev_ratio) > threshold * 2:
                aspect_ratios.append((frame_count, aspect_ratio))
                prev_ratio = aspect_ratio

    cap.release()
    logging.info(f"Detected {orientation_change_count} orientation changes")
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

def recombine_segments(segments, output_path, debug):
    if not segments:
        logging.warning("No segments to recombine.")
        return

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = None

    for i, (segment_frames, aspect_ratio) in enumerate(segments):
        if not segment_frames:
            logging.warning(f"Skipping empty segment {i}")
            continue
        height, width = segment_frames[0].shape[:2]
        if out is None or out.get(cv2.CAP_PROP_FRAME_WIDTH) != width or out.get(cv2.CAP_PROP_FRAME_HEIGHT) != height:
            if out is not None:
                out.release()
            out = cv2.VideoWriter(output_path, fourcc, 30.0, (width, height))
            if debug:
                logging.debug(f"Created new VideoWriter for segment {i} with dimensions {width}x{height}")
        
        for frame in segment_frames:
            out.write(frame)
        
        if debug:
            logging.debug(f"Processed segment {i} with {len(segment_frames)} frames")

    if out is not None:
        out.release()
        logging.info(f"Video saved to {output_path}")
    else:
        logging.error("Error: No video was written")

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
        logging.error(f"Error: Input file not found: {input_path}")
        return

    try:
        logging.info("Detecting aspect ratio changes...")
        aspect_ratios = detect_aspect_ratio_changes(input_path)
        logging.info(f"Detected {len(aspect_ratios)} aspect ratio changes")

        if len(aspect_ratios) == 1:
            logging.info("Only one aspect ratio detected. Copying the entire video.")
            shutil.copy2(input_path, output_path)
            logging.info(f"Video copied to {output_path}")
        else:
            logging.info("Splitting video into segments...")
            segments = []
            for i, (start, end) in enumerate(zip(aspect_ratios[:-1], aspect_ratios[1:])):
                segment = split_video_segment(input_path, start[0], end[0], start[1])
                segments.append(segment)
                logging.info(f"Processed segment {i+1}/{len(aspect_ratios)-1}")

            logging.info("Recombining segments...")
            recombine_segments(segments, output_path, debug)

        logging.info("Video processing complete!")
    except Exception as e:
        logging.error(f"An error occurred during video processing: {str(e)}")

def get_space_creation_date(file_path, specified_date=None):
    try:
        command = f'ffprobe -v quiet -print_format json -show_entries format_tags=creation_time -i "{file_path}"'
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)
        created_at = metadata.get('format', {}).get('tags', {}).get('creation_time')
        if created_at:
            return datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d")
    except subprocess.CalledProcessError:
        logging.error("Error: ffprobe failed to extract creation date.")
    except json.JSONDecodeError:
        logging.error("Error: Failed to parse ffprobe output.")
    except Exception as e:
        logging.error(f"Error getting space creation date: {e}")
    
    # If metadata extraction failed or date wasn't found, use specified date or current date
    if specified_date:
        try:
            return datetime.strptime(specified_date, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            logging.error(f"Invalid date format in specified date: {specified_date}")
    
    logging.warning("Using current date as fallback.")
    return datetime.now().strftime("%Y-%m-%d")

def main():
    args = parse_arguments()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    user_input = get_user_input(args)
    
    if args.space:
        space_url = args.space
        space_id = space_url.split('/')[-1]
        
        # Extract date from -o argument if provided
        specified_date = None
        if args.output:
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', args.output)
            if date_match:
                specified_date = date_match.group(1)
        
        # Create a subfolder for the space
        space_folder = os.path.join(args.output, space_id)
        os.makedirs(space_folder, exist_ok=True)
        
        temp_output_path = get_unique_output_path(space_folder, f"temp-X-Space-#{space_id}", ".m4a")
        
        logging.info(f"Downloading X Space from: {space_url}")
        try:
            is_video_space = download_space(space_url, temp_output_path, user_input['cookie_path'], args.debug, args.tool)
            logging.info("Download complete.")
            
            creation_date = get_space_creation_date(temp_output_path, specified_date)
            
            final_output_path = get_unique_output_path(space_folder, f"{creation_date}-X-Space-#{space_id}", ".m4a")
            os.rename(temp_output_path, final_output_path)
            
            if is_video_space:
                logging.info("Processing video...")
                processed_output_path = get_unique_output_path(space_folder, f"{creation_date}-X-Space-#{space_id}", "_processed.mp4")
                process_video(final_output_path, processed_output_path, args.debug)
            
            logging.info(f"Original audio file saved to: {os.path.abspath(final_output_path)}")
            
            if is_video_space:
                logging.info(f"Processed video file saved to: {os.path.abspath(processed_output_path)}")
                
                if os.path.exists(processed_output_path):
                    logging.info(f"Processed video file successfully created: {processed_output_path}")
                else:
                    logging.error(f"Error: Processed video file not found at {processed_output_path}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Error occurred during download: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
    else:
        logging.error("Please provide a direct space link using the -s option.")

if __name__ == "__main__":
    main()