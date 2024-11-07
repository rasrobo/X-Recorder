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

def analyze_space_metrics(metadata_path):
    """Extract and log viewer metrics from space metadata."""
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        metrics = {
            'concurrent_viewers': metadata.get('concurrent_viewers', 0),
            'total_viewers': metadata.get('total_viewers', 0),
            'live_viewers': metadata.get('live_viewers', 0),
            'replay_viewers': metadata.get('replay_viewers', 0),
            'participants': len(metadata.get('participants', [])),
            'duration': metadata.get('duration', 0),
            'started_at': metadata.get('started_at', ''),
            'ended_at': metadata.get('ended_at', '')
        }

        logging.info("Space Metrics:")
        for key, value in metrics.items():
            if value:
                if key == 'duration':
                    logging.info(f"Duration: {value / 60:.1f} minutes")
                elif key in ['started_at', 'ended_at']:
                    logging.info(f"{key.replace('_', ' ').title()}: {value}")
                else:
                    logging.info(f"{key.replace('_', ' ').title()}: {value}")

        return metrics
    except Exception as e:
        logging.error(f"Error analyzing space metrics: {e}")
        return None

def verify_download(file_path, expected_duration=None):
    """Verify downloaded file integrity and duration."""
    try:
        command = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)

        duration = float(info.get('format', {}).get('duration', 0))
        if duration < 60:
            logging.warning(f"File duration suspiciously short: {duration} seconds")
            return False

        if expected_duration and abs(duration - expected_duration) > 300:
            logging.warning(f"Duration mismatch: got {duration / 60:.1f}min, expected {expected_duration / 60:.1f}min")
            return False

        return True
    except Exception as e:
        logging.error(f"Error verifying download: {e}")
        return False

def parse_arguments():
    parser = argparse.ArgumentParser(description="X-Recorder: Record and archive X Spaces")
    parser.add_argument("-o", "--output", type=str, default=DEFAULT_DOWNLOAD_DIR,
                        help=f"Output directory for saving recordings (default: {DEFAULT_DOWNLOAD_DIR})")
    parser.add_argument("-oc", "--output-copy", type=str,
                        help="Additional directory to copy the recordings to")
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
                logging.warning(f"Failed to remove incomplete download {partial_file}: {e}")
    
    return None

def download_space(space_url, cookie_path, debug):
    """Download X Space with improved error handling and verification."""
    space_id = space_url.split('/')[-1]
    existing_file = check_tmp_for_existing_files(space_id)

    if existing_file and os.path.exists(existing_file) and not existing_file.endswith('.part'):
        logging.info(f"Found previously downloaded file at {existing_file}, using it for processing.")
        return existing_file, False

    logging.info(f"Initiating download...")
    temp_file_path = f'{TEMP_DIR}/X-Space-{space_id}_temp.m4a'

    try:
        # Download command with essential options
        download_command = [
            'yt-dlp',
            '--cookies', cookie_path,
            '--write-info-json',
            '--continue',  # Enable download resumption
            '--no-part',  # Don't use .part files
            '--fragment-retries', 'infinite',  # Keep retrying failed fragments
            '--retries', 'infinite',  # Keep retrying on errors
            '--extractor-args', 'twitter:max_retries=3',  # Twitter-specific retries
            '-o', temp_file_path,
            space_url
        ]

        if debug:
            logging.debug(f"Running download command: {' '.join(download_command)}")

        subprocess.run(download_command, check=True)

        if os.path.exists(temp_file_path):
            # Verify the download
            if verify_download(temp_file_path):
                logging.info(f"Successfully downloaded and verified space to {temp_file_path}")
                return temp_file_path, True
            else:
                logging.error("Download verification failed")
                return None, False

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

