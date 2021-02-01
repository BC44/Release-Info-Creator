#!python3

import os
import pyperclip
import subprocess
import sys
import time

import Helper
from Settings import Settings
from ReleaseInfo import ReleaseInfo
from DvdAnalyzer import DvdAnalyzer
from ScreenshotGenerator import ScreenshotGenerator
from ImageUploader import ImageUploader

CLEAR_FN = 'cls' if os.name == 'nt' else 'clear'


def main():
    if len(sys.argv) == 1:
        Settings.query_options()
        exit()
    Settings.load_settings()
    Settings.assert_paths()
    image_host_id = Settings.get_preferred_host()
    image_host_name = Settings.image_hosts[image_host_id]['name']

    assert len(sys.argv) > 1, 'Error, need input file'

    subprocess.run(CLEAR_FN, shell=True)

    print( 'Image host "{}" will be used for uploading\n'.format(image_host_name) )
    print('Gathering media info')
    rls = ReleaseInfo( os.path.abspath(sys.argv[1]) )
    release_info = rls.get_complete_mediainfo()

    print('Generating screenshots')
    screenshot_gen = ScreenshotGenerator(n_images=6)
    images = screenshot_gen.generate_screenshots(rls)

    print( 'Uploading images to {}'.format(image_host_name) )
    gallery_name = Helper.get_gallery_name(sys.argv[1])
    uploader = ImageUploader(images, gallery_name, image_host_id=image_host_id)
    uploader.upload()
    image_urls = uploader.get_image_urls()

    pyperclip.copy(release_info + image_urls)
    print('\nMediainfo + image URLs have been copied to clipboard')
    time.sleep(5)


if __name__ == '__main__':
    main()
