# MediaInfo_ScreenshotGenerator
Generates mediainfo and screenshots automatically given a video file, uploads them, then pastes the resulting mediainfo and image URLs to your clipboard.

Requires minimum Python 3.6


# Setup
Set `IMAGE_SAVE_LOCATION` to your desired save location for screenshots and `IMGBB_KEY` for your [imgbb](https://imgbb.com/) account's API key inside the .py file

Run `pip3 install -r requirements.txt`


# Usage
	
	> Detects `*.ifo` file in the same directory and gathers mediainfo from it as well

    py MediaScreenGen.py "video_file.vob"

    py MediaScreenGen.py "video_file.mkv"
