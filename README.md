# 𝕏-Recorder: Archive and Download 𝕏 Spaces

𝕏-Recorder is a powerful tool for capturing, archiving, and downloading 𝕏 Spaces (formerly Twitter Spaces). It supports both audio and video spaces, allowing you to never miss your favorite content again!

## Features

- Download 𝕏 Spaces using direct links
- Automatic aspect ratio change detection and correction
- Easy-to-use command-line interface
- Automatic fallback to yt-dlp if twspace-dl fails
- Error handling for unsupported space types
- Debug mode for verbose output

## Prerequisites

To use 𝕏-Recorder, you need:

1. 𝕏 (Twitter) Cookie File
2. Python 3.6 or higher
3. OpenCV library

### Obtaining the 𝕏 (Twitter) Cookie File

You need to obtain the 𝕏 (Twitter) cookie file in Netscape format. Here's how to do it without using a browser plugin:

1. Open your web browser (Chrome, Firefox, or Edge) and go to 𝕏 (Twitter).

2. Log in to your 𝕏 account if you haven't already.

3. Open the browser's Developer Tools:
   - Chrome/Edge: Press F12 or Ctrl+Shift+I (Cmd+Option+I on Mac)
   - Firefox: Press F12 or Ctrl+Shift+I (Cmd+Option+I on Mac)

4. Go to the "Network" tab in the Developer Tools.

5. Refresh the 𝕏 page.

6. In the Network tab, find any request to "twitter.com" or "x.com".

7. Click on this request and look for the "Cookies" section in the request headers.

8. Copy all the cookie data. It should look something like this:
   ```
   auth_token=1234567890abcdef; ct0=abcdefghijklmnop; ...
   ```

9. Open a text editor and create a new file.

10. At the top of the file, add the following line:
    ```
    # Netscape HTTP Cookie File
    ```

11. For each cookie in the data you copied, add a line in this format:
    ```
    .twitter.com	TRUE	/	TRUE	1767225600	cookie_name	cookie_value
    ```
    Replace `cookie_name` and `cookie_value` with the actual name and value of each cookie.

12. Save the file with a `.txt` extension, for example `x_cookies.txt`.

Example of the final cookie file content:
```
# Netscape HTTP Cookie File
.twitter.com	TRUE	/	TRUE	1767225600	auth_token	1234567890abcdef
.twitter.com	TRUE	/	TRUE	1767225600	ct0	abcdefghijklmnop
```

Make sure to keep this file secure and do not share it, as it contains your login information.

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/rasrobo/X-Recorder.git
   ```
2. Navigate to the project directory:
   ```
   cd X-Recorder
   ```
3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Install `twspace-dl`:
   ```
   pip install twspace-dl
   ```
5. Install `yt-dlp`:
   ```
   pip install yt-dlp
   ```
6. Install OpenCV:
   ```
   pip install opencv-python
   ```

## Usage

Run the script with the following command:

```
python 𝕏_recorder.py -c /path/to/cookie/file -s SPACE_LINK [-o OUTPUT_DIR] [-d]
```

- `-c` or `--cookie`: Required. Specify the full path to the 𝕏 (Twitter) cookie file in Netscape format.
- `-s` or `--space`: Required. Specify the direct link to a specific 𝕏 Space.
- `-o` or `--output`: Optional. Specify the output directory for saving recordings. Default is `~/Downloads/𝕏-Recorder`.
- `-d` or `--debug`: Optional. Enable debug mode for verbose output.

## Examples

1. Download a specific space:
   ```
   python 𝕏_recorder.py -c /path/to/cookie/file -s https://twitter.com/i/spaces/1RDGlyLmRPrJL
   ```

2. Download a space with debug output:
   ```
   python 𝕏_recorder.py -c /path/to/cookie/file -s https://twitter.com/i/spaces/1RDGlyLmRPrJL -d
   ```

3. Download a space to a specific output directory:
   ```
   python 𝕏_recorder.py -c /path/to/cookie/file -s https://twitter.com/i/spaces/1RDGlyLmRPrJL -o /path/to/custom/output
   ```

## Output

The script will generate two files in the specified output directory:
1. The original downloaded space file (usually in .m4a format)
2. A processed video file with corrected aspect ratios (in .mp4 format)

## Troubleshooting

- If you encounter a "ModuleNotFoundError" for cv2, make sure you have installed OpenCV using `pip install opencv-python`.
- If the download fails, check that your cookie file is up to date and that you have the necessary permissions to access the 𝕏 Space.
- For any other issues, run the script with the `-d` flag to get more detailed debug output.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Keywords

X Spaces, Twitter Spaces, audio recording, video recording, podcast archiving, social media content, live audio, live video, space downloader, X API, Twitter API, audio archiver, video archiver, space recorder, aspect ratio correction
