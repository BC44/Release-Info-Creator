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
import time
from PIL import Image

ENDPOINT_IMGBB = 'https://api.imgbb.com/1/upload'
ENDPOINT_PTPIMG = 'http://ptpimg.me/upload.php'

MEDIAINFO_COMPLETE_NAME_RE = r'(Complete name *:).+'
VIDEO_FILE_TYPES = ('.mkv', '.avi', '.mp4', '.ts')
VOB_EXTS = ('.vob', 'VOB')
IFO_EXTS = ('.ifo', '.IFO')
CLEAR_FN = 'cls' if os.name == 'nt' else 'clear'

IMAGE_HOSTS = ['IMGBB', 'PTPIMG']
SETTINGS_JSON_NAME = 'Release-Info-Creator.json'

SETTINGS_KEYS = ['IMGBB_KEY', 'PTPIMG_KEY', 'image_save_location', 'ffmpeg_bin_location', 'mediainfo_bin_location']
SETTINGS = {}

class ReleaseInfo:
    def __init__(self, user_set_path):
        self.user_set_path = user_set_path
        self.release_type = ''
        self.main_ifo_file = ''
        self.main_video_files = []
        self.media_infos = []

    def get_complete_mediainfo(self):
        relevant_files = self._get_relevant_files()
        header = ''
        if self.release_type == 'dvd': header = '[size=4][b]' + os.path.basename(self.user_set_path) + '[/b][/size]\n\n'

        for file in relevant_files:
            base_video_name = os.path.basename(file)

            args = '"{mediainfo_bin_location}" "{file}"'.format(
                mediainfo_bin_location=SETTINGS['mediainfo_bin_location'], 
                file=file
                )
            mediainfo = subprocess.check_output(args, shell=True).decode()
            mediainfo = re.sub(MEDIAINFO_COMPLETE_NAME_RE, fr'\1 {base_video_name}', mediainfo)
            mediainfo = mediainfo.replace('\r\n', '\n')

            self.media_infos.append('[mediainfo]\n' + mediainfo.strip() + '\n[/mediainfo]\n\n')

        return header + ''.join(self.media_infos)

    def _get_relevant_files(self):
        # check if user-set path is of a proper video type
        if os.path.isfile(self.user_set_path) and self.user_set_path.endswith(VIDEO_FILE_TYPES):
            self.release_type = 'single'
            self.main_video_files.append(self.user_set_path)
            return [self.user_set_path]
        
        assert os.path.isdir(self.user_set_path), 'Input path is not a folder or a file of relevant video type' + ', '.join(VIDEO_FILE_TYPES)

        # check if user-set path contains folder 'VIDEO_TS'
        if os.path.isdir(os.path.join(self.user_set_path, 'VIDEO_TS')):
            self.release_type = 'dvd'

            dvd_info = DvdAnalyder(self.user_set_path)
            self.main_ifo_file = dvd_info.get_ifo_file()
            self.main_video_files = dvd_info.get_main_vob_files()

            return [ self.main_ifo_file, self.main_video_files[0] ]
        else:
            self.release_type = 'single'
            video_files = [os.path.join(self.user_set_path, f) for f in os.listdir(self.user_set_path) if f.endswith(VIDEO_FILE_TYPES)]
            largest_filepath = get_largest_file(video_files)
            self.main_video_files = [largest_filepath]

            return [largest_filepath]

class DvdAnalyder:
    def __init__(self, user_set_path):
        self.videots_folder_path = os.path.join(user_set_path, 'VIDEO_TS')

    def get_ifo_file(self):
        ifo_files = [os.path.join(self.videots_folder_path, f) for f in os.listdir(self.videots_folder_path) if f.endswith(IFO_EXTS)]

        largest_ifo = ifo_files[0]
        largest_size = os.path.getsize(largest_ifo)

        for ifo in ifo_files:
            filesize = os.path.getsize(ifo)
            if filesize > largest_size:
                largest_ifo = ifo
                largest_size = filesize
        return largest_ifo

    def get_main_vob_files(self):
        vob_files = [os.path.join(self.videots_folder_path, f) for f in os.listdir(self.videots_folder_path) if f.endswith(VOB_EXTS)]
        assert len(vob_files) > 0, 'No VOB files found in VIDEO_TS'

        largest_vob_filepath = get_largest_file(vob_files)

        main_vob_files = []
        for vob_file in vob_files:
            if os.path.getsize(vob_file)/os.path.getsize(largest_vob_filepath) < 0.9:
                continue
            main_vob_files.append(vob_file)

        main_vob_files.sort()
        return main_vob_files


