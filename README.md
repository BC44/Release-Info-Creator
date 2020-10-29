# Release-Info-Creator
Generates mediainfo and screenshots automatically given a video file, uploads them, then pastes the resulting mediainfo and image URLs to your clipboard.



## Requirements
Minimum Python 3.6

Directories that contain `mediainfo` and `ffmpeg` binaries should be set to PATH



## Setup
Run `pip install -r requirements.txt` to install required modules

Run the script as indicated below. If no config `.json` file exists, a first-run setup will launch and you will be asked to input your preferences / image host API keys



## Usage

> Detects `*.ifo` file in the same directory and gathers mediainfo from it as well

    py Release-Info-Creator.py "DVD_main_folder"

    py Release-Info-Creator.py "video_file.mkv"
