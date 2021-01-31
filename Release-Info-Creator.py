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

VIDEO_FILE_TYPES = ('.mkv', '.avi', '.mp4', '.ts')
VOB_EXTS = ('.vob', 'VOB')
IFO_EXTS = ('.ifo', '.IFO')
CLEAR_FN = 'cls' if os.name == 'nt' else 'clear'


class Settings:
    settings_file_name = 'Release-Info-Creator.json'
    settings_file_path = os.path.join( os.path.dirname(os.path.abspath(__file__)), settings_file_name )
    paths = {}
    preferred_host_name = ''
    image_hosts_skeleton = [
        {
            'name': 'ptpimg',
            'api_key': '',
            'default': False
        },
        {
            'name': 'imgbb',
            'api_key': '',
            'default': False
        },
        {
            'name': 'hdbimg',
            'username': '',
            'api_key': '',
            'default': False
        },
        {
            'name': 'ahdimg',
            'api_key': '',
            'default': False
        }
    ]
    image_hosts = image_hosts_skeleton

    @staticmethod
    def load_settings():
        try:
            with open(Settings.settings_file_path, 'r', encoding='utf8') as f:
                settings = json.load(f)
            Settings.paths = settings['paths']
            Settings.image_hosts = settings['image_hosts']
            Settings._append_missing_image_hosts()
        except FileNotFoundError:
            Settings._query_new_settings()

    @staticmethod
    def _query_new_settings():
        retry = True

        while retry:
            print(f'\nInput your settings to be saved into {Settings.settings_file_name}')
            Settings._query_image_host_info()
            Settings._query_paths()

            subprocess.run(CLEAR_FN, shell=True)
            print('\nYour Settings:\n' + json.dumps(Settings._get_settings_dict(), indent=4) + '\n')

            retry = False if input('Use these settings [Y/n]?').lower() == 'y' else True
            subprocess.run(CLEAR_FN, shell=True)

        with open(Settings.settings_file_path, 'w', encoding='utf8') as f:
            json.dump(Settings._get_settings_dict(), f, indent=4)

    @staticmethod
    def _query_image_host_info():
        Settings.image_hosts = Settings.image_hosts_skeleton
        # to check if user has chosen an image host as their default
        is_set_default = False

        for i, _ in enumerate(Settings.image_hosts_skeleton):
            host_name = Settings.image_hosts[i]['name']
            Settings.image_hosts[i]['api_key'] = input(f'\nInput the API key for {host_name} (to skip, leave blank): ')

            if host_name == 'hdbimg':
                Settings.image_hosts[i]['username'] = input(f'Input your username for {host_name} (to skip, leave blank): ')

            # Query for default if api key is is given a value
            if Settings.image_hosts[i]['api_key'].strip() != '' and not is_set_default:
                Settings.image_hosts[i]['default'] = True if input(
                    f'Set {host_name} as the default [Y/n]? ').lower() == 'y' else False
                if Settings.image_hosts[i]['default']:
                    is_set_default = True

    @staticmethod
    def _query_paths():
        Settings.paths = {}
        Settings.paths['image_save_location'] = input('\nInput the image save directory: ').strip()
        Settings.paths['ffmpeg_bin_path'] = input('Input the full path for the ffmpeg binary: ').strip()
        Settings.paths['mediainfo_bin_path'] = input('Input the full path for the mediainfo binary: ').strip()

    @staticmethod
    def _get_settings_dict():
        return { 'paths': Settings.paths, 'image_hosts': Settings.image_hosts }

    # Query preferred host from user.
    @staticmethod
    def get_preferred_host():
        default_host_name = Settings._get_default_host()
        # If image host has 'default' flag set, skip query and use that
        if default_host_name is not None:
            return default_host_name

        bad_choice_msg = ''
        max_num = len(Settings.image_hosts_skeleton)

        while True:
            print(f'{bad_choice_msg}Choose an image host to use: ')

            for i, image_host in enumerate(Settings.image_hosts_skeleton):
                host_name = image_host['name']

                # will be printed in the console-printed options menu to indicate if the image host key is not set
                set_str = '    (not set)' if not Settings.get_key(host_name) else ''
                print(f'  {i + 1}: {host_name}{set_str}')

            choice = input(f'\nYour choice (between {1} and {max_num}): ')
            if not choice.isnumeric() or not ( int(choice) >= 1 and int(choice) <= max_num ):
                bad_choice_msg = 'Bad choice. Try again.\n'
                subprocess.run(CLEAR_FN, shell=True)
                continue
            else:
                return Settings.image_hosts_skeleton[int(choice) - 1]

    @staticmethod
    def _get_default_host():
        for image_host in Settings.image_hosts:
            if image_host['default']:
                return image_host['name']
        return None

    @staticmethod
    def _append_missing_image_hosts():
        if len(Settings.image_hosts) == len(Settings.image_hosts_skeleton):
            return

        image_host_names_from_file = [d['name'] for d in Settings.image_hosts]

        for image_host in Settings.image_hosts_skeleton:
            if image_host['name'] not in image_host_names_from_file:
                Settings.image_hosts.append(image_host)

        with open(Settings.settings_file_path, 'w', encoding='utf8') as f:
            json.dump(Settings._get_settings_dict(), f, indent=4)

    @staticmethod
    def query_options():
        pass

    @staticmethod
    def get_key(host_name):
        for image_host in Settings.image_hosts:
            if image_host['name'] == host_name:
                return image_host['api_key']
        return None