class ScreenshotGenerator:
    def __init__(self, n_images=6):
        self.n_images = n_images
        self.param_DAR = ''
        
    def generate_screenshots(self, rls):
        saved_images = []
        timestamp_data = self._get_timestamp_data(rls)

        display_aspect_ratio = self._get_dar(rls)
        self.param_DAR = f'-vf "scale={display_aspect_ratio}"'

        temp_num = 0
        for data in timestamp_data:
            video_filepath = data['path']
            for timestamp in data['timestamps']:
                now = datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S')
                output_file = f'snapshot_{temp_num} {now}'
                output_filepath = os.path.join(SETTINGS['image_save_location'], output_file)

                args = r'{ffmpeg_bin_location} -hide_banner -loglevel panic -ss {timestamp} -i "{video_filepath}" -vf "select=gt(scene\,0.01)" {param_DAR} -r 1 -frames:v 1 "{output_filepath}.png"'.format(
                    ffmpeg_bin_location=SETTINGS['ffmpeg_bin_location'], 
                    timestamp=timestamp, 
                    video_filepath=video_filepath, 
                    param_DAR=self.param_DAR, 
                    output_filepath=output_filepath
                    )
                subprocess.call(args, shell=True)
                temp_num += 1

                picture = Image.open(f'{output_filepath}.png')
                picture.save(f'{output_filepath}.jpg', optimize=True, quality=15)

                compressed_size = os.path.getsize(f'{output_filepath}.jpg')
                saved_images.append({'path': output_filepath, 'size': compressed_size})

        return self._keep_n_largest(saved_images)

    def _get_timestamp_data(self, rls):
        main_files_data = self._get_runtime_data(rls)
        timestamp_data = []

        min_timestamp_secs = int(main_files_data['total_runtime'] * 0.05)
        max_timestamp_secs = int(main_files_data['total_runtime'] * 0.6)
        increase_interval_secs = (max_timestamp_secs - min_timestamp_secs) // self.n_images

        timestamp = min_timestamp_secs
        num_remaining = self.n_images
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

    def _get_runtime_data(self, rls):
        main_files_data = {
            'total_runtime': 0,
            'runtime_data': []
        }

        for video_filepath in rls.main_video_files:
            args = '{mediainfo_bin_location} --Output=JSON "{video_filepath}"'.format(
                mediainfo_bin_location=SETTINGS['mediainfo_bin_location'], 
                video_filepath=video_filepath
                )
            mediainfo_json = subprocess.check_output(args, shell=True).decode()
            mediainfo_json = json.loads(mediainfo_json)
            total_runtime_secs = float(mediainfo_json['media']['track'][0]['Duration'])

            main_files_data['total_runtime'] += total_runtime_secs
            main_files_data['runtime_data'].append({'path': video_filepath, 'runtime': total_runtime_secs})

        return main_files_data

    def _get_dar(self, rls):
        if rls.release_type == 'dvd':
            info_file = rls.main_ifo_file
        else:
            info_file = rls.main_video_files[0]

        args = '{mediainfo_bin_location} --Output=JSON "{info_file}"'.format(
            mediainfo_bin_location=SETTINGS['mediainfo_bin_location'], 
            info_file=info_file
            )
        mediainfo_json = subprocess.check_output(args, shell=True).decode()
        mediainfo_json = json.loads(mediainfo_json)
        video_info = self._get_video_data(mediainfo_json)

        pixel_width = display_width = int(video_info['Width'])
        pixel_height = display_height = int(video_info['Height'])
        if float(video_info['PixelAspectRatio']) == 1:
            return f'{pixel_width}:{pixel_height}'

        dar_float = float(video_info['DisplayAspectRatio'])
        temp_display_width = round(pixel_height * dar_float)
        if temp_display_width >= pixel_width:
            display_width = temp_display_width
        else:
            display_height = round(pixel_width / dar_float)

        return f'{display_width}:{display_height}'

    def _keep_n_largest(self, saved_images):
        for i, _ in enumerate(saved_images):
            for k in range(i + 1, len(saved_images)):
                if saved_images[i]['size'] < saved_images[k]['size']:
                    saved_images[k], saved_images[i] = saved_images[i], saved_images[k]

        for i, file in enumerate(saved_images):
            os.unlink(file['path'] + '.jpg')
            if i >= self.n_images:
                os.unlink(file['path'] + '.png')

        return [f['path'] + '.png' for f in saved_images[0:self.n_images]]

    def _get_video_data(self, mediainfo_json):
        for track in mediainfo_json['media']['track']:
            if track['@type'] == 'Video':
                return track
        return None


