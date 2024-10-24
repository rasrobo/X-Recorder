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
    """Check for existing files and return the media file if found."""
    files = glob.glob(f'{TEMP_DIR}/*{space_id}*.*')
    if files:
        # First, look for complete media files
        media_files = [f for f in files if f.endswith('.m4a') and 
                      not f.endswith('.part') and 
                      not f.endswith('.info.json')]
        
        metadata_files = [f for f in files if f.endswith(('.json', '.m3u8'))]
        partial_files = [f for f in files if f.endswith('.part')]
        
        # Log what we found
        if media_files:
            selected_file = media_files[0]
            logging.info(f"Found existing media file: {selected_file}")
            return selected_file
        
        if metadata_files:
            logging.debug("Found metadata files but no complete media file:")
            for f in metadata_files:
                logging.debug(f"  {f}")
        
        # Clean up partial downloads
        for partial_file in partial_files:
            try:
                os.remove(partial_file)
                logging.debug(f"Removed incomplete download: {partial_file}")
            except Exception as e:
                logging.warning(f"Failed to remove incomplete download {partial_file}: {e}")
    
    return None

def download_space(space_url, cookie_path, debug):
    space_id = space_url.split('/')[-1]
    existing_file = check_tmp_for_existing_files(space_id)

    if existing_file and os.path.exists(existing_file) and not existing_file.endswith('.part'):
        logging.info(f"Found previously downloaded file at {existing_file}, using it for processing.")
        return existing_file, False

    logging.info(f"Initiating download...")
    temp_file_path = f'{TEMP_DIR}/X-Space-{space_id}_temp.m4a'

    try:
        # Download command with resume capability and fragment retries
        download_command = [
            'yt-dlp',
            '--cookies', cookie_path,
            '--write-info-json',
            '--continue',              # Enable download resumption
            '--no-part',               # Don't use .part files
            '--fragment-retries', 'infinite',  # Keep retrying failed fragments
            '--retries', 'infinite',          # Keep retrying on errors
            '--buffer-size', '16K',           # Smaller buffer size for more frequent saves
            '--hls-use-mpegts',              # Use MPEG-TS format for better compatibility
            '-o', temp_file_path,
            space_url
        ]
        
        if debug:
            logging.debug(f"Running download command: {' '.join(download_command)}")
        
        subprocess.run(download_command, check=True)
        
        if os.path.exists(temp_file_path):
            logging.info(f"Successfully downloaded space to {temp_file_path}")
            return temp_file_path, True
        
        logging.error("Download completed but file not found at expected location")
        return None, False
            
    except subprocess.CalledProcessError as e:
        logging.error(f'Error downloading space with yt-dlp: {e}')
        raise
    except KeyboardInterrupt:
        logging.warning("\nDownload interrupted by user.")
        logging.info("Progress saved. Run the same command to resume download.")
        raise
    except Exception as e:
        logging.error(f"Unexpected error during download: {str(e)}")
        raise

def extract_metadata(file_path):
    try:
        # First try to extract metadata using ffprobe
        command = f'ffprobe -v quiet -print_format json -show_entries format_tags -i "{file_path}"'
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)
        
        if not metadata or not metadata.get('format', {}).get('tags'):
            # If no metadata found, try extracting to a temporary file
            temp_metadata_file = os.path.join(TEMP_DIR, f"metadata_{os.path.basename(file_path)}.txt")
            extract_cmd = f'ffmpeg -i "{file_path}" -f ffmetadata "{temp_metadata_file}"'
            subprocess.run(extract_cmd, shell=True, check=True)
            
            # Read the metadata file
            with open(temp_metadata_file, 'r') as f:
                metadata_text = f.read()
            
            # Clean up
            os.remove(temp_metadata_file)
            
            # Convert the metadata text to a dictionary
            metadata = {'format': {'tags': {}}}
            for line in metadata_text.splitlines():
                if '=' in line:
                    key, value = line.split('=', 1)
                    metadata['format']['tags'][key.strip()] = value.strip()
        
        return metadata
    except subprocess.CalledProcessError:
        logging.error("Error: ffprobe/ffmpeg failed to extract metadata.")
    except json.JSONDecodeError:
        logging.error("Error: Failed to parse ffprobe output.")
    except Exception as e:
        logging.error(f"Error extracting metadata: {e}")
    return {'format': {'tags': {}}}