def verify_space_duration(file_path, expected_duration=None):
    """Verify the downloaded file duration matches expected length."""
    try:
        command = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            file_path
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        
        actual_duration = float(info.get('format', {}).get('duration', 0))
        actual_minutes = actual_duration / 60
        
        if expected_duration:
            expected_minutes = expected_duration / 60
            if abs(actual_minutes - expected_minutes) > 5:  # 5 minute tolerance
                logging.warning(f"Duration mismatch: got {actual_minutes:.1f} minutes, "
                              f"expected {expected_minutes:.1f} minutes")
                return False
        
        logging.info(f"File duration: {actual_minutes:.1f} minutes")
        
        # Basic sanity check - file should be longer than 1 minute
        if actual_minutes < 1:
            logging.warning("File duration suspiciously short")
            return False
            
        return True
    except Exception as e:
        logging.error(f"Error verifying duration: {e}")
        return False

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

def convert_to_mp3(input_path, output_path, title=None, date=None):
    """Convert to MP3 and add metadata."""
    try:
        command = [
            'ffmpeg',
            '-i', input_path,
            '-b:a', '192k',
            '-map_metadata', '0'
        ]
        
        # Add metadata if provided
        if title:
            command.extend(['-metadata', f'title={title}'])
        if date:
            command.extend(['-metadata', f'date={date}'])
            
        command.append(output_path)
        
        subprocess.run(command, check=True)
        logging.info(f"Successfully converted to MP3: {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error converting to MP3: {e}")
        return False

def is_video_space(formats):
    """Improved video space detection."""
    for fmt in formats:
        if any([
            fmt.get('vcodec', 'none').lower() not in ['none', 'n/a'],
            fmt.get('width', 0) > 0 and fmt.get('height', 0) > 0,
            fmt.get('fps', 0) > 0,
            'video' in fmt.get('format_note', '').lower(),
            fmt.get('acodec', '') == 'none',
            'video only' in fmt.get('format', '').lower()
        ]):
            return True
    return False


def cleanup_temp_files(space_id=None, preserve_metadata=True, had_errors=False):
    """Clean up temporary files with better error handling."""
    pattern = f'X-Space-{space_id}*' if space_id else 'X-Space-*'
    preserved_extensions = ['.json', '.m3u8', '.info.json', '.m4a'] if had_errors else ['.json', '.info.json']

    try:
        files = glob.glob(os.path.join(TEMP_DIR, pattern))
        for file in files:
            try:
                if preserve_metadata and any(file.endswith(ext) for ext in preserved_extensions):
                    logging.debug(f"Preserving file: {file}")
                    continue

                os.remove(file)
                logging.info(f"Removed temporary file: {file}")
            except Exception as e:
                logging.warning(f"Failed to remove temporary file {file}: {e}")
    except Exception as e:
        logging.error(f"Error during cleanup: {e}")


@dataclass
class Config:
    """Configuration settings for X-Recorder."""
    DEFAULT_DOWNLOAD_DIR: str = '/mnt/e/AV/Capture/X-Recorder/'
    TEMP_DIR: str = os.path.expanduser("~/Downloads")
    VALID_AUDIO_EXTENSIONS: tuple = ('.m4a', '.mp3')
    MAX_FILENAME_LENGTH: int = 255
    METADATA_EXTENSIONS: tuple = ('.json', '.m3u8', '.info.json', '.ytdl')


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

def cleanup_destination_duplicates(space_folder, space_id):
    """Clean up duplicate files in destination folder, keeping the most informative one."""
    try:
        # Get all m4a files for this space
        files = glob.glob(os.path.join(space_folder, f'*-X-Space-#{space_id}*.m4a'))
        if len(files) <= 1:
            return

        # Sort files by name length (longer names typically have more info)
        # and then by modification time (newer first)
        files.sort(key=lambda x: (-len(os.path.basename(x)), -os.path.getmtime(x)))

        # Keep the first file (most informative/newest) and remove others
        keep_file = files[0]
        for file in files[1:]:
            try:
                os.remove(file)
                logging.info(f"Removed duplicate file: {file}")
            except Exception as e:
                logging.warning(f"Failed to remove duplicate file {file}: {e}")

        logging.info(f"Kept most informative file: {keep_file}")

    except Exception as e:
        logging.error(f"Error cleaning up destination duplicates: {e}")