class ImageUploader:
    def __init__(self, images, host=None):
        assert host is not None, 'Error: No host has been chosen'
        assert SETTINGS[host + '_KEY'], f'Error: No API key has been set for {host}'

        self.host = host
        self.images = images
        self.image_urls = ''

    def get_image_urls(self):
        return self.image_urls

    def upload(self):
        if self.host == 'PTPIMG':
            self._upload_ptpimg()
        elif self.host == 'IMGBB':
            self._upload_imgbb()

    def _upload_imgbb(self):
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

    def _upload_ptpimg(self):
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
    SETTINGS = load_settings()
    preferred_host = get_host_preference()

    assert len(sys.argv) > 1, 'Error, need input file'

    subprocess.call(CLEAR_FN, shell=True)
    print('Getting media info(s)')
    rls = ReleaseInfo(os.path.abspath(sys.argv[1]))
    release_info = rls.get_complete_mediainfo()

    print('Generating screenshots')
    screenshot_gen = ScreenshotGenerator(n_images=6)
    images = screenshot_gen.generate_screenshots(rls)

    print('Uploading images')
    uploader = ImageUploader(images, host=preferred_host)
    uploader.upload()
    image_urls = uploader.get_image_urls()

    pyperclip.copy(release_info + image_urls)
    print('\nMediainfo(s) + image URLs copied to clipboard')
    time.sleep(5)


def get_largest_file(files):
    largest_filepath = files[0]
    largest_filesize = os.path.getsize(files[0])

    for file in files:
        filesize = os.path.getsize(file)
        if filesize > largest_filesize:
            largest_filepath = file
            largest_filesize = filesize

    return largest_filepath


def load_settings():
    script_dir = os.path.dirname(sys.argv[0])
    settings_json_location = os.path.join(script_dir, SETTINGS_JSON_NAME)

    try:
        with open(settings_json_location, 'r', encoding='utf8') as f:
            settings = json.load(f)
        if not is_missing_settings(settings):
            return settings
        else:
            return set_missing_settings(settings, settings_json_location)
    except Exception:
        return query_new_settings(settings_json_location)


def get_host_preference():
    default_choice = get_default_choice()
    if default_choice is not None:
        return default_choice

    bad_choice_msg = ''
    max_num = len(IMAGE_HOSTS)

    while True:
        print(f'{bad_choice_msg}Choose an image host to use: ')
        for i, image_host in enumerate(IMAGE_HOSTS):
            set_str = '    (not set)' if not SETTINGS[image_host + '_KEY'] else ''
            print(f'  {i + 1}: {image_host}{set_str}')

        choice = input(f'\nYour choice (between {1} and {max_num}): ')
        if not choice.isnumeric() or not ( int(choice) >= 1 and int(choice) <= max_num ):
            bad_choice_msg = 'Bad choice. Try again.\n'
            subprocess.call(CLEAR_FN, shell=True)
            continue
        else:
            choice = int(choice)
            return IMAGE_HOSTS[choice - 1]


def get_default_choice():
    last_available_host = ''
    for image_host in IMAGE_HOSTS:
        current_key = SETTINGS[image_host + '_KEY']
        if current_key and last_available_host:
            return None
        if current_key:
            last_available_host = image_host
    return last_available_host


def is_missing_settings(settings):
    for key in SETTINGS_KEYS:
        if settings.get(key, None) is None:
            return True
    return False


def set_missing_settings(settings, settings_json_location):
    for key in SETTINGS_KEYS:
        if settings.get(key, None) is None:
            settings[key] = input(f'Input the missing value for "{key}": ').strip('"')

    with open(settings_json_location, 'w', encoding='utf8') as f:
        json.dump(settings, f, indent=4)

    subprocess.call(CLEAR_FN, shell=True)
    return settings


def query_new_settings(settings_json_location):
    settings = {}
    retry = True

    while retry:
        print(f'Input your settings to be saved into {SETTINGS_JSON_NAME}')
        for image_host in IMAGE_HOSTS:
            key_name = image_host + '_KEY'
            settings[key_name] = input(f'Input your {image_host} API key (can skip): ')

        settings['image_save_location'] = input('Input the image save directory: ')
        settings['ffmpeg_bin_location'] = input('Input the full path for the ffmpeg binary: ')
        settings['mediainfo_bin_location'] = input('Input the full path for the mediainfo binary: ')

        print('\nYour Settings:\n' + json.dumps(settings, indent=4), '\n')
        retry = True if input('Edit these settings [Y/n]? ').lower() == 'y' else False
        subprocess.call(CLEAR_FN, shell=True)

    with open(settings_json_location, 'w', encoding='utf8') as f:
        json.dump(settings, f, indent=4)

    return settings


if __name__ == '__main__':
    main()
