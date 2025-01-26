import argparse
import subprocess
import os
import sys
import glob
import json
import shutil
import re
import logging
from datetime import datetime
from dataclasses import dataclass
import requests
import subprocess
import math
from dotenv import load_dotenv
import os

load_dotenv()

TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_OAUTH_TOKEN = os.getenv('TWITCH_OAUTH_TOKEN')



# Configuration
DEFAULT_DOWNLOAD_DIR = '/mnt/e/AV/Capture/X-Recorder/'
TEMP_DIR = os.path.expanduser("~/Downloads")

# Logging Setup
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

@dataclass
class Config:
    """Configuration settings for X-Recorder."""
    DEFAULT_DOWNLOAD_DIR: str = DEFAULT_DOWNLOAD_DIR
    TEMP_DIR: str = TEMP_DIR
    VALID_AUDIO_EXTENSIONS: tuple = ('.m4a', '.mp3')
    MAX_FILENAME_LENGTH: int = 255
    METADATA_EXTENSIONS: tuple = ('.json', '.m3u8', '.info.json', '.ytdl')
    DURATION_TOLERANCE_MINUTES: int = 5

def extract_metadata(file_path):
    """Extract metadata from media file using ffprobe."""
    try:
        command = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_entries', 'format_tags',
            file_path
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)
        
        if not metadata or not metadata.get('format', {}).get('tags'):
            # If no metadata found, try extracting to a temporary file
            temp_metadata_file = os.path.join(TEMP_DIR, f"metadata_{os.path.basename(file_path)}.txt")
            extract_cmd = [
                'ffmpeg',
                '-i', file_path,
                '-f', 'ffmetadata',
                temp_metadata_file
            ]
            subprocess.run(extract_cmd, capture_output=True, text=True, check=True)
            
            # Read the metadata file
            with open(temp_metadata_file, 'r', encoding='utf-8') as f:
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
        logging.error("Error: ffprobe/ffmpeg failed to extract metadata")
    except json.JSONDecodeError:
        logging.error("Error: Failed to parse ffprobe output")
    except Exception as e:
        logging.error(f"Error extracting metadata: {e}")
    
    return {'format': {'tags': {}}}

def split_audio_file(input_file, output_folder, max_duration=7200):  # 7200 seconds = 2 hours
    try:
        # Get the total duration of the input file
        total_duration = get_audio_duration(input_file)
        
        # Calculate the number of chunks needed
        num_chunks = math.ceil(total_duration / max_duration)
        
        if num_chunks == 1:
            logging.info("File duration is less than 2 hours. No splitting required.")
            return [input_file]
        
        output_files = []
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        for i in range(num_chunks):
            start_time = i * max_duration
            output_title = f"{base_name}_part{i+1}"
            output_file = get_unique_output_path(output_folder, output_title, ".m4a")
            
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', input_file,
                '-ss', str(start_time),
                '-t', str(max_duration),
                '-c', 'copy',
                '-y',  # Overwrite output files without asking
                output_file
            ]
            
            subprocess.run(ffmpeg_cmd, check=True)
            output_files.append(output_file)
            logging.info(f"Created split file: {output_file}")
        
        return output_files
    except Exception as e:
        logging.error(f"Error splitting audio file: {str(e)}")
        return [input_file]  # Return the original file if splitting fails

def sanitize_filename(title):
    """Make filename safe for all filesystems."""
    safe_chars = " -._()[]{}#"
    filename = ''.join(c for c in title if c.isalnum() or c in safe_chars)
    filename = filename.strip('. ')
    filename = ' '.join(filename.split())
    return filename[:Config.MAX_FILENAME_LENGTH]

