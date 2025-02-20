import argparse
import subprocess
import os
import glob
import json
import shutil
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass

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
            temp_metadata_file = os.path.join(TEMP_DIR, f"metadata_{os.path.basename(file_path)}.txt")
            extract_cmd = [
                'ffmpeg',
                '-i', file_path,
                '-f', 'ffmetadata',
                temp_metadata_file
            ]
            subprocess.run(extract_cmd, capture_output=True, text=True, check=True)
            with open(temp_metadata_file, 'r', encoding='utf-8') as f:
                metadata_text = f.read()
            os.remove(temp_metadata_file)
            metadata = {'format': {'tags': {}}}
            for line in metadata_text.splitlines():
                if '=' in line:
                    key, value = line.split('=', 1)
                    metadata['format']['tags'][key.strip()] = value.strip()
        return metadata
    except Exception as e:
        logging.error(f"Error extracting metadata: {e}")
    return {'format': {'tags': {}}}

def sanitize_filename(title):
    """Make filename safe for all filesystems using POSIX-safe naming convention."""
    # First, replace problematic characters and sequences
    replacements = {
        "::: ": "_",
        ":::": "_",
        ": ": "_",
        ":": "_",
        "/": "_",
        "\\": "_",
        "w/": "w_",
        " - ": "_",
        "-": "_",
        " ": "_"
    }
    
    # Apply replacements
    for old, new in replacements.items():
        title = title.replace(old, new)
    
    # Keep only alphanumeric and safe characters
    safe_chars = "_.()"
    filename = ''.join(c for c in title if c.isalnum() or c in safe_chars)
    
    # Clean up multiple underscores
    while "__" in filename:
        filename = filename.replace("__", "_")
    
    # Remove leading/trailing underscores and dots
    filename = filename.strip('._')
    
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
        if metrics['title']:
            logging.info(f"Title: {metrics['title']}")
        if metrics['creator']:
            logging.info(f"Creator: {metrics['creator']} (Followers: {metrics['creator_followers']:,})")
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
        logging.info("\nViewer Statistics:")
        if metrics['concurrent_viewers']:
            logging.info(f"Peak Concurrent Viewers: {metrics['concurrent_viewers']:,}")
        if metrics['total_viewers']:
            logging.info(f"Total Viewers: {metrics['total_viewers']:,}")
        if metrics['live_viewers']:
            logging.info(f"Live Viewers: {metrics['live_viewers']:,}")
        if metrics['replay_viewers']:
            logging.info(f"Replay Viewers: {metrics['replay_viewers']:,}")
        logging.info("\nEngagement:")
        if metrics['participant_count']:
            logging.info(f"Total Participants: {metrics['participant_count']:,}")
        if metrics['likes']:
            logging.info(f"Likes: {metrics['likes']:,}")
        if metrics['retweets']:
            logging.info(f"Retweets: {metrics['retweets']:,}")
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

def generate_summary_report(metadata_path, space_id, final_output_path, duration, success, had_errors):
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        report = {
            "space_id": space_id,
            "title": metadata.get('title', ''),
            "duration_minutes": duration / 60 if duration else 0,
            "file_path": final_output_path,
            "file_size_mb": get_file_size_mb(final_output_path),
            "success": success,
            "had_errors": had_errors,
            "participants": metadata.get('participants', []),
            "viewer_count": metadata.get('viewer_count', 0),
            "started_at": metadata.get('started_at', ''),
            "ended_at": metadata.get('ended_at', '')
        }
        report_path = os.path.join(os.path.dirname(final_output_path), f"{space_id}_report.json")
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logging.info(f"Summary report generated: {report_path}")
    except Exception as e:
        logging.error(f"Error generating summary report: {str(e)}")
        logging.error(f"Error type: {type(e).__name__}")

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

