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
    # basic bbcode tagging for the image hosts that don't provide thumbnails
    bbcoded_img_url_template = Template('[img]$direct_url[/img]')
    thumbnailed_bbcoded_img_url_template = Template('[url=$direct_url][img]$thumb_url[/img][/url]')

    def __init__(self, image_files: list, gallery_name: str, image_host):
        self.image_host = image_host
        self.image_files = image_files
        self.formatted_urls = ''
        self.gallery_name = gallery_name

    def get_formatted_urls(self) -> str:
        """
        Gets image urls for the already-uploaded images
        :return str: formatted string containing image URLs
        """
        return self.formatted_urls

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
        form_data = dict(key=self.image_host['api_key'])

        for i, image in enumerate(self.image_files):
            now = datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S')
            with open(image, 'rb') as f:
                form_data['image'] = base64.b64encode(f.read())
                form_data['name'] = f'{i}_snapshot {now}'

                resp = requests.post(url=ENDPOINT_IMGBB, data=form_data)

            assert resp.ok, f'IMGBB returned status code {resp.status_code}'
            resp_json = resp.json()
            direct_url = resp_json['data']['image']['url']
            thumb_url = resp_json['data']['medium']['url']

            if Settings.use_bbcode_tags:
                bbcoded_image_url = self.thumbnailed_bbcoded_img_url_template.safe_substitute(
                    direct_url=direct_url,
                    thumb_url=thumb_url
                )
                self.formatted_urls += bbcoded_image_url + '\n'
            else:
                self.formatted_urls += direct_url + '\n'

    def _upload_ptpimg(self):
        form_data = dict(api_key=self.image_host['api_key'])
        files = {}

        file_descriptors = []
        image_urls = []
        totalsize = 0        
        for img in self.image_files:
            size = os.path.getsize(img)
            # PTPIMG uses CloudFlare which has a 100mb upload limit, so we split into batches <100mb
            # This limit can be hit with 4k files
            if totalsize + size > 100000000:
                # ptpimg does not retain filenames
                print(f'Uploading {len(files)} images totaling {round(totalsize /1000000, 2)}mb')
                resp = requests.post(url=ENDPOINT_PTPIMG, files=files, data=form_data)
                assert resp.ok, f'PTPIMG returned status code {resp.status_code}'

                resp_json = resp.json()
                image_urls = image_urls + ['https://ptpimg.me/{}.png'.format(img['code']) for img in resp_json]
                files = {}
                totalsize = 0

            fd = open(img, 'rb')
            file_descriptors.append(fd)
            files[ f'file-upload[{len(files)}]' ] = ('potatoes_boilem_mashem_ptpimg_dont_care', fd)
            totalsize += size

        if len(files) > 0:
            # ptpimg does not retain filenames
            print(f'Uploading {len(files)} images totaling {round(totalsize / 1000/1000, 2)}mb')
            resp = requests.post(url=ENDPOINT_PTPIMG, files=files, data=form_data)
            assert resp.ok, f'PTPIMG returned status code {resp.status_code}'

            resp_json = resp.json()
            image_urls = image_urls + ['https://ptpimg.me/{}.png'.format(img['code']) for img in resp_json]
            files = {}

        for direct_url in image_urls:
            if Settings.use_bbcode_tags:
                bbcoded_image_url = self.bbcoded_img_url_template.safe_substitute(
                    direct_url=direct_url
                )
                self.formatted_urls += bbcoded_image_url + '\n'
            else:
                self.formatted_urls += direct_url + '\n'
        [fd.close() for fd in file_descriptors]

    def _upload_hdbimg(self):
        # galleryoption == '0' indicates no new gallery will be created
        # galleryoption == '0' is not honored; new gallery is created regardless
        # galleryoption == '1' indicates new gallery will be created
        form_data = dict(
            username=self.image_host['username'],
            passkey=self.image_host['api_key'],
            galleryoption='1',
            galleryname=self.gallery_name
        )
        files = {}

        file_descriptors = [open(img, 'rb') for img in self.image_files]
        for i, fd in enumerate(file_descriptors):
            files[f'images_files[{i}]'] = (os.path.basename(self.image_files[i]), fd)

        resp = requests.post(url=ENDPOINT_HDBIMG, files=files, data=form_data)
        assert resp.ok, f'HDBIMG returned status code {resp.status_code}'

        # image urls come pre-formatted for use within hdbits
        self.formatted_urls = resp.text
        [fd.close() for fd in file_descriptors]
