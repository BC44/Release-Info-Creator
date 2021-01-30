# Release-Info-Creator
Generates mediainfo and screenshots automatically given a video file, uploads them, then pastes the resulting mediainfo and image URLs to your clipboard.



## Requirements
Minimum Python 3.6

`mediainfo` and `ffmpeg` command-line tools

Note: The `mediainfo` CLI tool that is installable via apt/apt-get for linux may not support JSON-formatted console outputs. It's best to install the CLI tool directly from https://mediaarea.net/en/MediaInfo/Download



## Setup
Run `pip3 install -r requirements.txt` to install required modules

Run the script as indicated below. If no config `.json` file exists, a first-run setup will launch and you will be asked to input your preferences / image host API keys



## Usage

> Detects `*.ifo` file in the same directory and gathers mediainfo from it as well

    py Release-Info-Creator.py "DVD_main_folder"

    py Release-Info-Creator.py "video_file.mkv"
