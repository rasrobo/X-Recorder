# 𝕏-Recorder: Ultimate Twitter Spaces Recorder

𝕏-Recorder is a powerful tool for capturing, archiving, and downloading pre-recorded Twitter Spaces (now known as 𝕏 Spaces). It's like a VCR for your favorite audio and video content!

## Key Features

- Download missed 𝕏 Spaces using direct links
- Supports both audio and video spaces
- Automatic aspect ratio correction for video spaces
- Smart fallback system (twspace-dl to yt-dlp)
- Efficient handling of previously downloaded spaces
- Debug mode for troubleshooting

## Prerequisites

- Python 3.6+
- 𝕏 (Twitter) Cookie File
- OpenCV library

## Quick Start

1. Clone and set up:
   ```bash
   git clone https://github.com/rasrobo/X-Recorder.git
   cd X-Recorder
   pip install -r requirements.txt
   pip install twspace-dl yt-dlp opencv-python
   ```

2. Run the script:
   ```bash
   python x_recorder.py -c /path/to/cookie/file -s SPACE_LINK
   ```

## Advanced Usage

### Custom Output Directory

```bash
python x_recorder.py -c /path/to/cookie/file -s SPACE_LINK -o /custom/output/path
```

### Debug Mode

```bash
python x_recorder.py -c /path/to/cookie/file -s SPACE_LINK -d
```

## Output

The script generates two files:
1. Original downloaded space file (.m4a format)
2. Processed video file with corrected aspect ratios (.mp4 format)

## Obtaining the 𝕏 (Twitter) Cookie File

1. Open your browser and log in to 𝕏 (Twitter).
2. Open Developer Tools (F12) and go to the Network tab.
3. Find a request to "twitter.com" or "x.com" and copy the cookie data.
4. Create a text file with the header:
   ```
   # Netscape HTTP Cookie File
   ```
5. Add each cookie in this format:
   ```
   .twitter.com	TRUE	/	TRUE	1767225600	cookie_name	cookie_value
   ```
6. Save as `x_cookies.txt`.

## Troubleshooting

- For "ModuleNotFoundError": Ensure all dependencies are installed.
- If download fails: Check cookie file and permissions.
- Use `-d` flag for verbose debug output.

## Donations

If you find this software useful and would like to support its development, you can buy me a coffee! Your support is greatly appreciated.

[![Buy Me A Coffee](https://cdn.buymeacoffee.com/buttons/default-orange.png)](https://buymeacoffee.com/robodigitalis)


## Contributing

We welcome contributions! Please submit a Pull Request or open an Issue.

## License

MIT License - see [LICENSE](LICENSE) for details.

---

𝕏-Recorder: Your go-to solution for recording and archiving Twitter Spaces. Perfect for podcast enthusiasts, social media managers, and content creators.

Keywords: X Spaces, Twitter Spaces, audio recording, video recording, podcast archiving, social media content, live audio, live video, space downloader, X API, Twitter API, audio archiver, video archiver, space recorder, aspect ratio correction