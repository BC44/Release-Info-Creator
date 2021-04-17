# Release-Info-Creator
Generates mediainfo and screenshots automatically given a video file, uploads them, then pastes the resulting mediainfo and image URLs to your clipboard.



## Requirements
Minimum Python 3.6

`mediainfo` and `ffmpeg` command-line tools

Note: The `mediainfo` CLI tool that is installable via apt/apt-get for linux may not support JSON-formatted console outputs. To check, invoke MediaInfo manually via a terminal: `MediaInfo --Output=JSON "video_file.mkv"`. 

If it doesn't output the mediainfo in a JSON format, then you'll need to install the CLI tool directly from https://mediaarea.net/en/MediaInfo/Download



## Setup
Run `pip3 install -r requirements.txt` to install required modules

Run the script as indicated below. If no config `.json` file exists, a first-run setup will launch and you will be asked to input your preferences / image host API keys



## Usage

> Will also detect the correct `*.ifo` file from DVD folder

    py ReleaseInfoCreator.py "DVD_main_folder"

    py ReleaseInfoCreator.py "video_file.mkv"
