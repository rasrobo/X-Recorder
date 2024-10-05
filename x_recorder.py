import argparse
import requests
import pandas as pd
from datetime import datetime, timedelta
import subprocess
import os

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

def generate_output_filename(space_id, title):
    current_date = datetime.now().strftime("%Y-%m-%d")
    formatted_title = title.replace(' ', '-')
    return f'{current_date}-{formatted_title}-#{space_id}'
import subprocess
import re

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
        
        # Generate a default title (you may want to fetch the actual title if possible)
        default_title = "𝕏-Space"
        
        # Generate the output filename
        output_filename = generate_output_filename(space_id, default_title)
        output_path = os.path.join(args.output, output_filename)
        
        download_space(space_url, output_path, user_input['cookie_path'], args.debug)
    else:
        print("Please provide a direct space link using the -s option.")

if __name__ == "__main__":
    main()