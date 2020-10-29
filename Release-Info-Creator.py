#!python3

import base64
import datetime
import json
import os
import pyperclip
import re
import requests
import subprocess
import sys
from PIL import Image

ENDPOINT_IMGBB = 'https://api.imgbb.com/1/upload'
ENDPOINT_PTPIMG = 'http://ptpimg.me/upload.php'

MEDIAINFO_COMPLETE_NAME_RE = r'(Complete name *:).+'
DAR_RE = r'Display aspect ratio *: (\d+(?:\.\d+)?):(\d+)'
HEIGHT_RE = r'Height *: (\d+) pixels'
WIDTH_RE = r'Width *: (\d+) pixels'

VIDEO_FILE_TYPES = ('.mkv', '.avi', '.mp4', '.ts')
CLEAR_FN = 'cls' if os.name == 'nt' else 'clear'

IMAGE_HOSTS = ['IMGBB', 'PTPIMG']
SETTINGS_JSON_NAME = 'Release-Info-Creator.json'
SETTINGS = {}


class ReleaseInfo:
    def __init__(self, main_folder_path):
        self.main_folder_path = main_folder_path
        self.release_type = ''
        self.main_files = []
        self.media_infos = []

    def GetCompleteMediaInfo(self):
        relevant_files = self._GetRelevantVideoFiles()

        for video_file in relevant_files:
            base_video_name = os.path.basename(video_file)
            mediainfo = subprocess.check_output(f'mediainfo "{video_file}"', shell=True).decode()
            mediainfo = re.sub(MEDIAINFO_COMPLETE_NAME_RE, fr'\1 {base_video_name}', mediainfo)
            mediainfo = mediainfo.replace('\r\n', '\n')

            self.media_infos.append('[mediainfo]\n' + mediainfo.strip() + '\n[/mediainfo]\n\n')

        if self.release_type == 'DVD':
            return '[size=4][b]' + os.path.basename(self.main_folder_path) + '[/b][/size]\n\n' + ''.join(self.media_infos)
        return ''.join(self.media_infos)

    def _GetRelevantVideoFiles(self):
        if os.path.isfile(self.main_folder_path) and self.main_folder_path.endswith(VIDEO_FILE_TYPES):
            self.main_files = [self.main_folder_path]
            return [self.main_folder_path]
        
        assert os.path.isdir(self.main_folder_path), 'Input path is not a folder or a file of relevant video type' + ', '.join(VIDEO_FILE_TYPES)

        if os.path.isdir(os.path.join(self.main_folder_path, 'VIDEO_TS')):
            self.release_type = 'DVD'
            dvd_info = DVDAnalyzer(self.main_folder_path)
            ifo_filepath = dvd_info.GetIFOfile()
            self.main_files = dvd_info.GetMainVobFiles()
            vob_filepath = self.main_files[0]

            return [ifo_filepath, vob_filepath]
        else:
            self.release_type = 'single'
            video_files = [os.path.join(self.main_folder_path, f) for f in os.listdir(self.main_folder_path) if f.endswith(VIDEO_FILE_TYPES)]
            largest_filepath = GetLargestFile(video_files)
            self.main_files = [largest_filepath]

            return [largest_filepath]

class DVDAnalyzer:
    def __init__(self, main_folder_path):
        self.videots_folder_path = os.path.join(main_folder_path, 'VIDEO_TS')

    def GetIFOfile(self):
        ifo_files = [os.path.join(self.videots_folder_path, f) for f in os.listdir(self.videots_folder_path) if f.endswith(('.ifo', '.IFO'))]

        largest_ifo = ifo_files[0]
        largest_size = os.path.getsize(largest_ifo)

        for ifo in ifo_files:
            filesize = os.path.getsize(ifo)
            if filesize > largest_size:
                largest_ifo = ifo
                largest_size = filesize
        return largest_ifo

    def GetMainVobFiles(self):
        vob_files = [os.path.join(self.videots_folder_path, f) for f in os.listdir(self.videots_folder_path) if f.endswith(('.vob', '.VOB'))]
        assert len(vob_files) > 0, 'No VOB files found in VIDEO_TS'

        largest_vob_filepath = GetLargestFile(vob_files)

        main_vob_files = []
        for vob_file in vob_files:
            if os.path.getsize(vob_file)/os.path.getsize(largest_vob_filepath) < 0.9:
                continue
            main_vob_files.append(vob_file)

        main_vob_files.sort()
        return main_vob_files