def add_metadata_to_m4a(file_path, title=None, date=None):
    try:
        temp_output = f"{os.path.splitext(file_path)[0]}_temp.m4a"
        command = [
            'ffmpeg',
            '-i', file_path,
            '-c', 'copy',
            '-metadata', f'title={title if title else ""}',
            '-metadata', f'date={date if date else ""}',
            temp_output
        ]
        
        if os.path.exists(temp_output):
            os.remove(temp_output)
            
        subprocess.run(command, check=True, capture_output=True, text=True)
        
        # Only replace the original file if the temporary file was created successfully
        if os.path.exists(temp_output):
            os.replace(temp_output, file_path)
            logging.info(f"Metadata added to {file_path}: title={title}, date={date}")
        else:
            logging.error("Failed to create temporary file for metadata addition")
            
    except subprocess.CalledProcessError as e:
        logging.error(f"Error adding metadata with ffmpeg: {e}")
        if e.stderr:
            logging.error(f"FFmpeg error output: {e.stderr}")
    except Exception as e:
        logging.error(f"Error adding metadata: {str(e)}")

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
    except subprocess.CalledProcessError as e:
        logging.error(f"Error converting to MP3: {e}")

def cleanup_temp_files(space_id=None, preserve_metadata=True, had_errors=False):
    """
    Clean up temporary files, preserving metadata files if there were errors.
    
    Args:
        space_id: If provided, only clean files for this space ID
        preserve_metadata: If True, preserve metadata and manifest files
        had_errors: If True, preserve all metadata files for debugging
    """
    pattern = f'X-Space-{space_id}*' if space_id else 'X-Space-*'
    try:
        files = glob.glob(os.path.join(TEMP_DIR, pattern))
        for file in files:
            try:
                # Skip files we want to preserve
                if had_errors or (preserve_metadata and any(x in file for x in [
                    '_metadata.json', 
                    '_manifest.m3u8', 
                    '.info.json',
                    '.ytdl'
                ])):
                    logging.debug(f"Preserving file for debugging: {file}")
                    continue
                    
                os.remove(file)
                logging.info(f"Removed temporary file: {file}")
            except Exception as e:
                logging.warning(f"Failed to remove temporary file {file}: {e}")
    except Exception as e:
        logging.error(f"Error during cleanup: {e}")

def sanitize_filename(title):
    """Make filename safe for all filesystems."""
    # Replace problematic characters
    safe_chars = " -._()[]{}#"
    filename = ''.join(c for c in title if c.isalnum() or c in safe_chars)
    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')
    # Collapse multiple spaces
    filename = ' '.join(filename.split())
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
    return filename