class ReleaseInfo:
    mediainfo_complete_name_re = r'(Complete name *:).+'

    def __init__(self, input_path):
        self.input_path = input_path
        self.release_type = ''
        self.primary_ifo_info = ''
        self.main_video_files = []
        self.media_infos = []

    def get_complete_mediainfo(self):
        relevant_files = self._get_relevant_files()
        header = ''
        if self.release_type == 'dvd': header = '[size=4][b]' + os.path.basename(self.input_path) + '[/b][/size]\n\n'

        for file in relevant_files:
            base_video_name = os.path.basename(file)

            args = '"{mediainfo_bin_location}" "{file}"'.format(
                mediainfo_bin_location=Settings.paths['mediainfo_bin_path'], 
                file=file
                )
            mediainfo = subprocess.check_output(args, shell=True).decode()
            mediainfo = re.sub(ReleaseInfo.mediainfo_complete_name_re, fr'\1 {base_video_name}', mediainfo)
            mediainfo = mediainfo.replace('\r\n', '\n')

            self.media_infos.append('[mediainfo]\n' + mediainfo.strip() + '\n[/mediainfo]\n\n')

        return header + ''.join(self.media_infos)

    def _get_relevant_files(self):
        # check if user-set path is of a proper video type
        if os.path.isfile(self.input_path) and self.input_path.endswith(VIDEO_FILE_TYPES):
            self.release_type = 'single'
            self.main_video_files.append(self.input_path)
            return [self.input_path]
        
        assert os.path.isdir(self.input_path), 'Input path is not a DVD folder or a file of relevant video type: ' + ', '.join(VIDEO_FILE_TYPES)

        # check if user-set path contains folder 'VIDEO_TS'
        if os.path.isdir(os.path.join(self.input_path, 'VIDEO_TS')):
            self.release_type = 'dvd'

            dvd_info = DvdAnalyder(self.input_path)
            self.primary_ifo_info = dvd_info.get_primary_ifo_info()
            self.main_video_files = dvd_info.get_main_vob_files()

            return [ self.primary_ifo_info['path'], self.main_video_files[0] ]
        else:
            self.release_type = 'single'
            video_files = [os.path.join(self.input_path, f) for f in os.listdir(self.input_path) if f.endswith(VIDEO_FILE_TYPES)]
            largest_filepath = get_largest_file(video_files)
            self.main_video_files = [largest_filepath]

            return [largest_filepath]