class ScreenshotsGenerator:
    def __init__(self, rls, n=6):
        self.n = n
        self.param_DAR = ''
        self.main_files = rls.main_files

        if rls.release_type == 'DVD':
            display_aspect_ratio = self._GetDAR(rls.media_infos[0])
            self.param_DAR = f'-vf "scale={display_aspect_ratio}"'
        
    def GenerateScreenshots(self):
        saved_images = []
        timestamp_data = self._GetTimestampData()

        temp_num = 0
        for data in timestamp_data:
            video_filepath = data['path']
            for timestamp in data['timestamps']:
                now = datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S')
                output_file = f'snapshot_{temp_num} {now}'
                output_filepath = os.path.join(SETTINGS['image_save_location'], output_file)

                subprocess.call(
                    fr'ffmpeg -hide_banner -loglevel panic -ss {timestamp} -i "{video_filepath}" -vf "select=gt(scene\,0.01)" {self.param_DAR} -r 1 -frames:v 1 "{output_filepath}.png"',
                    shell=True)
                temp_num += 1

                picture = Image.open(f'{output_filepath}.png')
                picture.save(f'{output_filepath}.jpg', optimize=True, quality=15)

                compressed_size = os.path.getsize(f'{output_filepath}.jpg')
                saved_images.append({'path': output_filepath, 'size': compressed_size})

        return self._Keep_n_largest(saved_images)

    def _Keep_n_largest(self, saved_images):
        for i, _ in enumerate(saved_images):
            for k in range(i + 1, len(saved_images)):
                if saved_images[i]['size'] < saved_images[k]['size']:
                    saved_images[k], saved_images[i] = saved_images[i], saved_images[k]

        for i, file in enumerate(saved_images):
            os.unlink(file['path'] + '.jpg')
            if i >= self.n:
                os.unlink(file['path'] + '.png')

        return [f['path'] + '.png' for f in saved_images[0:self.n]]

    def _GetTimestampData(self):
        main_files_data = self._GetRuntimeData()
        timestamp_data = []

        min_timestamp_secs = int(main_files_data['total_runtime'] * 0.05)
        max_timestamp_secs = int(main_files_data['total_runtime'] * 0.6)
        increase_interval_secs = (max_timestamp_secs - min_timestamp_secs) // self.n

        timestamp = min_timestamp_secs
        num_remaining = self.n
        for filedata in main_files_data['runtime_data']:
            timestamps = []
            while num_remaining > 0 and timestamp < filedata['runtime']:
                timestamps.append(timestamp)
                timestamp += increase_interval_secs
                num_remaining -= 1

            if timestamp > filedata['runtime']:
                timestamp -= int(filedata['runtime'] - 1)
            if timestamps:
                timestamp_data.append({'path': filedata['path'], 'timestamps': timestamps})

        return timestamp_data

    def _GetRuntimeData(self):
        main_files_data = {
            'total_runtime': 0,
            'runtime_data': []
        }

        for video_filepath in self.main_files:
            mediainfo_json = subprocess.check_output(f'mediainfo --Output=JSON "{video_filepath}"', shell=True).decode()
            mediainfo_json = json.loads(mediainfo_json)
            total_runtime_secs = float(mediainfo_json['media']['track'][0]['Duration'])

            main_files_data['total_runtime'] += total_runtime_secs
            main_files_data['runtime_data'].append({'path': video_filepath, 'runtime': total_runtime_secs})

        return main_files_data

    def _GetDAR(self, mediainfo):
        m = re.search(DAR_RE, mediainfo)
        aspect_width = float(m.group(1))
        aspect_height = float(m.group(2))

        pixel_height = int(re.search(HEIGHT_RE, mediainfo).group(1))
        pixel_width = int(re.search(WIDTH_RE, mediainfo).group(1))

        temp_pixel_width = int(pixel_height/aspect_height * aspect_width)

        if temp_pixel_width >= pixel_width:
            pixel_width = temp_pixel_width
        else:
            pixel_height = pixel_width/aspect_width * aspect_height
            pixel_height = int(pixel_height)

        return f'{pixel_width}:{pixel_height}'


