import os
import Helper

VOB_EXTS = ('.vob', '.VOB')
IFO_EXTS = ('.ifo', '.IFO')


class DvdAnalyzer:
    def __init__(self, input_path):
        self.video_ts_folder_path = os.path.join(input_path, 'VIDEO_TS')

    def get_primary_ifo_info(self) -> dict:
        """
        Gathers mediainfo on all IFO files and determines which is the primary IFO
        :return dict: Contains the path of the primary IFO file, as well as its mediainfo
        """
        ifo_files = [os.path.join(self.video_ts_folder_path, f)
                     for f in os.listdir(self.video_ts_folder_path) if f.endswith(IFO_EXTS)]

        # Preliminary choosing; pick first IFO file as the primary
        primary_ifo_file = ifo_files[0]
        primary_mediainfo_json = {}
        longest_duration = 0

        for ifo_file in ifo_files:
            mediainfo_json = Helper.get_mediainfo_json(ifo_file)

            for track in mediainfo_json['media']['track']:
                if track['@type'] == 'General':
                    if track.get('Duration') is None:
                        continue
                    if float(track['Duration']) > longest_duration:
                        longest_duration = float(track['Duration'])
                        primary_ifo_file = ifo_file
                        primary_mediainfo_json = mediainfo_json
                    continue
        return {'path': primary_ifo_file, 'mediainfo_json': primary_mediainfo_json}

    def get_main_vob_files(self) -> list:
        """
        Get primary movie VOB files (ie. largest-size VOB files), which are similar in size
        :return list<str>: File paths of the VOB files found
        """
        vob_files = [os.path.join(self.video_ts_folder_path, f)
                     for f in os.listdir(self.video_ts_folder_path) if f.endswith(VOB_EXTS)]
        assert len(vob_files) > 0, 'No VOB files found in VIDEO_TS'

        largest_vob_filepath = Helper.get_largest_file(vob_files)

        main_vob_files = []
        for vob_file in vob_files:
            if os.path.getsize(vob_file)/os.path.getsize(largest_vob_filepath) < 0.9:
                continue
            main_vob_files.append(vob_file)

        main_vob_files.sort()
        return main_vob_files