def analyze_space_metrics(metadata_path):
    """Extract and log comprehensive viewer metrics from space metadata."""
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        metrics = {
            'title': metadata.get('title', ''),
            'state': metadata.get('state', ''),
            'concurrent_viewers': metadata.get('concurrent_viewers', 0),
            'total_viewers': metadata.get('total_viewers', 0),
            'live_viewers': metadata.get('live_viewers', 0),
            'replay_viewers': metadata.get('replay_viewers', 0),
            'participants': len(metadata.get('participants', [])),
            'duration': metadata.get('duration', 0),
            'started_at': metadata.get('started_at', ''),
            'ended_at': metadata.get('ended_at', ''),
            'available_for_replay': metadata.get('available_for_replay', False),
            'language': metadata.get('language', ''),
            'creator': metadata.get('creator', {}).get('name', ''),
            'creator_followers': metadata.get('creator', {}).get('followers_count', 0),
            'description': metadata.get('description', ''),
            'scheduled_start': metadata.get('scheduled_start', ''),
            'recording_status': metadata.get('recording_status', ''),
            'participant_count': len(metadata.get('participants', [])),
            'likes': metadata.get('like_count', 0),
            'retweets': metadata.get('retweet_count', 0)
        }
        
        logging.info("\nSpace Metrics:")
        logging.info("=" * 50)
        
        # Title and Creator Info
        if metrics['title']:
            logging.info(f"Title: {metrics['title']}")
        if metrics['creator']:
            logging.info(f"Creator: {metrics['creator']} (Followers: {metrics['creator_followers']:,})")
        
        # Time Information
        if metrics['started_at'] and metrics['ended_at']:
            start_time = datetime.strptime(metrics['started_at'], "%Y-%m-%dT%H:%M:%S.%fZ")
            end_time = datetime.strptime(metrics['ended_at'], "%Y-%m-%dT%H:%M:%S.%fZ")
            duration_mins = (end_time - start_time).total_seconds() / 60
            logging.info(f"\nTiming:")
            logging.info(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logging.info(f"Ended: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logging.info(f"Duration: {duration_mins:.1f} minutes")
        elif metrics['duration']:
            logging.info(f"\nDuration: {metrics['duration']/60:.1f} minutes")
        
        # Viewer Statistics
        logging.info("\nViewer Statistics:")
        if metrics['concurrent_viewers']:
            logging.info(f"Peak Concurrent Viewers: {metrics['concurrent_viewers']:,}")
        if metrics['total_viewers']:
            logging.info(f"Total Viewers: {metrics['total_viewers']:,}")
        if metrics['live_viewers']:
            logging.info(f"Live Viewers: {metrics['live_viewers']:,}")
        if metrics['replay_viewers']:
            logging.info(f"Replay Viewers: {metrics['replay_viewers']:,}")
            
        # Engagement Metrics
        logging.info("\nEngagement:")
        if metrics['participant_count']:
            logging.info(f"Total Participants: {metrics['participant_count']:,}")
        if metrics['likes']:
            logging.info(f"Likes: {metrics['likes']:,}")
        if metrics['retweets']:
            logging.info(f"Retweets: {metrics['retweets']:,}")
            
        # Additional Information
        logging.info("\nAdditional Information:")
        if metrics['language']:
            logging.info(f"Language: {metrics['language']}")
        if metrics['state']:
            logging.info(f"State: {metrics['state']}")
        if metrics['recording_status']:
            logging.info(f"Recording Status: {metrics['recording_status']}")
        if metrics['available_for_replay']:
            logging.info("Available for Replay: Yes")
        if metrics['description']:
            logging.info(f"\nDescription: {metrics['description']}")
            
        logging.info("=" * 50)
        return metrics
    except Exception as e:
        logging.error(f"Error analyzing space metrics: {e}")
        return None

def get_file_size_mb(file_path):
    """Get file size in megabytes."""
    return os.path.getsize(file_path) / (1024 * 1024)

def is_video_space(formats):
    """Improved video space detection."""
    if not formats:
        return False
        
    video_space = False
    for fmt in formats:
        if any([
            fmt.get('vcodec', 'none').lower() not in ['none', 'n/a'],
            fmt.get('width', 0) > 0 and fmt.get('height', 0) > 0,
            fmt.get('fps', 0) > 0,
            'video' in fmt.get('format_note', '').lower(),
            fmt.get('acodec', '') == 'none',
            'video only' in fmt.get('format', '').lower()
        ]):
            video_space = True
            logging.info(f"Detected video indicators in format: {fmt.get('format', '')}")
            break
    
    if not video_space:
        logging.info("No video indicators found in formats")
    return video_space

def get_space_creation_date(file_path, specified_date=None):
    """Get the creation date from file metadata or specified date."""
    try:
        # First try to get date from ffprobe
        command = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_entries', 'format_tags',
            file_path
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)
        
        # Try different date formats
        creation_date = (
            metadata.get('format', {}).get('tags', {}).get('creation_time') or
            metadata.get('format', {}).get('tags', {}).get('date') or
            metadata.get('streams', [{}])[0].get('tags', {}).get('creation_time')
        )
        
        if creation_date:
            for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d", "%Y%m%d"]:
                try:
                    return datetime.strptime(creation_date, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
            
        if specified_date:
            try:
                return datetime.strptime(specified_date, "%Y-%m-%d").strftime("%Y-%m-%d")
            except ValueError:
                logging.error(f"Invalid specified date format: {specified_date}")
        
        logging.warning("Using current date as fallback")
        return datetime.now().strftime("%Y-%m-%d")
        
    except Exception as e:
        logging.error(f"Error getting creation date: {e}")
        return datetime.now().strftime("%Y-%m-%d")

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
            logging.warning(f"File duration suspiciously short: {duration/60:.1f} minutes")
            return False
            
        if expected_duration and abs(duration - expected_duration) > 300:  # 5 min tolerance
            logging.warning(f"Duration mismatch: got {duration/60:.1f}min, expected {expected_duration/60:.1f}min")
            return False
            
        logging.info(f"File duration verified: {duration/60:.1f} minutes")
        return True
    except Exception as e:
        logging.error(f"Error verifying download: {e}")
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
    """Clean up duplicate files in destination folder, keeping all split files."""
    try:
        files = glob.glob(os.path.join(space_folder, f'*-X-Space-#{space_id}*.m4a'))
        if not files:
            return None

        # Sort files by modification time (newest first)
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        # Keep all files that are part of the most recent set (split files)
        most_recent_base = os.path.splitext(files[0])[0].rsplit('_part', 1)[0]
        keep_files = [f for f in files if f.startswith(most_recent_base)]
        
        # Remove older files
        for file in files:
            if file not in keep_files:
                try:
                    os.remove(file)
                    logging.info(f"Removed duplicate file: {file}")
                except Exception as e:
                    logging.warning(f"Failed to remove duplicate file {file}: {e}")

        logging.info(f"Kept files: {keep_files}")
        return keep_files
    except Exception as e:
        logging.error(f"Error cleaning up destination duplicates: {e}")
        return None

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

def get_user_input(args):
    """Prompt for cookie file path if not provided."""
    if not args.cookie:
        cookie_path = input("Enter the full path to the X cookie file: ")
    else:
        cookie_path = args.cookie
    return {'cookie_path': cookie_path}

def check_tmp_for_existing_files(space_id):
    """Check for existing files and return the media file if found."""
    files = glob.glob(f'{TEMP_DIR}/*{space_id}*.*')
    if files:
        # First, look for complete media files
        media_files = [f for f in files if f.endswith('.m4a') and not f.endswith('.part') and not f.endswith('.info.json')]
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
                logging.debug(f" {f}")

        # Clean up partial downloads
        for partial_file in partial_files:
            try:
                os.remove(partial_file)
                logging.debug(f"Removed incomplete download: {partial_file}")
            except Exception as e:
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
            '--continue',              # Enable download resumption
            '--no-part',               # Don't use .part files
            '--fragment-retries', 'infinite',  # Keep retrying failed fragments
            '--retries', 'infinite',          # Keep retrying on errors
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
            logging.warning(f"Duration mismatch: got {duration/60:.1f}min, expected {expected_duration/60:.1f}min")
            return False
            
        logging.info(f"File duration verified: {duration/60:.1f} minutes")
        return True
    except Exception as e:
        logging.error(f"Error verifying download: {e}")
        return False

def convert_to_mp3(input_path, output_path, title=None, date=None):
    """Convert to MP3 and add metadata."""
    try:
        command = [
            'ffmpeg',
            '-i', input_path,
            '-c:a', 'libmp3lame',
            '-b:a', '192k',  # 192k bitrate for good quality and smaller file size
            '-map_metadata', '0'
        ]
        
        # Add metadata if provided
        if title:
            command.extend(['-metadata', f'title={title}'])
        if date:
            command.extend(['-metadata', f'date={date}'])
            
        command.append(output_path)
        
        subprocess.run(command, check=True, capture_output=True, text=True)
        logging.info(f"Successfully converted to MP3: {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error converting to MP3: {e}")
        if e.stderr:
            logging.error(f"FFmpeg error output: {e.stderr}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error during MP3 conversion: {e}")
        return False

def detect_long_silence(audio_path, min_silence_len=300000, silence_thresh=-50, max_duration=7200000):
    """Detect silence using ffmpeg instead of pydub."""
    try:
        # Use ffmpeg to analyze audio
        command = [
            'ffmpeg',
            '-i', audio_path,
            '-af', f'silencedetect=n={silence_thresh}dB:d={min_silence_len/1000}',
            '-f', 'null',
            '-'
        ]
        
        result = subprocess.run(command, capture_output=True, text=True, stderr=subprocess.PIPE)
        
        # Parse ffmpeg output for silence detection
        silence_starts = []
        for line in result.stderr.split('\n'):
            if 'silence_start' in line:
                try:
                    silence_start = float(line.split('silence_start: ')[1].split()[0])
                    silence_starts.append(silence_start * 1000)  # Convert to milliseconds
                except (IndexError, ValueError):
                    continue
        
        if silence_starts:
            # Return the first silence after 2 hours (if any)
            for start in silence_starts:
                if start >= max_duration:
                    return start
        
        return None
    except Exception as e:
        logging.error(f"Error in detect_long_silence: {str(e)}")
        return None

def cleanup_destination_duplicates(space_folder, space_id):
    """Clean up duplicate files in destination folder, keeping the most recent one."""
    try:
        files = glob.glob(os.path.join(space_folder, f'*-X-Space-#{space_id}*.m4a'))
        if not files:
            return None
            
        if len(files) == 1:
            return files[0]

        # Sort files by modification time (newest first)
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        keep_file = files[0]
        
        for file in files[1:]:
            try:
                os.remove(file)
                logging.info(f"Removed duplicate file: {file}")
            except Exception as e:
                logging.warning(f"Failed to remove duplicate file {file}: {e}")

        logging.info(f"Kept most recent file: {keep_file}")
        return keep_file
    except Exception as e:
        logging.error(f"Error cleaning up destination duplicates: {e}")
        return None

def trim_audio(input_path, output_path, trim_point):
    """
    Trim the audio file from the beginning to the trim point.
    """
    audio = AudioSegment.from_file(input_path)
    trimmed_audio = audio[:trim_point]
    trimmed_audio.export(output_path, format="m4a")
    logging.info(f"Audio trimmed at {trim_point/1000:.2f} seconds ({trim_point/60000:.2f} minutes)")

def get_unique_output_path(base_path, output_title, extension):
    """Get a unique output path, checking for both exact matches and similar filenames."""
    counter = 1
    while True:
        if counter == 1:
            file_name = f"{output_title}{extension}"
        else:
            file_name = f"{output_title}_{counter}{extension}"
        
        file_path = os.path.join(base_path, file_name)
        if not os.path.exists(file_path):
            return file_path
        counter += 1

def get_space_creation_date(file_path, specified_date=None):
    """Get the creation date from file metadata or specified date."""
    try:
        metadata = extract_metadata(file_path)
        creation_date = (
            metadata.get('format', {}).get('tags', {}).get('creation_time') or
            metadata.get('format', {}).get('tags', {}).get('date') or
            metadata.get('streams', [{}])[0].get('tags', {}).get('creation_time')
        )
        
        if creation_date:
            for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d", "%Y%m%d"]:
                try:
                    return datetime.strptime(creation_date, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
                    
        if specified_date:
            try:
                return datetime.strptime(specified_date, "%Y-%m-%d").strftime("%Y-%m-%d")
            except ValueError:
                logging.error(f"Invalid specified date format: {specified_date}")
                
        return datetime.now().strftime("%Y-%m-%d")
        
    except Exception as e:
        logging.error(f"Error getting creation date: {e}")
        return datetime.now().strftime("%Y-%m-%d")

def add_metadata_to_m4a(file_path, title=None, date=None):
    """Add metadata to M4A file."""
    try:
        temp_output = f"{os.path.splitext(file_path)[0]}_temp.m4a"
        command = [
            'ffmpeg',
            '-i', file_path,
            '-c', 'copy'
        ]
        
        # Add metadata if provided
        if title:
            command.extend(['-metadata', f'title={title}'])
        if date:
            command.extend(['-metadata', f'date={date}'])
            
        command.append(temp_output)
        
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



def cleanup_destination_duplicates(space_folder, space_id):
    """Clean up duplicate files in destination folder, keeping all split files."""
    try:
        files = glob.glob(os.path.join(space_folder, f'*-X-Space-#{space_id}*.m4a'))
        if not files:
            return []

        # Sort files by modification time (newest first)
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        # Keep all files that are part of the most recent set (split files)
        most_recent_base = os.path.splitext(files[0])[0].rsplit('_part', 1)[0]
        keep_files = [f for f in files if f.startswith(most_recent_base)]
        
        # Remove older files that are not part of the most recent set
        for file in files:
            if file not in keep_files:
                try:
                    os.remove(file)
                    logging.info(f"Removed duplicate file: {file}")
                except Exception as e:
                    logging.warning(f"Failed to remove duplicate file {file}: {e}")

        logging.info(f"Kept files: {keep_files}")
        return keep_files
    except Exception as e:
        logging.error(f"Error cleaning up destination duplicates: {e}")
        return []

def get_audio_duration(file_path):
    try:
        probe_cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        duration = float(subprocess.check_output(probe_cmd).decode('utf-8').strip())
        return duration
    except Exception as e:
        logging.error(f"Error getting audio duration: {str(e)}")
        return 0

def download_twitch_vod(vod_url, output_path):
    try:
        command = [
            'yt-dlp',
            '--no-part',
            '--no-continue',
            '-o', output_path,
            vod_url
        ]
        subprocess.run(command, check=True)
        logging.info(f"Successfully downloaded Twitch VOD to {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        logging.error(f"Error downloading Twitch VOD: {e}")
        return None

def parse_arguments():
    parser = argparse.ArgumentParser(description="X-Recorder and Twitch VOD Downloader")
    parser.add_argument("-o", "--output", type=str, default=DEFAULT_DOWNLOAD_DIR,
                        help=f"Output directory for saving recordings (default: {DEFAULT_DOWNLOAD_DIR})")
    parser.add_argument("-oc", "--output-copy", type=str, 
                        help="Additional directory to copy the recordings to")
    parser.add_argument("-c", "--cookie", type=str, 
                        help="Full path to the X cookie file")
    parser.add_argument("-d", "--debug", action="store_true", 
                        help="Enable debug mode for verbose output")
    parser.add_argument("-u", "--url", type=str, 
                        help="Direct link to a specific X Space or Twitch VOD")
    parser.add_argument("-s", "--space", type=str, 
                        help="Direct link to a specific X Space")
    return parser.parse_args()

def process_x_space(space_url, user_input, args):
    # Existing X Space processing logic here
    pass

def process_twitch_vod(vod_url, args):
    vod_id = vod_url.split('/')[-1]
    output_folder = os.path.join(args.output, f"twitch_{vod_id}")
    os.makedirs(output_folder, exist_ok=True)
    
    output_path = os.path.join(output_folder, f"twitch_vod_{vod_id}.mp4")
    downloaded_file = download_twitch_vod(vod_url, output_path)
    
    if downloaded_file:
        logging.info(f"Twitch VOD downloaded: {downloaded_file}")
        # Add any post-processing steps for Twitch VODs here
    else:
        logging.error("Failed to download Twitch VOD")


def main():
    logging.info(f"Temporary files will be stored in: {TEMP_DIR}")
    
    args = parse_arguments()
    success = False
    had_errors = False
    video_space = False
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    user_input = get_user_input(args)
    
    if args.url:
        url = args.url
        if 'twitter.com' in url or 'x.com' in url:
            space_id = url.split('/')[-1]
            process_x_space(url, user_input, space_id, args)
        elif 'twitch.tv' in url:
            process_twitch_vod(url, args)
        else:
            logging.error("Unsupported URL. Please provide a valid X Space or Twitch VOD URL.")
    else:
        logging.error("Please provide a direct URL using the -u option.")

def process_x_space(space_url, user_input, space_id, args):
    try:
        metadata_command = [
            'yt-dlp',
            '--cookies', user_input['cookie_path'],
            '--dump-json',
            '--no-download',
            space_url
        ]
        
        metadata_result = subprocess.run(metadata_command, capture_output=True, text=True, check=True)
        space_info = json.loads(metadata_result.stdout)
        
        space_title = str(space_info.get('title', ''))
        space_date = space_info.get('upload_date', '')
        
        space_folder = os.path.join(args.output, space_id)
        os.makedirs(space_folder, exist_ok=True)

        temp_file_path, is_new_download = download_space(space_url, user_input['cookie_path'], args.debug)

        if temp_file_path:
            add_metadata_to_m4a(temp_file_path, title=space_title, date=space_date)

            final_output_path = get_unique_output_path(space_folder, f"{space_title}-X-Space-#{space_id}", ".m4a")
            shutil.move(temp_file_path, final_output_path)

            logging.info(f"Successfully downloaded and moved file to {final_output_path}")

            file_duration = get_audio_duration(final_output_path)
            logging.info(f"File duration: {file_duration/60:.1f} minutes")

            if args.output_copy:
                copy_to_additional_location(final_output_path, args.output_copy, space_id)

            metadata_files = glob.glob(os.path.join(TEMP_DIR, f'X-Space-{space_id}*.*'))
            for metadata_file in metadata_files:
                if any(x in metadata_file for x in ['_metadata.json', '.info.json']):
                    dest_metadata_file_name = os.path.basename(metadata_file)
                    dest_metadata_file_path = os.path.join(space_folder, dest_metadata_file_name)
                    shutil.copy2(metadata_file, dest_metadata_file_path)
                    logging.debug(f"Copied metadata file to: {dest_metadata_file_path}")

            success = True

        else:
            logging.error("Failed to download or locate the X Space media file.")
            had_errors = True

    except Exception as e:
        logging.error(f"Error processing X Space: {str(e)}")
        had_errors = True

def process_twitch_vod(vod_url, args):
    vod_id = vod_url.split('/')[-1]
    output_folder = os.path.join(args.output, f"twitch_{vod_id}")
    os.makedirs(output_folder, exist_ok=True)
    
    output_path = os.path.join(output_folder, f"twitch_vod_{vod_id}.mp4")
    metadata_path = os.path.join(output_folder, f"twitch_vod_{vod_id}_metadata.json")
    
    # Fetch metadata from Twitch API
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {TWITCH_OAUTH_TOKEN}'
    }
    response = requests.get(f'https://api.twitch.tv/helix/videos?id={vod_id}', headers=headers)
    
    if response.status_code == 200:
        vod_metadata = response.json()['data'][0]
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(vod_metadata, f, indent=2, ensure_ascii=False)
        logging.info(f"Twitch VOD metadata saved to: {metadata_path}")
    else:
        logging.error(f"Failed to fetch Twitch VOD metadata: {response.status_code}")
        vod_metadata = {}

    downloaded_file = download_twitch_vod(vod_url, output_path)
    
    if downloaded_file:
        logging.info(f"Twitch VOD downloaded: {downloaded_file}")
        
        # Add metadata to the video file
        try:
            title = vod_metadata.get('title', f'Twitch VOD {vod_id}')
            created_at = vod_metadata.get('created_at', '')
            user_name = vod_metadata.get('user_name', '')
            
            command = [
                'ffmpeg',
                '-i', downloaded_file,
                '-c', 'copy',
                '-metadata', f'title={title}',
                '-metadata', f'date={created_at}',
                '-metadata', f'artist={user_name}',
                '-metadata', f'comment=Twitch VOD ID: {vod_id}',
                f'{downloaded_file}_temp.mp4'
            ]
            subprocess.run(command, check=True)
            os.replace(f'{downloaded_file}_temp.mp4', downloaded_file)
            logging.info("Metadata added to Twitch VOD file")
        except Exception as e:
            logging.error(f"Error adding metadata to Twitch VOD: {str(e)}")
    else:
        logging.error("Failed to download Twitch VOD")


if __name__ == "__main__":
    main()