def main():
    logging.info(f"Temporary files will be stored in: {TEMP_DIR}")
    
    args = parse_arguments()
    success = False
    had_errors = False
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    user_input = get_user_input(args)
    
    if args.space:
        space_url = args.space
        space_id = space_url.split('/')[-1]
        
        try:
            # First, get metadata using yt-dlp
            metadata_command = [
                'yt-dlp',
                '--cookies', user_input['cookie_path'],
                '--dump-json',
                '--no-download',
                space_url
            ]
            
            try:
                metadata_result = subprocess.run(metadata_command, capture_output=True, text=True, check=True)
                space_info = json.loads(metadata_result.stdout)
                space_title = str(space_info.get('title', ''))
                space_date = space_info.get('upload_date', '')
                # Check if space has video streams
                is_video_space = any('video' in fmt.get('format', '').lower() 
                                   for fmt in space_info.get('formats', []))
                if args.debug:
                    logging.debug(f"Space metadata: title='{space_title}', date='{space_date}', is_video={is_video_space}")
            except Exception as e:
                logging.warning(f"Failed to get space metadata: {e}")
                space_title = None
                space_date = None
                is_video_space = False
                had_errors = True
            
            specified_date = None
            if args.output:
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', args.output)
                if date_match:
                    specified_date = date_match.group(1)
            
            space_folder = os.path.join(args.output, space_id)
            os.makedirs(space_folder, exist_ok=True)
            
            logging.info(f"Downloading X Space from: {space_url}")
            
            temp_file_path, is_new_download = download_space(space_url, user_input['cookie_path'], args.debug)
            
            if temp_file_path:
                if is_new_download:
                    logging.info("Download complete.")
                else:
                    logging.info("Using existing file, skipping download.")
                
                try:
                    # Use space metadata if available, otherwise fall back to specified date
                    if space_date:
                        try:
                            creation_date = datetime.strptime(space_date, "%Y%m%d").strftime("%Y-%m-%d")
                        except ValueError:
                            creation_date = get_space_creation_date(temp_file_path, specified_date)
                            had_errors = True
                    else:
                        creation_date = get_space_creation_date(temp_file_path, specified_date)

                    # Create title for metadata and filename
                    
                    # In main function, update the title processing section:
                    try:
                        if space_title:
                            title = str(space_title)
                            # Make filename safe without slugify
                            safe_title = sanitize_filename(title)
                            output_title = f"{creation_date}-{safe_title}-X-Space-#{space_id}"
                        else:
                            title = f"X Space #{space_id}"
                            output_title = f"{creation_date}-X-Space-#{space_id}"
                    except Exception as e:
                        logging.error(f"Error processing title: {e}")
                        title = f"X Space #{space_id}"
                        output_title = f"{creation_date}-X-Space-#{space_id}"
                        had_errors = True
                        
                    # Add metadata to the M4A file
                    add_metadata_to_m4a(temp_file_path, title=title, date=creation_date)
                    
                    final_output_path = get_unique_output_path(space_folder, output_title, ".m4a")
                    
                    try:
                        shutil.copy2(temp_file_path, final_output_path)
                        logging.info(f"Successfully copied file to {final_output_path}")
                        logging.info(f"Original audio file saved to: {os.path.abspath(final_output_path)}")
                        
                        # Convert to MP3 only if it's a video space
                        if is_video_space:
                            logging.info("Video space detected, converting to MP3...")
                            mp3_output_path = get_unique_output_path(space_folder, output_title, ".mp3")
                            convert_to_mp3(final_output_path, mp3_output_path)
                            logging.info(f"MP3 file saved to: {os.path.abspath(mp3_output_path)}")
                        else:
                            logging.info("Audio-only space detected, skipping MP3 conversion.")
                        
                        success = True and not had_errors
                        
                    except IOError as e:
                        logging.error(f"Error copying file to final location: {e}")
                        had_errors = True
                        raise
                except Exception as e:
                    logging.error(f"Error processing file: {e}")
                    had_errors = True
                    raise
            else:
                logging.error("Failed to download or locate the space file.")
                had_errors = True
                raise Exception("Failed to download or locate the space file.")
        
        except subprocess.CalledProcessError as e:
            logging.error(f"Error occurred during download: {e}")
            had_errors = True
        except Exception as e:
            logging.error(f"Failed to process the X Space: {str(e)}")
            had_errors = True
        finally:
            if success and not had_errors:
                if is_new_download:
                    os.remove(temp_file_path)
                    logging.info(f"Removed temporary file: {temp_file_path}")
                cleanup_temp_files(space_id=space_id, preserve_metadata=False)
                logging.info("All temporary files cleaned up.")
            else:
                logging.info("Keeping temporary files for debugging purposes.")
    
    else:
        logging.error("Please provide a direct space link using the -s option.")

if __name__ == "__main__":
    main()