def copy_to_additional_location(source_file, output_copy_dir, space_id):
    """Copy the file to an additional location."""
    try:
        # Create the space folder in the copy location
        copy_space_folder = os.path.join(output_copy_dir, space_id)
        os.makedirs(copy_space_folder, exist_ok=True)
        
        # Get the filename without the path
        filename = os.path.basename(source_file)
        copy_path = os.path.join(copy_space_folder, filename)
        
        # Copy the file
        shutil.copy2(source_file, copy_path)
        logging.info(f"Successfully copied file to additional location: {copy_path}")
        return True
    except Exception as e:
        logging.error(f"Error copying to additional location: {e}")
        return False

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
                expected_duration = float(space_info.get('duration', 0))
                
                # Save metadata JSON for future reference
                metadata_path = f'{TEMP_DIR}/X-Space-{space_id}_metadata.json'
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(space_info, f, indent=2, ensure_ascii=False)
                
                # Improved video space detection
                formats = space_info.get('formats', [])
                is_video_space = False
                
                # Check multiple indicators for video content
                for fmt in formats:
                    if any([
                        fmt.get('vcodec', 'none').lower() not in ['none', 'n/a'],
                        'video' in fmt.get('format_note', '').lower(),
                        fmt.get('width', 0) > 0,
                        fmt.get('height', 0) > 0,
                        fmt.get('fps', 0) > 0,
                        fmt.get('acodec', '') == 'none',  # Video-only stream
                        'video only' in fmt.get('format', '').lower()
                    ]):
                        is_video_space = True
                        break
                
                if args.debug:
                    logging.debug(f"Space metadata: title='{space_title}', date='{space_date}', "
                                f"is_video={is_video_space}, duration={expected_duration/60:.1f}min")
                    if formats:
                        logging.debug("Available formats:")
                        for fmt in formats:
                            logging.debug(f"Format: {fmt}")
                
                if expected_duration > 0:
                    logging.info(f"Expected space duration: {expected_duration/60:.1f} minutes")
                
            except Exception as e:
                logging.warning(f"Failed to get space metadata: {e}")
                space_title = None
                space_date = None
                is_video_space = False
                expected_duration = 0
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
                    logging.info("Download complete, verifying...")
                    # Verify downloaded file duration
                    try:
                        probe_cmd = [
                            'ffprobe',
                            '-v', 'quiet',
                            '-print_format', 'json',
                            '-show_format',
                            temp_file_path
                        ]
                        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
                        file_info = json.loads(probe_result.stdout)
                        actual_duration = float(file_info.get('format', {}).get('duration', 0))
                        
                        if expected_duration > 0 and abs(actual_duration - expected_duration) > 300:  # 5 min tolerance
                            logging.warning(f"Duration mismatch: expected {expected_duration/60:.1f}min, "
                                          f"got {actual_duration/60:.1f}min")
                            had_errors = True
                        else:
                            logging.info(f"File duration verified: {actual_duration/60:.1f}min")
                    except Exception as e:
                        logging.error(f"Error verifying file duration: {e}")
                        had_errors = True
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
                    try:
                        if space_title:
                            title = str(space_title)
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
                            logging.info("Audio-only space detected, keeping M4A format")
                        
                        # Copy metadata files to destination
                        metadata_files = glob.glob(os.path.join(TEMP_DIR, f'X-Space-{space_id}*.*'))
                        for metadata_file in metadata_files:
                            if any(x in metadata_file for x in ['_metadata.json', '.info.json']):
                                dest_metadata = os.path.join(space_folder, os.path.basename(metadata_file))
                                shutil.copy2(metadata_file, dest_metadata)
                                logging.debug(f"Copied metadata file to: {dest_metadata}")
                        
                        # Clean up duplicate files in destination
                        cleanup_destination_duplicates

if __name__ == "__main__":
    main()