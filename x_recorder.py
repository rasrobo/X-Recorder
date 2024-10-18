import argparse
import subprocess
import os
import glob
import json
import shutil
import re
import logging
from slugify import slugify
from datetime import datetime

DEFAULT_DOWNLOAD_DIR = '/mnt/e/AV/Capture/X-Recorder/'
TEMP_DIR = os.path.expanduser("~/Downloads")
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
    files = glob.glob(f'{TEMP_DIR}/*{space_id}*.*')
    if files:
        logging.info(f"Found existing file(s) for space ID {space_id}:")
        for file in files:
            logging.info(f"  {file}")
        return files[0]
    return None

def save_to_tmp(temp_file_path, output_path, space_id):
    try:
        if os.path.exists(temp_file_path):
            shutil.copy2(temp_file_path, output_path)
            os.remove(temp_file_path)
        else:
            files = glob.glob(f'{TEMP_DIR}/*{space_id}*.*')
            if files:
                logging.warning(f"File not found at the expected location. Found file(s) based on space ID: {files}")
                temp_file_path = files[0]
                shutil.copy2(temp_file_path, output_path)
                os.remove(temp_file_path)
            else:
                raise FileNotFoundError(f"Downloaded file not found for space ID: {space_id}")
    except FileNotFoundError as e:
        logging.error(f"Error saving file from {TEMP_DIR}: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error saving file from {TEMP_DIR}: {e}")
        raise

def download_space(space_url, output_path, cookie_path, debug, tool='auto'):
    space_id = space_url.split('/')[-1]
    existing_file = check_tmp_for_existing_files(space_id)

    if existing_file:
        logging.info(f"Found previously downloaded file at {existing_file}, using it for processing.")
        try:
            shutil.copy2(existing_file, output_path)
            logging.info(f"Successfully copied existing file to {output_path}")
            return False
        except IOError as e:
            logging.error(f"Error copying existing file: {e}")
            return False

    logging.info(f"No existing file found in {TEMP_DIR}, initiating download...")

    temp_file_path = f'{TEMP_DIR}/X-Space-{space_id}_temp.m4a'

    download_successful = False
    try:
        if tool == 'auto' or tool == 'twspace_dl':
            try:
                command = f'twspace_dl -c "{cookie_path}" -i "{space_url}" -o "{temp_file_path}"'
                if debug:
                    logging.debug(f"Running command: {command}")
                
                subprocess.run(command, shell=True, check=True)
                
                if debug:
                    logging.debug(f"Successfully downloaded space to {temp_file_path}")
                
                download_successful = True
            except subprocess.CalledProcessError:
                if tool == 'twspace_dl':
                    logging.error(f'Error downloading space with twspace_dl')
                    raise
                logging.warning("twspace_dl failed. Falling back to yt-dlp.")

        if (tool == 'auto' and not download_successful) or tool == 'yt-dlp':
            try:
                command = f'yt-dlp "{space_url}" --cookies "{cookie_path}" -o "{temp_file_path}"'
                if debug:
                    logging.debug(f"Running command: {command}")
                subprocess.run(command, shell=True, check=True)
                if debug:
                    logging.debug(f"Successfully downloaded space using yt-dlp to {temp_file_path}")
                
                download_successful = True
            except subprocess.CalledProcessError as e:
                logging.error(f'Error downloading space with yt-dlp: {e}')
                raise

        if download_successful:
            try:
                save_to_tmp(temp_file_path, output_path, space_id)
                return True
            except Exception as e:
                logging.error(f"Error saving downloaded file: {e}")
                return False
        else:
            logging.error("Download failed with all available methods.")
            return False
    except KeyboardInterrupt:
        logging.warning("Download interrupted by user.")
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise

