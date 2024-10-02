# X-Recorder: Archive and Download X Spaces

X-Recorder is a powerful tool for capturing, archiving, and downloading X Spaces (formerly Twitter Spaces). It supports both audio and video spaces, allowing you to never miss your favorite content again!

## Features

- Search for X Spaces by profile or direct link
- Flexible timeframe options: 7, 14, 30, 90, or 120 days
- Easy-to-use command-line interface
- Comprehensive summary of found recordings
- Automatically download audio and video spaces
- Error handling for unsupported space types

## Prerequisites

To use X-Recorder, you need to obtain two important pieces of information:

1. X (Twitter) Cookie File
2. X (Twitter) API Access Token

### Obtaining the X (Twitter) Cookie File

1. Install the "Cookie-Editor" Chrome extension from the Chrome Web Store: [Cookie Editor](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)

2. Log in to your X (Twitter) account in the Chrome browser.

3. Click on the "Cookie-Editor" extension icon in the Chrome toolbar.

4. In the Cookie-Editor window, select the "X.com" domain from the list of websites.

5. Click on the "Export" button and choose "Netscape HTTP Cookie File" as the format.

6. Save the exported cookie file in Netscape format to a location of your choice.

### Obtaining the X (Twitter) API Access Token

To obtain an API access token, you need to have a developer account on the X (Twitter) platform. Follow these steps:

1. Go to the X (Twitter) Developer Portal (https://developer.twitter.com/) and sign in with your X (Twitter) account.

2. Create a new developer app or select an existing one.

3. In your app's dashboard, navigate to the "Keys and Tokens" section.

4. Generate a new access token and access token secret for your app.

5. Copy the access token and keep it safe. You will need it when running the X-Recorder script.

Please note that to access certain features and endpoints of the X (Twitter) API, you may need to have a Premium or Enterprise subscription. Check the X (Twitter) API documentation for more information on the available subscription plans and their limitations.

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

## Usage

Run the script with the following command:

```
python x_recorder.py -c /path/to/cookie/file -a YOUR_API_ACCESS_TOKEN [-t TIMEFRAME] [-o OUTPUT_DIR] [-d] [-p PROFILE]
```

- `-c` or `--cookie`: Required. Specify the full path to the X (Twitter) cookie file in Netscape format.
- `-a` or `--access-token`: Required. Specify your X (Twitter) API access token.
- `-t` or `--timeframe`: Optional. Specify the number of days to search for recordings. Choose from 7, 14, 30, 90, or 120 days. Default is 7 days.
- `-o` or `--output`: Optional. Specify the output directory for saving recordings. Default is `~/Downloads/X-Recorder`.
- `-d` or `--debug`: Optional. Enable debug mode for verbose output (API connections, commands, and downloads).
- `-p` or `--profile`: Optional. Specify the X profile name(s) to search for spaces (comma-separated if multiple).

## Example

```
python x_recorder.py -c /path/to/cookie/file -a YOUR_API_ACCESS_TOKEN -t 30 -o /path/to/custom/output -d -p aiarttoday420
```

This command will search for X Spaces recordings from the past 30 days for the profile "aiarttoday420", save them in the specified output directory, and enable debug mode for verbose output.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Keywords

X Spaces, Twitter Spaces, audio recording, video recording, podcast archiving, social media content, live audio, live video, space downloader, X API, Twitter API, audio archiver, video archiver, space recorder