def verify_download(file_path, expected_duration=None):
    """Verify downloaded file integrity and duration."""
    try:
        if not os.path.exists(file_path):
            logging.error(f"File does not exist: {file_path}")
            return False
            
        logging.debug(f"Verifying file: {file_path}")
        command = [
            'ffprobe',
            '-v', 'error',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        
        # Check if file has valid format information
        if not info.get('format'):
            logging.error("No format information found in file")
            return False
            
        duration = float(info['format'].get('duration', 0))
        if duration < 60:
            logging.warning(f"File duration suspiciously short: {duration/60:.1f} minutes")
            return False
            
        if expected_duration and abs(duration - expected_duration) > 300:
            logging.warning(f"Duration mismatch: got {duration/60:.1f}min, expected {expected_duration/60:.1f}min")
            return False
            
        logging.info(f"File duration verified: {duration/60:.1f} minutes")
        return True
        
    except Exception as e:
        logging.error(f"Error verifying download: {e}")
        return False

def cleanup_temp_files(space_id=None, preserve_metadata=True):
    """Clean up temporary files with better error handling."""
    pattern = f'X-Space-{space_id}*' if space_id else 'X-Space-*'
    preserved_extensions = ['.json', '.info.json']
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

def copy_to_additional_location(source_file, output_copy_dir, space_id):
    """Copy the file to an additional location."""
    try:
        copy_space_folder = os.path.join(output_copy_dir, space_id)
        os.makedirs(copy_space_folder, exist_ok=True)
        filename = os.path.basename(source_file)
        copy_path = os.path.join(copy_space_folder, filename)
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
        media_files = [f for f in files if f.endswith('.m4a') and not f.endswith('.part') and not f.endswith('.info.json')]
        metadata_files = [f for f in files if f.endswith(('.json', '.m3u8'))]
        partial_files = [f for f in files if f.endswith('.part')]
        if media_files:
            selected_file = media_files[0]
            logging.info(f"Found existing media file: {selected_file}")
            return selected_file
        if metadata_files:
            logging.debug("Found metadata files, but no media file")
        if partial_files:
            logging.debug("Found partial download files")
        return None
    return None

def download_space(space_url, cookie_path, debug=False):
    """Download X Space using yt-dlp with improved temp file handling."""
    try:
        space_id = space_url.split('/')[-1]
        temp_file_pattern = os.path.join(TEMP_DIR, f'X-Space-{space_id}_temp.*')
        existing_temp = glob.glob(temp_file_pattern)
        
        # Filter for media files only
        existing_media = [f for f in existing_temp if f.endswith(('.mp4', '.m4a'))]
        
        if existing_media:
            temp_file = existing_media[0]
            logging.info(f"Found existing temp file: {temp_file}")
            return temp_file, False

        output_template = os.path.join(TEMP_DIR, f'X-Space-{space_id}_temp.%(ext)s')
        command = [
            'yt-dlp',
            '--no-part',
            '--cookies', cookie_path,
            '-o', output_template,
            space_url
        ]
        if debug:
            command.insert(1, '-v')
            
        subprocess.run(command, check=True)
        
        # Look for newly downloaded media files
        downloaded_files = glob.glob(temp_file_pattern)
        media_files = [f for f in downloaded_files if f.endswith(('.mp4', '.m4a'))]
        
        if media_files:
            downloaded_file = media_files[0]
            logging.info(f"Successfully downloaded file: {downloaded_file}")
            return downloaded_file, True
        else:
            raise FileNotFoundError("No media file found after download")
            
    except Exception as e:
        logging.error(f"Download error: {e}")
        return None, False

def add_metadata_to_m4a(file_path, title, date):
    """Add metadata to M4A file."""
    try:
        command = [
            'ffmpeg',
            '-i', file_path,
            '-c', 'copy',
            '-metadata', f'title={title}',
            '-metadata', f'date={date}',
            f'{file_path}_temp.m4a'
        ]
        subprocess.run(command, check=True)
        os.replace(f'{file_path}_temp.m4a', file_path)
        logging.info(f"Metadata added to {file_path}: title={title}, date={date}")
    except Exception as e:
        logging.error(f"Error adding metadata to file: {e}")

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

def get_audio_duration(file_path):
    """Get audio duration using ffprobe."""
    try:
        command = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return float(result.stdout)
    except Exception as e:
        logging.error(f"Error getting audio duration: {e}")
        return 0

def download_twitch_vod(vod_url, output_path):
    """Download Twitch VOD using yt-dlp with progress updates."""
    try:
        command = [
            'yt-dlp',
            '--no-part',
            '--no-continue',
            '-o', output_path,
            '--progress',
            vod_url
        ]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        for line in process.stdout:
            if '[download]' in line:
                logging.info(line.strip())
        process.wait()
        if process.returncode == 0:
            logging.info(f"Successfully downloaded Twitch VOD to {output_path}")
            return output_path
        else:
            logging.error(f"Error downloading Twitch VOD: yt-dlp exited with code {process.returncode}")
            return None
    except Exception as e:
        logging.error(f"Error downloading Twitch VOD: {e}")
        return None

def process_twitch_vod(vod_url, args):
    try:
        # Get VOD metadata first
        vod_id = vod_url.split('/')[-1]
        
        metadata_command = [
            'yt-dlp',
            '--dump-json',
            '--no-download',
            vod_url
        ]
        metadata_result = subprocess.run(metadata_command, capture_output=True, text=True, check=True)
        vod_info = json.loads(metadata_result.stdout)
        
        # Extract relevant metadata fields from yt-dlp
        streamer_name = vod_info.get('uploader', 'Unknown')
        stream_title = vod_info.get('title', f'Twitch VOD {vod_id}')
        
        # Get the actual stream date from timestamp
        if vod_info.get('timestamp'):
            formatted_date = datetime.fromtimestamp(vod_info['timestamp']).strftime('%Y%m%d')
        elif vod_info.get('release_timestamp'):
            formatted_date = datetime.fromtimestamp(vod_info['release_timestamp']).strftime('%Y%m%d')
        else:
            formatted_date = vod_info.get('upload_date', datetime.now().strftime('%Y%m%d'))
            logging.warning(f"Could not get stream timestamp, using date: {formatted_date}")
        
        # Create POSIX-safe directory name
        dir_name = f"{formatted_date}_{sanitize_filename(streamer_name)}_{sanitize_filename(stream_title)}"
        output_folder = os.path.join(args.output, dir_name)
        os.makedirs(output_folder, exist_ok=True)
        
        # Create final output path with same naming convention
        output_path = os.path.join(output_folder, f"{dir_name}.mp4")
        
        downloaded_file = download_twitch_vod(vod_url, output_path)
        
        if downloaded_file:
            logging.info(f"Twitch VOD downloaded: {downloaded_file}")
            
            # Add metadata to the video file
            try:
                command = [
                    'ffmpeg',
                    '-i', downloaded_file,
                    '-c', 'copy',
                    '-metadata', f'title={stream_title}',
                    '-metadata', f'date={formatted_date}',
                    '-metadata', f'artist={streamer_name}',
                    '-metadata', f'comment=Twitch VOD ID: {vod_id}',
                    f'{downloaded_file}_temp.mp4'
                ]
                subprocess.run(command, check=True)
                os.replace(f'{downloaded_file}_temp.mp4', downloaded_file)
                logging.info("Metadata added to Twitch VOD file")
                
                file_duration = get_audio_duration(downloaded_file)
                logging.info(f"File duration: {file_duration/60:.1f} minutes")
                
                if args.output_copy:
                    copy_to_additional_location(downloaded_file, args.output_copy, dir_name)
                    
                return True
                
            except Exception as e:
                logging.error(f"Error adding metadata to Twitch VOD: {str(e)}")
                return False
        else:
            logging.error("Failed to download Twitch VOD")
            return False
            
    except Exception as e:
        logging.error(f"Error processing Twitch VOD: {str(e)}")
        return False

def process_x_space(space_url, user_input, space_id, args):
    temp_file_path = None
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
        
        # Get the actual recording date from the timestamp if available
        if space_info.get('release_timestamp'):
            space_date = datetime.fromtimestamp(space_info['release_timestamp']).strftime('%Y%m%d')
        elif space_info.get('timestamp'):
            space_date = datetime.fromtimestamp(space_info['timestamp']).strftime('%Y%m%d')
        else:
            # Fallback to current date
            space_date = datetime.now().strftime('%Y%m%d')
            logging.warning(f"Could not get recording date from metadata, using current date: {space_date}")
        
        # Create sanitized names for both directory and file
        sanitized_name = f"{space_date}_{sanitize_filename(space_title)}"
        
        # Create output folder using sanitized name
        output_folder = os.path.join(args.output, sanitized_name)
        os.makedirs(output_folder, exist_ok=True)
        logging.info(f"Created folder: {output_folder}")

        temp_file_path, is_new_download = download_space(space_url, user_input['cookie_path'], args.debug)

        if temp_file_path:
            # Verify the downloaded file
            if not verify_download(temp_file_path):
                logging.error("Downloaded file verification failed.")
                # Don't delete temp file on verification failure
                return False

            try:
                add_metadata_to_m4a(temp_file_path, title=space_title, date=space_date)
                final_output_path = os.path.join(output_folder, f"{sanitized_name}.m4a")
                shutil.move(temp_file_path, final_output_path)
                logging.info(f"Successfully downloaded and moved file to {final_output_path}")

                file_duration = get_audio_duration(final_output_path)
                if file_duration == 0:
                    logging.error("Failed to get audio duration, file might be corrupted.")
                    # Move file back to temp location if duration check fails
                    shutil.move(final_output_path, temp_file_path)
                    return False

                # Process completed successfully, now we can cleanup
                cleanup_temp_files(space_id)
                return True

            except Exception as e:
                logging.error(f"Error processing file: {e}")
                # Keep temp file on processing error
                return False
        else:
            logging.error("Failed to download or locate the X Space media file.")
            return False
            
    except Exception as e:
        logging.error(f"Error processing X Space: {str(e)}")
        # Keep temp file on any error
        return False

def parse_arguments():
    """Parse command line arguments."""
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
    return parser.parse_args()

def main():
    logging.info(f"Temporary files will be stored in: {TEMP_DIR}")
    args = parse_arguments()
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

if __name__ == "__main__":
    main()