def get_space_creation_date(file_path, specified_date=None):
    try:
        command = f'ffprobe -v quiet -print_format json -show_entries format_tags=creation_time -i "{file_path}"'
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)
        created_at = metadata.get('format', {}).get('tags', {}).get('creation_time')
        if created_at:
            return datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d")
        else:
            logging.warning(f"No creation_time found in metadata: {metadata}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running ffprobe: {e}")
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing ffprobe output: {e}")
    except Exception as e:
        logging.error(f"Error getting space creation date: {e}")
    
    if specified_date:
        try:
            return datetime.strptime(specified_date, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            logging.error(f"Invalid date format in specified date: {specified_date}")
    
    logging.warning("Using current date as fallback.")
    return datetime.now().strftime("%Y-%m-%d")

def extract_space_title(file_path):
    try:
        command = f'ffprobe -v quiet -print_format json -show_entries format_tags=title -i "{file_path}"'
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)
        title = metadata.get('format', {}).get('tags', {}).get('title')
        if title:
            return title
    except subprocess.CalledProcessError:
        logging.error("Error: ffprobe failed to extract title.")
    except json.JSONDecodeError:
        logging.error("Error: Failed to parse ffprobe output.")
    except Exception as e:
        logging.error(f"Error getting space title: {e}")
    return None

def convert_to_mp3(input_path, output_path):
    try:
        command = f'ffmpeg -i "{input_path}" -b:a 192k -map_metadata 0 "{output_path}"'
        subprocess.run(command, shell=True, check=True)
        logging.info(f"Successfully converted {input_path} to {output_path}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error converting to MP3: {e}")

def cleanup_temp_files():
    pattern = 'X-Space-*'
    try:
        files = glob.glob(os.path.join(TEMP_DIR, pattern))
        for file in files:
            try:
                os.remove(file)
                logging.info(f"Removed temporary file: {file}")
            except Exception as e:
                logging.warning(f"Failed to remove temporary file {file}: {e}")
    except Exception as e:
        logging.error(f"Error during cleanup: {e}")

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
            
            if os.path.exists(temp_output_path):
                creation_date = get_space_creation_date(temp_output_path, specified_date)
                space_title = extract_space_title(temp_output_path)
                
                if space_title:
                    slugified_title = slugify(space_title)
                    output_title = f"{creation_date}-{slugified_title}-X-Space-#{space_id}"
                else:
                    output_title = f"{creation_date}-X-Space-#{space_id}"
                
                final_output_path = get_unique_output_path(space_folder, output_title, ".m4a")
                
                try:
                    shutil.copy2(temp_output_path, final_output_path)
                    os.remove(temp_output_path)
                    logging.info(f"Successfully moved downloaded file to {final_output_path}")
                except IOError as e:
                    logging.error(f"Error moving file to final location: {e}")
                    try:
                        with open(temp_output_path, 'rb') as fsrc, open(final_output_path, 'wb') as fdst:
                            shutil.copyfileobj(fsrc, fdst)
                        os.remove(temp_output_path)
                        logging.info(f"Successfully copied file to final location with alternative method")
                    except IOError as e:
                        logging.error(f"Error copying file to final location with alternative method: {e}")
                        logging.info(f"File remains at temporary location: {temp_output_path}")
                        final_output_path = temp_output_path
                
                logging.info(f"Original audio file saved to: {os.path.abspath(final_output_path)}")
                
                # Convert M4A to MP3 and transfer metadata
                mp3_output_path = get_unique_output_path(space_folder, output_title, ".mp3")
                convert_to_mp3(final_output_path, mp3_output_path)
                
                # Delete the source M4A file
                os.remove(final_output_path)
                
                logging.info(f"MP3 file saved to: {os.path.abspath(mp3_output_path)}")
                
                # Cleanup only after successful download and conversion
                cleanup_temp_files()
                logging.info("Temporary files cleaned up.")
            else:
                logging.error(f"Downloaded file not found at expected location: {temp_output_path}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Error occurred during download: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
    else:
        logging.error("Please provide a direct space link using the -s option.")

    logging.info(f"Temporary files will be stored in: {TEMP_DIR}")

if __name__ == "__main__":
    main()