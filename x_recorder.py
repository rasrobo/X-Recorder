import argparse
import requests
import pandas as pd
from datetime import datetime, timedelta
import subprocess
import os
import cv2
import numpy as np

# Twitter API endpoint and headers
api_url = 'https://api.x.com/2/spaces'
headers = {
    'Authorization': 'Bearer YOUR_TWITTER_API_TOKEN'
}

def parse_arguments():
    parser = argparse.ArgumentParser(description="𝕏-Recorder: Record and archive 𝕏 Spaces")
    parser.add_argument("-t", "--timeframe", type=int, choices=[7, 14, 30, 90, 120], default=7,
                        help="Timeframe in days to search for recordings (default: 7)")
    parser.add_argument("-o", "--output", type=str, default=os.path.expanduser('~/Downloads/𝕏-Recorder'),
                        help="Output directory for saving recordings (default: ~/Downloads/𝕏-Recorder)")
    parser.add_argument("-c", "--cookie", type=str, help="Full path to the 𝕏 cookie file")
    parser.add_argument("-a", "--access-token", type=str, help="𝕏 (Twitter) API access token")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode for verbose output")
    parser.add_argument("-p", "--profile", type=str, help="𝕏 profile name(s) to search for spaces (comma-separated if multiple)")
    parser.add_argument("-s", "--space", type=str, help="Direct link to a specific 𝕏 Space")
    return parser.parse_args()

def get_user_input(args):
    if not args.cookie:
        cookie_path = input("Enter the full path to the 𝕏 cookie file: ")
    else:
        cookie_path = args.cookie

    return {'cookie_path': cookie_path}

def download_space(space_url, output_path, cookie_path, debug):
    try:
        # Attempt to download the space using twspace-dl
        command = f'twspace_dl -c "{cookie_path}" -i "{space_url}" -o "{output_path}.m4a"'
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
            print(f"Successfully downloaded space: {space_url}")
    except subprocess.CalledProcessError:
        try:
            # If twspace-dl fails, attempt to download the space using yt-dlp
            command = f'yt-dlp "{space_url}" --cookies "{cookie_path}" -o "{output_path}.%(ext)s"'
            if debug:
                print(f"Running command: {command}")
            subprocess.run(command, shell=True, check=True)
            if debug:
                print(f"Successfully downloaded space using yt-dlp: {space_url}")
        except subprocess.CalledProcessError as e:
            print(f'Error downloading space: {e}')
            raise  # Re-raise the exception to be caught in the main function

def detect_aspect_ratio_changes(video_path, threshold=0.01):
    cap = cv2.VideoCapture(video_path)
    aspect_ratios = []
    frame_count = 0
    prev_ratio = None

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1
        height, width = frame.shape[:2]
        aspect_ratio = width / height
        
        if prev_ratio is None or abs(aspect_ratio - prev_ratio) > threshold:
            aspect_ratios.append((frame_count, aspect_ratio))
            prev_ratio = aspect_ratio

    cap.release()
    return aspect_ratios

def split_video_by_aspect_ratio(video_path, aspect_ratios):
    cap = cv2.VideoCapture(video_path)
    segments = []
    current_segment_frames = []
    segment_index = 0
    frame_count = 0

    for next_change in aspect_ratios:
        while frame_count < next_change[0]:
            ret, frame = cap.read()
            if not ret:
                break
            current_segment_frames.append(frame)
            frame_count += 1
        
        if current_segment_frames:
            segments.append((segment_index, current_segment_frames, next_change[1]))
            segment_index += 1
            current_segment_frames = []

    # Add remaining frames to the last segment
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        current_segment_frames.append(frame)
    
    if current_segment_frames:
        segments.append((segment_index, current_segment_frames, aspect_ratios[-1][1]))

    cap.release()
    return segments

def recombine_segments(segments, output_path):
    if not segments:
        return
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = None

    for index, segment, aspect_ratio in segments:
        if not segment:
            continue
        height, width = segment[0].shape[:2]
        if out is None or out.get(cv2.CAP_PROP_FRAME_WIDTH) != width or out.get(cv2.CAP_PROP_FRAME_HEIGHT) != height:
            if out is not None:
                out.release()
            out = cv2.VideoWriter(output_path, fourcc, 30.0, (width, height))
        
        for frame in segment:
            out.write(frame)

    if out is not None:
        out.release()

def process_video(input_path, output_path):
    if not os.path.exists(input_path):
        print(f"Error: Input file not found: {input_path}")
        return

    print("Detecting aspect ratio changes...")
    aspect_ratios = detect_aspect_ratio_changes(input_path)
    print(f"Detected {len(aspect_ratios)} aspect ratio changes")

    print("Splitting video into segments...")
    segments = split_video_by_aspect_ratio(input_path, aspect_ratios)
    print(f"Split video into {len(segments)} segments")

    print("Recombining segments...")
    recombine_segments(segments, output_path)
    print("Video processing complete!")

def main():
    args = parse_arguments()
    
    # Create the output directory if it does not exist
    if not os.path.exists(args.output):
        os.makedirs(args.output)
    
    user_input = get_user_input(args)
    
    if args.space:
        # If a direct space link is provided, download the space immediately
        space_url = args.space
        space_id = space_url.split('/')[-1]
        
        # Generate the output filename
        output_filename = f"{datetime.now().strftime('%Y-%m-%d')}-X-Space-#{space_id}"
        output_path = os.path.join(args.output, output_filename)
        
        print(f"Downloading X Space from: {space_url}")
        try:
            download_space(space_url, output_path, user_input['cookie_path'], args.debug)
            print("Download complete. Processing video...")
            process_video(f"{output_path}.m4a", f"{output_path}_processed.mp4")
        except subprocess.CalledProcessError as e:
            print(f"Error occurred during download: {e}")
    else:
        print("Please provide a direct space link using the -s option.")

if __name__ == "__main__":
    main()