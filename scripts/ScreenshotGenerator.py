import datetime
import json
import os
import subprocess
from PIL import Image

from Settings import Settings


class ScreenshotGenerator:
    def __init__(self, n_images=6):
        self.n_images = n_images
        self.display_width = 0
        self.display_height = 0
        self.param_DAR = ''

    def generate_screenshots(self, rls):
        saved_images = []
        timestamp_data = self._get_timestamp_data(rls)

        self.display_width, self.display_height = self._get_display_dimensions(rls)
        self.param_DAR = f'-vf "scale={self.display_width}:{self.display_height}"'

        temp_num = 0
        for data in timestamp_data:
            video_filepath = data['path']
            for timestamp in data['timestamps']:
                now = datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S')
                output_file = f'snapshot_{temp_num} {now}'
                output_filepath = os.path.join(Settings.paths['image_save_location'], output_file)

                args = r'"{ffmpeg_bin_location}" -hide_banner -loglevel panic -ss {timestamp} -i "{video_filepath}" ' \
                       r'-vf "select=gt(scene\,0.01)" {param_DAR} -r 1 -frames:v 1 "{output_filepath}.png"'.format(
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
            args = '"{mediainfo_bin_location}" --Output=JSON "{video_filepath}"'.format(
                mediainfo_bin_location=Settings.paths['mediainfo_bin_path'],
                video_filepath=video_filepath
            )
            mediainfo_json = subprocess.check_output(args, shell=True).decode()
            mediainfo_json = json.loads(mediainfo_json)
            total_runtime_secs = float(mediainfo_json['media']['track'][0]['Duration'])

            main_files_data['total_runtime'] += total_runtime_secs
            main_files_data['runtime_data'].append({'path': video_filepath, 'runtime': total_runtime_secs})

        return main_files_data

    def _get_display_dimensions(self, rls):
        mediainfo_json = {}

        if rls.release_type == 'dvd':
            mediainfo_json = rls.primary_ifo_info['mediainfo_json']
        else:
            args = '"{mediainfo_bin_location}" --Output=JSON "{info_file}"'.format(
                mediainfo_bin_location=Settings.paths['mediainfo_bin_path'],
                info_file=rls.main_video_files[0]
            )
            mediainfo_json = subprocess.check_output(args, shell=True).decode()
            mediainfo_json = json.loads(mediainfo_json)

        video_info = self._get_video_data(mediainfo_json)

        pixel_width = display_width = int(video_info['Width'])
        pixel_height = display_height = int(video_info['Height'])
        if float(video_info['PixelAspectRatio']) == 1:
            return pixel_width, pixel_height

        dar_float = float(video_info['DisplayAspectRatio'])
        temp_display_width = round(pixel_height * dar_float)
        if temp_display_width >= pixel_width:
            display_width = temp_display_width
        else:
            display_height = round(pixel_width / dar_float)

        return display_width, display_height

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
