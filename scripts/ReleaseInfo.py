import os
import re
import subprocess

import Helper
from Settings import Settings
from DvdAnalyzer import DvdAnalyzer

VIDEO_FILE_TYPES = ('.mkv', '.avi', '.mp4', '.ts')

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

        assert os.path.isdir(
            self.input_path), 'Input path is not a DVD folder or a file of relevant video type: ' + ', '.join(
            VIDEO_FILE_TYPES)

        # check if user-set path contains folder 'VIDEO_TS'
        if os.path.isdir(os.path.join(self.input_path, 'VIDEO_TS')):
            self.release_type = 'dvd'

            dvd_info = DvdAnalyzer(self.input_path)
            self.primary_ifo_info = dvd_info.get_primary_ifo_info()
            self.main_video_files = dvd_info.get_main_vob_files()

            return [self.primary_ifo_info['path'], self.main_video_files[0]]
        else:
            self.release_type = 'single'
            video_files = [os.path.join(self.input_path, f) for f in os.listdir(self.input_path) if
                           f.endswith(VIDEO_FILE_TYPES)]
            largest_filepath = Helper.get_largest_file(video_files)
            self.main_video_files = [largest_filepath]

            return [largest_filepath]
