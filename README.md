# X-Recorder

## Download and Archive X Spaces with Metadata Preservation

X-Recorder is a powerful command-line tool for capturing, archiving, and downloading X Spaces (formerly Twitter Spaces). Perfect for content creators, researchers, and anyone wanting to maintain a high-quality archive of X Spaces.

### Features
- High-quality audio downloads
- Preserves original metadata (title, date)
- Smart handling of video spaces
- Consistent file naming and organization
- Automatic metadata embedding
- Robust error handling and recovery
- Debug mode for troubleshooting

### Use Cases
- Content creators archiving their spaces
- Researchers collecting data
- Podcast creators repurposing content
- Digital archivists
- Personal collections

## Installation

1. Clone the repository:
```bash
git clone https://github.com/rasrobo/X-Recorder.git
cd X-Recorder
```

2. Create a virtual environment:
```bash
python -m venv x-recorder-env
source x-recorder-env/bin/activate  # Linux/Mac
# or
.\x-recorder-env\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Basic usage:
```bash
python x_recorder.py -c /path/to/cookie.txt -s https://x.com/i/spaces/YOUR_SPACE_ID
```

Options:
- `-c, --cookie`: Path to X cookie file
- `-o, --output`: Custom output directory
- `-d, --debug`: Enable debug logging
- `-s, --space`: X Space URL to download

## Output Format
Downloads are organized by space ID:
```
output_dir/
└── space_id/
    ├── YYYY-MM-DD-space-title-#space_id.m4a
    └── YYYY-MM-DD-space-title-#space_id.mp3 (for video spaces)
```

## Requirements
- Python 3.8+
- ffmpeg
- X (Twitter) cookie file
- Internet connection

## Obtaining the X Cookie File

1. Open your browser and log in to X
2. Open Developer Tools (F12) and go to the Network tab
3. Find a request to "twitter.com" or "x.com" and copy the cookie data
4. Save as a text file

## Troubleshooting

- For "ModuleNotFoundError": Ensure all dependencies are installed
- If download fails: Check cookie file and permissions
- Use `-d` flag for verbose debug output

## Donations

If you find this software useful and would like to support its development, you can buy me a coffee! Your support is greatly appreciated.

[![Buy Me A Coffee](https://cdn.buymeacoffee.com/buttons/default-orange.png)](https://buymeacoffee.com/robodigitalis)

## Contributing
Contributions welcome! Please feel free to submit a Pull Request.

## License
MIT License

---

Keywords: X Spaces downloader, Twitter Spaces recorder, social media archival tool, X Space archive, Twitter Space download, social media content preservation, X Spaces backup tool, Twitter Spaces archiver, audio recording, space downloader, audio archiver, metadata preservation, space recorder, content archival, podcast archiving, digital preservation, X API, audio archiving tool