class DvdAnalyder:
    def __init__(self, input_path):
        self.videots_folder_path = os.path.join(input_path, 'VIDEO_TS')

    def get_primary_ifo_info(self):
        """
        Gathers mediainfo on all ifo files. Returns ifo file with longest runtime, which indicates the total runtime of movie
        :return: file path (str)
        """
        ifo_files = [os.path.join(self.videots_folder_path, f) for f in os.listdir(self.videots_folder_path) if f.endswith(IFO_EXTS)]

        # Preliminary choosing.
        primary_ifo_file = ifo_files[0]
        longest_duration = 0

        for ifo_file in ifo_files:
            args = '{mediainfo_bin_location} --Output=JSON "{ifo_file}"'.format(
                mediainfo_bin_location=Settings.paths['mediainfo_bin_path'],
                ifo_file=ifo_file
                )
            mediainfo_json = subprocess.check_output(args, shell=True).decode()
            mediainfo_json = json.loads(mediainfo_json)

            for track in mediainfo_json['media']['track']:
                if track['@type'] == 'General':
                    if float(track['Duration']) > longest_duration:
                        longest_duration = float(track['Duration'])
                        primary_ifo_file = ifo_file
                    continue
        return {'path': primary_ifo_file, 'mediainfo_json': mediainfo_json}

    def get_main_vob_files(self):
        """
        Get primary movie VOB files (ie. largest-size VOB files), which are similar in size
        :return: file path (str)
        """
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
                output_filepath = os.path.join(Settings.paths['image_save_location'], output_file)

                args = r'{ffmpeg_bin_location} -hide_banner -loglevel panic -ss {timestamp} -i "{video_filepath}" -vf "select=gt(scene\,0.01)" {param_DAR} -r 1 -frames:v 1 "{output_filepath}.png"'.format(
                    ffmpeg_bin_location=Settings.paths['ffmpeg_bin_path'], 
                    timestamp=timestamp, 
                    video_filepath=video_filepath, 
                    param_DAR=self.param_DAR, 
                    output_filepath=output_filepath
                    )
                subprocess.run(args, shell=True)
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
                mediainfo_bin_location=Settings.paths['mediainfo_bin_path'], 
                video_filepath=video_filepath
                )
            mediainfo_json = subprocess.check_output(args, shell=True).decode()
            mediainfo_json = json.loads(mediainfo_json)
            total_runtime_secs = float(mediainfo_json['media']['track'][0]['Duration'])

            main_files_data['total_runtime'] += total_runtime_secs
            main_files_data['runtime_data'].append({'path': video_filepath, 'runtime': total_runtime_secs})

        return main_files_data

    def _get_dar(self, rls):
        mediainfo_json = {}

        if rls.release_type == 'dvd':
            mediainfo_json = rls.primary_ifo_info['mediainfo_json']
        else:
            args = '{mediainfo_bin_location} --Output=JSON "{info_file}"'.format(
                mediainfo_bin_location=Settings.paths['mediainfo_bin_path'],
                info_file=rls.main_video_files[0]
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
    def __init__(self, images, host_name=None):
        assert host_name is not None, 'Error: No image host has been chosen'

        self.api_key = Settings.get_key(host_name)
        assert self.api_key, f'Error: No API key has been set for {host_name}'

        self.host_name = host_name
        self.images = images
        self.image_urls = ''

    def get_image_urls(self):
        return self.image_urls

    def upload(self):
        if self.host_name == 'ptpimg':
            self._upload_ptpimg()
        elif self.host_name == 'imgbb':
            self._upload_imgbb()

    def _upload_imgbb(self):
        for i, image in enumerate(self.images):
            now = datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S')
            with open(image, 'rb') as f:
                formdata = {
                    'key': self.api_key, 
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
                formdata = {'api_key': self.api_key}
                files = { ('file-upload[0]', (image_basename, f, 'image/png')) }

                resp = requests.post(url=ENDPOINT_PTPIMG, files=files, data=formdata)
                resp = json.loads(resp.text)

                image_id = resp[0]['code']
                direct_url = f'https://ptpimg.me/{image_id}.png'
                self.image_urls += direct_url + '\n'


def main():
    if len(sys.argv) == 1:
        Settings.query_options()
        exit()
    Settings.load_settings()
    preferred_host = Settings.get_preferred_host()

    assert len(sys.argv) > 1, 'Error, need input file'

    subprocess.run(CLEAR_FN, shell=True)

    print(f'Image host "{preferred_host}" will be used for uploading\n')
    print('Gathering media info')
    rls = ReleaseInfo( os.path.abspath(sys.argv[1]) )
    release_info = rls.get_complete_mediainfo()

    print('Generating screenshots')
    screenshot_gen = ScreenshotGenerator(n_images=6)
    images = screenshot_gen.generate_screenshots(rls)

    print(f'Uploading images to {preferred_host}')
    uploader = ImageUploader(images, host_name=preferred_host)
    uploader.upload()
    image_urls = uploader.get_image_urls()

    pyperclip.copy(release_info + image_urls)
    print('\nMediainfo + image URLs copied to clipboard')
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


if __name__ == '__main__':
    main()
