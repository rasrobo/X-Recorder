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
    parser = argparse.ArgumentParser(description="X-Recorder: Record and archive X Spaces")
    parser.add_argument("-t", "--timeframe", type=int, choices=[7, 14, 30, 90, 120], default=7,
                        help="Timeframe in days to search for recordings (default: 7)")
    parser.add_argument("-o", "--output", type=str, default=os.path.expanduser('~/Downloads/X-Recorder'),
                        help="Output directory for saving recordings (default: ~/Downloads/X-Recorder)")
    parser.add_argument("-c", "--cookie", type=str, help="Full path to the X cookie file")
    parser.add_argument("-a", "--access-token", type=str, help="X (Twitter) API access token")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode for verbose output (API connections, commands, and downloads)")
    parser.add_argument("-p", "--profile", type=str, help="X profile name(s) to search for spaces (comma-separated if multiple)")
    parser.add_argument("-s", "--space", type=str, help="Direct link to a specific X Space")
    return parser.parse_args()

def get_user_input(args):
    if not args.cookie:
        cookie_path = input("Enter the full path to the X cookie file: ")
    else:
        cookie_path = args.cookie

    if args.space:
        user_input = args.space
    elif args.profile:
        user_input = args.profile
    else:
        user_input = input("Enter profile names or a direct space link: ")

    return {'input': user_input, 'cookie_path': cookie_path}

def get_space_recordings(user_input, timeframe, debug):
    recordings = []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=timeframe)

    # Check if input is a link or a profile
    if user_input['input'].startswith('https://x.com/i/spaces/'):
        space_link = user_input['input']
        space_id = space_link.split('/')[-1]
        recordings.append({
            'title': f"Space {space_id}",
            'space_url': space_link
        })
    else:
        profiles = user_input['input'].split(',')
        for profile in profiles:
            params = {
                'user.fields': 'id,username',
                'expansions': 'host_ids',
                'space.fields': 'title,started_at,state,host_ids,id,type',
                'start_time': start_date.isoformat(),
                'end_time': end_date.isoformat()
            }
            response = requests.get(api_url, headers=headers, params=params)
            if response.status_code == 200:
                if debug:
                    print(f"Successfully connected to the API for profile: {profile}")
                spaces_data = response.json()
                users_data = {user['id']: user['username'] for user in spaces_data.get('includes', {}).get('users', [])}
                for space in spaces_data.get('data', []):
                    if any(host_id == profile for host_id in space.get('host_ids', [])):
                        space_type = space.get('type', 'unknown')
                        if debug and space_type == 'video':
                            print(f"Video space detected for profile: {profile}")
                        recordings.append({
                            'title': space['title'],
                            'started_at': space['started_at'],
                            'state': space['state'],
                            'space_url': f'https://x.com/i/spaces/{space["id"]}',
                            'type': space_type
                        })
            else:
                if debug:
                    print(f"Failed to connect to the API for profile: {profile}")
                    print(f"API response status code: {response.status_code}")
                    print(f"API response content: {response.text}")
                print(f"No recordings found for the profile '{profile}' in the past {timeframe} days.")
    return recordings

def download_space(space_url, output_path, cookie_path, debug):
    try:
        # Attempt to download the space using twspace_dl
        command = f'twspace_dl -c "{cookie_path}" -i "{space_url}" -o "{output_path}.m4a"'
        if debug:
            print(f"Running command: {command}")
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        for line in process.stderr:
            if debug:
                print(line, end='')
            if "Cannot get correct #EXTINF value of segment" in line:
                if debug:
                    print("Detected 'Cannot get correct #EXTINF value of segment' error. Failing over to yt-dlp.")
                process.terminate()  # Terminate the twspace_dl process
                raise subprocess.CalledProcessError(1, command)  # Raise an exception to trigger the failover
        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command)
        if debug:
            print(f"Successfully downloaded audio space: {space_url}")
    except subprocess.CalledProcessError:
        if debug:
            print(f"twspace_dl failed to download the space. Attempting to download using yt-dlp.")
        try:
            # If twspace_dl fails, attempt to download the space using yt-dlp
            command = f'yt-dlp "{space_url}" --cookies "{cookie_path}" -o "{output_path}.%(ext)s"'
            if debug:
                print(f"Running command: {command}")
            subprocess.run(command, shell=True, check=True)
            if debug:
                print(f"Successfully downloaded video space: {space_url}")
        except subprocess.CalledProcessError as e:
            print(f'Error downloading space: {e}')

def main():
    args = parse_arguments()
    
    # Create the output directory if it does not exist
    if not os.path.exists(args.output):
        os.makedirs(args.output)
    
    # Update the headers with the provided API access token
    if args.access_token:
        headers['Authorization'] = f'Bearer {args.access_token}'
    
    user_input = get_user_input(args)
    recordings = get_space_recordings(user_input, args.timeframe, args.debug)
    
    if args.space:
        # If a direct space link is provided, download the space immediately
        space_url = args.space
        output_path = os.path.join(args.output, f"Space {space_url.split('/')[-1]}")
        download_space(space_url, output_path, user_input['cookie_path'], args.debug)
    else:
        # If profile(s) are provided, display available spaces and prompt for download
        if not recordings:
            print("No recordings found.")
        else:
            print("Available spaces for the specified timeframe:")
            for idx, record in enumerate(recordings, start=1):
                print(f"{idx}: {record['title']} (URL: {record['space_url']})")
            
            print("The following recordings are available:")
            for i, record in enumerate(recordings, 1):
                print(f"{i}. Title: {record['title']}, Status: {record['state']}, URL: {record['space_url']}")
            
            choice = input("Do you want to download all available spaces or enter the number for specific space(s) (comma-separated if multiple)? (Press Enter to continue with all): ").strip().lower()
            if choice:
                specific_indices = [int(x) - 1 for x in choice.split(',') if x.isdigit()]
                spaces_to_download = [recordings[i] for i in specific_indices if 0 <= i < len(recordings)]
            else:
                spaces_to_download = recordings
            
            for record in spaces_to_download:
                output_path = os.path.join(args.output, record['title'])
                download_space(record['space_url'], output_path, user_input['cookie_path'], args.debug)

if __name__ == "__main__":
    main()