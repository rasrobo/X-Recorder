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

def parse_arguments():
    parser = argparse.ArgumentParser(description="X-Recorder: Record and archive X Spaces")
    parser.add_argument("-o", "--output", type=str, default=DEFAULT_DOWNLOAD_DIR,
                        help=f"Output directory for saving recordings (default: {DEFAULT_DOWNLOAD_DIR})")
    parser.add_argument("-c", "--cookie", type=str, help="Full path to the X cookie file")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode for verbose output")
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
    files = glob.glob(f'{TEMP_DIR}/*{space_id}*.*')
    if files:
        logging.info(f"Found existing file(s) for space ID {space_id}:")
        for file in files:
            logging.info(f"  {file}")
        return files[0]
    return None

def download_space(space_url, cookie_path, debug):
    space_id = space_url.split('/')[-1]
    existing_file = check_tmp_for_existing_files(space_id)

    if existing_file:
        logging.info(f"Found previously downloaded file at {existing_file}, using it for processing.")
        return existing_file, False

    logging.info(f"No existing file found in {TEMP_DIR}, initiating download...")

    temp_file_path = f'{TEMP_DIR}/X-Space-{space_id}_temp.m4a'

    try:
        command = f'yt-dlp "{space_url}" --cookies "{cookie_path}" -o "{temp_file_path}"'
        if debug:
            logging.debug(f"Running command: {command}")
        subprocess.run(command, shell=True, check=True)
        
        if debug:
            logging.debug(f"Successfully downloaded space using yt-dlp to {temp_file_path}")
        
        return temp_file_path, True
    except subprocess.CalledProcessError as e:
        logging.error(f'Error downloading space with yt-dlp: {e}')
        raise
    except KeyboardInterrupt:
        logging.warning("Download interrupted by user.")
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise

def extract_metadata(file_path):
    try:
        command = f'ffprobe -v quiet -print_format json -show_entries format_tags=creation_time:title -i "{file_path}"'
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)
        
        if metadata:
            logging.debug(f"Extracted metadata for file {file_path}: {json.dumps(metadata, indent=2)}")
        else:
            logging.warning(f"No metadata found for file {file_path}")
        
        return metadata if metadata else {}
    except subprocess.CalledProcessError:
        logging.error("Error: ffprobe failed to extract metadata.")
    except json.JSONDecodeError:
        logging.error("Error: Failed to parse ffprobe output.")
    except Exception as e:
        logging.error(f"Error extracting metadata: {str(e)}")
    return {}

def add_metadata_to_m4a(file_path, title=None, date=None):
    try:
        logging.debug(f"Preparing to add metadata to file {file_path}: title={str(title)}, date={str(date)}")

        command = ['ffmpeg', '-i', file_path, '-c', 'copy', '-metadata', f'title={str(title)}', '-metadata', f'date={str(date)}', f'{file_path}.tmp']
        subprocess.run(command, check=True)

        if os.path.exists(f"{file_path}.tmp"):
            os.replace(f"{file_path}.tmp", file_path)

        logging.info(f"Metadata added to {file_path}: title={str(title)}, date={str(date)}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error adding metadata with ffmpeg: {str(e)}")

def get_space_creation_date(file_path, specified_date=None):
    metadata = extract_metadata(file_path)
    creation_date = (
        metadata.get('format', {}).get('tags', {}).get('creation_time') or
        metadata.get('format', {}).get('tags', {}).get('date') or
        metadata.get('streams', [{}])[0].get('tags', {}).get('creation_time')
    )
    
    if creation_date:
        try:
            return datetime.strptime(creation_date, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d")
        except ValueError:
            logging.warning(f"Invalid date format in metadata: {creation_date}")
    
    if specified_date:
        try:
            return datetime.strptime(specified_date, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            logging.error(f"Invalid date format in specified date: {specified_date}")
    
    logging.warning("Using current date as fallback.")
    return datetime.now().strftime("%Y-%m-%d")

def extract_space_title(file_path):
    metadata = extract_metadata(file_path)
    title = (
        metadata.get('format', {}).get('tags', {}).get('title') or
        metadata.get('format', {}).get('tags', {}).get('comment') or
        metadata.get('streams', [{}])[0].get('tags', {}).get('title')
    )
    
    if title:
        return title
    
    filename = os.path.splitext(os.path.basename(file_path))[0]
    return filename

def convert_to_mp3(input_path, output_path):
    try:
        command = f'ffmpeg -i "{input_path}" -b:a 192k -map_metadata 0 "{output_path}"'
        subprocess.run(command, shell=True, check=True)
        logging.info(f"Successfully converted {input_path} to {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error converting to MP3: {e}")
        return False

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
    logging.info(f"Temporary files will be stored in: {TEMP_DIR}")
    
    args = parse_arguments()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    user_input = get_user_input(args)
    
    if args.space:
        space_url = args.space
        space_id = space_url.split('/')[-1]
        
        specified_date = None
        if args.output:
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', args.output)
            if date_match:
                specified_date = date_match.group(1)
        
        space_folder = os.path.join(args.output, space_id)
        os.makedirs(space_folder, exist_ok=True)
        
        logging.info(f"Downloading X Space from: {space_url}")
        
        try:
            temp_file_path, is_new_download = download_space(space_url, user_input['cookie_path'], args.debug)
            
            if temp_file_path:
                if is_new_download:
                    logging.info("Download complete.")
                else:
                    logging.info("Using existing file, skipping download.")
                
                creation_date = get_space_creation_date(temp_file_path, specified_date)
                space_title = extract_space_title(temp_file_path)

                # Add extracted metadata back into the M4A file
                add_metadata_to_m4a(temp_file_path, title=space_title or "Unknown Title", date=creation_date)

                if space_title:
                    slugified_title = slugify(str(space_title))
                    output_title = f"{creation_date}-{slugified_title}-X-Space-#{space_id}"
                else:
                    output_title = f"{creation_date}-X-Space-#{space_id}"
                
                final_output_path = get_unique_output_path(space_folder, output_title, ".m4a")
                
                try:
                    shutil.copy2(temp_file_path, final_output_path)
                    logging.info(f"Successfully copied file to {final_output_path}")
                    
                    mp3_output_path = get_unique_output_path(space_folder, output_title, ".mp3")
                    if convert_to_mp3(final_output_path, mp3_output_path):
                        logging.info(f"MP3 file saved to: {os.path.abspath(mp3_output_path)}")

                    # Remove the temporary file only if the download was new and successful
                    if is_new_download:
                        os.remove(temp_file_path)
                        logging.info(f"Removed temporary file: {temp_file_path}")
                    
                    logging.info(f"Original audio file saved to: {os.path.abspath(final_output_path)}")

                except Exception as e:
                    logging.error(f"Error copying file to the final output path: {e}")
            else:
                logging.error("No file was downloaded or found for processing.")

        except Exception as e:
            logging.error(f"Failed to download or process the X Space: {e}")
    else:
        logging.error("No space URL provided. Use the -s or --space flag to specify a Space URL.")

    cleanup_temp_files()

if __name__ == "__main__":
    main()

