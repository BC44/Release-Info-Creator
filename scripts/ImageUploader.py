import base64
import datetime
import requests
import os

from string import Template
from Settings import Settings

ENDPOINT_PTPIMG = 'https://ptpimg.me/upload.php'
ENDPOINT_IMGBB = 'https://api.imgbb.com/1/upload'
ENDPOINT_HDBIMG = 'https://img.hdbits.org/upload_api.php'
ENDPOINT_AHDIMG = 'https://img.awesome-hd.me/api/upload'


class ImageUploader:
    img_url_template = Template('[url=$direct_url][img]$thumb_url[/img][/url]')
    # basic tagging for the image hosts that don't provide thumb urls
    basic_img_url_template = Template('[img]$direct_url[/img]')

    def __init__(self, images, gallery_name, image_host_id=-1):
        assert image_host_id != -1, 'Error: No image host has been chosen'

        self.image_host = Settings.image_hosts[image_host_id]
        self.images = images
        self.image_urls = ''

    def get_image_urls(self):
        return self.image_urls

    def upload(self):
        if self.image_host['name'] == 'ptpimg':
            self._upload_ptpimg()
        elif self.image_host['name'] == 'imgbb':
            self._upload_imgbb()
        elif self.image_host['name'] == 'hdbimg':
            self._upload_hdbimg()
        elif self.image_host['name'] == 'ahdimg':
            print('Error: ahdimg is not yet implemented on this script. Site currently down for testing.')
            exit()

    def _upload_imgbb(self):
        for i, image in enumerate(self.images):
            now = datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S')
            with open(image, 'rb') as f:
                formdata = {
                    'key': self.image_host['api_key'],
                    'image': base64.b64encode(f.read()),
                    'name': f'{i}_snapshot {now}'
                }
                resp = requests.post(url=ENDPOINT_IMGBB, data=formdata)

            assert resp.ok, f'IMGBB returned status code {resp.status_code}'
            resp_json = resp.json()
            direct_url = resp_json['data']['image']['url']
            thumb_url = resp_json['data']['medium']['url']

            if Settings.use_bbcode_tags:
                self.image_urls += self.img_url_template.safe_substitute(
                    direct_url=direct_url,
                    thumb_url=thumb_url
                ) + '\n'
            else:
                self.image_urls += direct_url + '\n'

    def _upload_ptpimg(self):
        data = {'api_key': self.image_host['api_key']}
        files = {}

        file_descriptors = [open(img, 'rb') for img in self.images]
        for i, fd in enumerate(file_descriptors):
            # ptpimg does not retain filenames
            files[ f'file-upload[{i}]' ] = ('potatoes_boilem_mashem_ptpimg_dont_care', fd)

        resp = requests.post(url=ENDPOINT_PTPIMG, files=files, data=data)
        assert resp.ok, f'PTPIMG returned status code {resp.status_code}'
        resp_json = resp.json()

        image_urls = ['https://ptpimg.me/{}.png'.format(img['code']) for img in resp_json]

        for direct_url in image_urls:
            if Settings.use_bbcode_tags:
                self.image_urls += self.basic_img_url_template.safe_substitute(
                    direct_url=direct_url
                ) + '\n'
            else:
                self.image_urls += direct_url + '\n'
        [fd.close() for fd in file_descriptors]

    def _upload_hdbimg(self):
        # galleryoption == '0' indicates no new gallery will be created
        # galleryoption == '1' indicates new gallery will be created
        data = {
            'username': self.image_host['username'],
            'passkey': self.image_host['api_key'],
            'galleryoption': '1',
            'galleryname': gallery_name
        }
        files = {}

        file_descriptors = [open(img, 'rb') for img in self.images]
        for i, fd in enumerate(file_descriptors):
            files[f'images_files[{i}]'] = (os.path.basename(self.images[i]), fd)

        resp = requests.post(url=ENDPOINT_HDBIMG, files=files, data=data)
        assert resp.ok, f'HDBIMG returned status code {resp.status_code}'

        # image urls come pre-formatted for use within hdbits
        self.image_urls = resp.text
        [fd.close() for fd in file_descriptors]