class ImageUploader:
    def __init__(self, images, host=None):
        assert host is not None, 'Error: No host has been chosen'
        assert SETTINGS[host + '_KEY'], f'Error: No API key has been set for {host}'

        self.host = host
        self.images = images
        self.image_urls = ''

    def GetImageURLs(self):
        return self.image_urls

    def Upload(self):
        if self.host == 'PTPIMG':
            self._Upload_PTPIMG()
        elif self.host == 'IMGBB':
            self._Upload_IMGBB()

    def _Upload_IMGBB(self):
        for i, image in enumerate(self.images):
            now = datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S')
            with open(image, 'rb') as f:
                formdata = {
                    'key': SETTINGS['IMGBB_KEY'], 
                    'image': base64.b64encode(f.read()),
                    'name': f'{i}_snapshot {now}'
                }

                resp = requests.post(url=ENDPOINT_IMGBB, data=formdata)
            resp_json = json.loads(resp.text)
            if resp_json.get('status_code', None) is not None:
                print('POST request error ', resp_json['status_code'], ', ', resp_json['status_txt'], ', ', resp_json['error']['message'])
                exit()

            direct_url = resp_json['data']['url']
            self.image_urls += direct_url + '\n'

    def _Upload_PTPIMG(self):
        for i, image in enumerate(self.images):
            now = datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S')
            image_basename = os.path.basename(image)
            with open(image, 'rb') as f:
                formdata = {'api_key': SETTINGS['PTPIMG_KEY']}
                files = { ('file-upload[0]', (image_basename, f, 'image/png')) }

                resp = requests.post(url=ENDPOINT_PTPIMG, files=files, data=formdata)
                resp = json.loads(resp.text)

                image_id = resp[0]['code']
                direct_url = f'https://ptpimg.me/{image_id}.png'
                self.image_urls += direct_url + '\n'


def main():
    global SETTINGS
    SETTINGS = LoadSettings()
    preferred_host = GetHostPreference()

    assert len(sys.argv) > 1, 'Error, need input file'

    print('  Getting media info(s)')
    rls = ReleaseInfo(os.path.abspath(sys.argv[1]))
    release_info = rls.GetCompleteMediaInfo()

    print('  Generating screenshots')
    screenshot_gen = ScreenshotsGenerator(rls, n=6)
    images = screenshot_gen.GenerateScreenshots()

    print('  Uploading images')
    uploader = ImageUploader(images, host=preferred_host)
    uploader.Upload()
    image_urls = uploader.GetImageURLs()

    pyperclip.copy(release_info + image_urls)
    print('Mediainfo(s) + image URLs pasted to clipboard')
    input('\nPress Enter to close')


def GetLargestFile(files):
    largest_filepath = files[0]
    largest_filesize = os.path.getsize(files[0])

    for file in files:
        filesize = os.path.getsize(file)
        if filesize > largest_filesize:
            largest_filepath = file
            largest_filesize = filesize

    return largest_filepath


def LoadSettings():
    script_dir = os.path.dirname(sys.argv[0])
    settings_json_location = os.path.join(script_dir, SETTINGS_JSON_NAME)
    try:
        with open(settings_json_location, 'r', encoding='utf8') as f:
            settings = json.load(f)
        return settings
    except Exception:
        return QueryNewSettings(settings_json_location)


def GetHostPreference():
    bad_choice_msg = ''
    max_num = len(IMAGE_HOSTS)

    while True:
        print(f'{bad_choice_msg}Choose an image host to use: ')
        for i, image_host in enumerate(IMAGE_HOSTS):
            print(f'  {i + 1}: {image_host}')
        print('')
        choice = input(f'Your choice (between {1} and {max_num}): ')
        if not choice.isnumeric() or not ( int(choice) >= 1 and int(choice) <= max_num ):
            bad_choice_msg = 'Bad choice. Try again.\n'
            subprocess.call(CLEAR_FN, shell=True)
            continue
        else:
            n = int(choice)
            return IMAGE_HOSTS[n - 1]


def QueryNewSettings(settings_json_location):
    settings = {}
    retry = True

    while retry:
        print(f'Input your settings to be saved into {SETTINGS_JSON_NAME}')
        for image_host in IMAGE_HOSTS:
            key_name = image_host + '_KEY'
            settings[key_name] = input(f'Input your {image_host} key: ')
        settings['image_save_location'] = input('Input the image save directory: ')

        print('\nYour Settings:\n' + json.dumps(settings, indent=4), '\n')
        retry = True if input('Edit these settings [Y/n]? ').lower() == 'y' else False
        subprocess.call(CLEAR_FN, shell=True)

    with open(settings_json_location, 'w', encoding='utf8') as f:
        json.dump(settings, f, indent=4)

    return settings


if __name__ == '__main__':
    main()
