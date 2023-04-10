import datetime
from typing import Tuple
import Helper
import os
import subprocess
from PIL import Image

from Settings import Settings


class ScreenshotGenerator:
    FFMPEG_SCREENSHOT_ARGS = r'"{ffmpeg_bin_location}" -hide_banner -loglevel panic -ss {timestamp} ' \
                             r'-i "{video_filepath}" -vf "select=gt(scene\,0.01)" {param_DAR} -r 1 ' \
                             r'-frames:v 1 "{output_filepath}"'

    OXIPNG_ARGS = r'"{oxi_bin_location}" -o 2 -s -a {images}'

    def __init__(self, n_images=6):
        """
        :param n_images (int): Number of screenshots to generate; 2 extra images will be generated
        in case some come out dark/blurry;
        """
        self.n_final_images = n_images
        self.n_total_images = n_images + 2
        self.saved_images = []

        self.param_DAR = ''

    def generate_screenshots(self, rls: object) -> list:
        """
        Generate screenshots for file or DVD
        :param rls (ReleaseInfo): Object containing video's/DVD's paths and any already-gathered mediainfo
        :return:
        """

        display_width, display_height = self._get_display_dimensions(rls)
        self.param_DAR = f'-vf "scale={display_width}:{display_height}:flags=full_chroma_int+full_chroma_inp+accurate_rnd+spline" -pix_fmt rgb24'

        if rls.release_type == 'dvd':
            general_info = Helper.get_track(rls.primary_ifo_info['mediainfo_json'], track_type='General')
        else:
            mediainfo_json = Helper.get_mediainfo_json(rls.main_video_files[0])
            general_info = Helper.get_track(mediainfo_json, track_type='General')

        total_runtime_secs = float(general_info['Duration'])
        # first screenshot will be at the 5% mark of the duration
        min_timestamp_secs = total_runtime_secs * 0.05
        # last screenshot should be at the 60% mark of the duration; prevents late-video spoilers
        max_timestamp_secs = total_runtime_secs * 0.6

        screenshot_interval = (max_timestamp_secs - min_timestamp_secs) // self.n_total_images
        current_timestamp = min_timestamp_secs

        # import pdb; pdb.set_trace()
        for video_file in rls.main_video_files:
            next_timestamp = self._take_screenshots(video_file, current_timestamp, screenshot_interval)
            current_timestamp = next_timestamp

        compressed_images = self._create_compressed_images()
        self.saved_images = self._discard_smallest_images(compressed_images)
        if Settings.use_png_optimise: self._optimise_images()

        return self.saved_images

    def _take_screenshots(self, video_file: str, current_timestamp: float, screenshot_interval: float) -> float:
        """
        Take screenshots for a given video file.
        :param video_file (str): path to video file
        :param current_timestamp (float): timestamp at which to take the screenshot
        :param screenshot_interval (float): interval by which to increase the timestamp for the next screenshot
        :return next_timestamp (float): time stamp for the next video; applicable only for DVDs where
                there are multiple VOB files. Screenshots will span throughout several files
        """
        mediainfo_json = Helper.get_mediainfo_json(video_file)
        general_info = Helper.get_track(mediainfo_json, track_type='General')
        duration_seconds = float(general_info.get('Duration'))

        processes: list[subprocess.Popen] = []
        while current_timestamp < duration_seconds and len(self.saved_images) < self.n_total_images:
            image_file, process = self._execute_screenshot(current_timestamp, video_file)
            processes.append(process)
            self.saved_images.append(image_file)
            current_timestamp += screenshot_interval

        for proc in processes:
            proc.wait()

        next_timestamp = current_timestamp - duration_seconds
        return next_timestamp

    def _execute_screenshot(self, timestamp: float, video_file: str) -> str:
        """
        Take a screenshot for video_file at given timestamp
        :param timestamp (float): timestamp at which to take a screenshot
        :param video_file (str): path to video file
        :return output_filepath (str): File path for the resulting PNG screenshot file
        """
        now = datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S')
        output_filename = 'snapshot_{num} {now}.png'.format(num=len(self.saved_images), now=now)
        output_filepath = os.path.join(Settings.paths['image_save_location'], output_filename)

        args = self.FFMPEG_SCREENSHOT_ARGS.format(
            ffmpeg_bin_location=Settings.paths['ffmpeg_bin_path'],
            timestamp=timestamp,
            video_filepath=video_file,
            param_DAR=self.param_DAR,
            output_filepath=output_filepath
        )
        process = subprocess.Popen(args, shell=True)

        return output_filepath, process

    def _create_compressed_images(self) -> list:
        """
        Create compressed images from the PNG files generated.
        :return compressed_images (list<str>): List of paths of the resulting compressed image files
        """
        compressed_images = []
        for image_path in self.saved_images:
            image_path_no_ext = os.path.splitext(image_path)[0]
            compressed_image_path = image_path_no_ext + '.jpg'

            compressed_image = Image.open(image_path)
            compressed_image.save(compressed_image_path, optimize=True, quality=15)

            compressed_images.append(compressed_image_path)
        return compressed_images

    def _optimise_images(self) -> None:
        print("Optimizing images!")
        processes = []
        for img in self.saved_images:
            proc = subprocess.Popen(self.OXIPNG_ARGS.format(
                oxi_bin_location = Settings.paths['optimise_bin_path'],
                images = f'"{img}"'
            ), shell=True)

            processes.append(proc)

        for proc in processes:
            proc.wait()


    def _discard_smallest_images(self, compressed_images: list) -> list:
        """
        Discard out the lowest-detailed images; the lowest-detailed images carry a
        distinctively lower file size when compressed (eg. dark frames; black transition frames)
        :param compressed_images (list<str>): List of paths of the compressed image files
        :return list<str>: List of uncompressed image file paths
        """
        compressed_images.sort(reverse=True, key=lambda x: os.path.getsize(x))
        final_images = []

        for i, image_path in enumerate(compressed_images):
            uncompressed_image_path = os.path.splitext(image_path)[0] + '.png'
            os.unlink(image_path)
            if i >= self.n_final_images:
                os.unlink(uncompressed_image_path)
                continue

            final_images.append(uncompressed_image_path)
        return final_images

    @staticmethod
    def _get_display_dimensions(rls: object) -> Tuple[int, int]:
        """
        Gets proper display dimensions of video, in distinction to the pixel dimensions; pixels may not always be square
        :param rls (ReleaseInfo): Object containing video's/DVD's paths and any already-gathered mediainfo
        :return tuple<int>: Video dimensions: width, height
        """
        if rls.release_type == 'dvd':
            mediainfo_json = rls.primary_ifo_info['mediainfo_json']
        else:
            mediainfo_json = Helper.get_mediainfo_json(rls.main_video_files[0])

        video_info = Helper.get_track(mediainfo_json, track_type='Video')

        pixel_width = display_width = int(video_info['Width'])
        pixel_height = display_height = int(video_info['Height'])
        if float(video_info['PixelAspectRatio']) == 1:
            return pixel_width, pixel_height

        dar_float = float(video_info['DisplayAspectRatio'])
        temp_display_width = int(pixel_height * dar_float)
        if temp_display_width >= pixel_width:
            display_width = temp_display_width
        else:
            display_height = int(pixel_width / dar_float)

        return display_width, display_height
