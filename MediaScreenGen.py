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

IMAGE_SAVE_LOCATION = r''
IMGBB_KEY = ''

MEDIAINFO_COMPLETE_NAME_RE = r'(Complete name *:).+'

DAR_RE = r'Display aspect ratio *: (\d+(?:\.\d+)?):(\d+)'
HEIGHT_RE = r'Height *: (\d+) pixels'


def main():
	videoFile = sys.argv[1]
	IFO_mediainfo = ''
	main_mediainfo = '[mediainfo]\n' + getMediaInfo(videoFile) + '[/mediainfo]'
	param_DAR = ''

	if videoFile.endswith(('.vob', '.VOB')):
		IFO_file = getIFOfile(videoFile)
		IFO_mediainfo = '[mediainfo]\n' + getMediaInfo(IFO_file) + '[/mediainfo]'

		DAR = getDAR(IFO_mediainfo)
		param_DAR = f'-vf "scale={DAR}"'

	images = generateScreenshots(videoFile, n=6, param_DAR=param_DAR)
	imageURLs = uploadImages(images)

	pyperclip.copy(main_mediainfo + '\n\n' + IFO_mediainfo + '\n' + imageURLs)

	print('Mediainfo + image URLs pasted to clipboard.\n')


def getDAR(mediainfo):
	m = re.search(DAR_RE, mediainfo)
	aspect_width = float(m.group(1))
	aspect_height = float(m.group(2))

	pixel_height = re.search(HEIGHT_RE, mediainfo).group(1)
	pixel_height = int(pixel_height)

	pixel_width = pixel_height/aspect_height * aspect_width
	pixel_width = int(pixel_width)

	return f'{pixel_width}:{pixel_height}'


def getIFOfile(videoFile):
	basefolder = os.path.dirname(videoFile)
	IFO_files = [os.path.join(basefolder, f) for f in os.listdir(basefolder) if f.endswith(('.ifo', '.IFO'))]

	largestIFO = IFO_files[0]
	largestSize = os.path.getsize(largestIFO)

	for ifo in IFO_files:
		filesize = os.path.getsize(ifo)
		if filesize > largestSize:
			largestIFO = ifo
			largestSize = filesize
	return largestIFO


def getMediaInfo(primaryVideoFilepath):
	baseVideoName = os.path.basename(primaryVideoFilepath)
	mediainfo = subprocess.check_output(f'mediainfo "{primaryVideoFilepath}"', shell=True).decode()
	mediainfo = re.sub(MEDIAINFO_COMPLETE_NAME_RE, fr'\1 {baseVideoName}', mediainfo)
	mediainfo = re.sub(r'\r\n', '\n', mediainfo)
	return mediainfo


def generateScreenshots(videoFilepath, n=6, param_DAR=''):
	savedImages = []
	timeStamp = 45
	increaseBy = 30

	for i in range(0, n + 2):
		now = datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S')
		outputFile = f'snapshot_{i} {now}'
		outputFilePath = os.path.join(IMAGE_SAVE_LOCATION, outputFile)

		subprocess.call(fr'ffmpeg -hide_banner -loglevel panic -ss {timeStamp} -i "{videoFilepath}" -vf "select=gt(scene\,0.01)" {param_DAR} -r 1 -frames:v 1 "{outputFilePath}.png"', shell=True)

		picture = Image.open(f'{outputFilePath}.png')
		picture.save(f'{outputFilePath}.jpg',optimize=True,quality=15)

		compressedSize = os.path.getsize(f'{outputFilePath}.jpg')
		savedImages.append({'path': outputFilePath, 'size': compressedSize})

		timeStamp += increaseBy

	return keep_n_largest(savedImages, n)


def keep_n_largest(savedImages, n):
	for i, _ in enumerate(savedImages):
		for k in range(i + 1, len(savedImages)):
			if savedImages[i]['size'] < savedImages[k]['size']:
				savedImages[k], savedImages[i] = savedImages[i], savedImages[k]

	for i, file in enumerate(savedImages):
		os.unlink(file['path'] + '.jpg')
		if i >= n:
			os.unlink(file['path'] + '.png')

	return [f['path'] + '.png' for f in savedImages[0:n]]


def uploadImages(images):
	imageURLs = ''
	endpoint_imgbb = 'https://api.imgbb.com/1/upload'

	for i, image in enumerate(images):
		now = datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S')
		with open(image, 'rb') as f:
			formdata_imgbb = {
			'key': IMGBB_KEY, 
			'image': base64.b64encode(f.read()),
			'name': f'{i}_Snapshot {now}'
			}

			r = requests.post(url=endpoint_imgbb, data=formdata_imgbb)
		returned_data = json.loads(r.text)
		if returned_data.get('status_code', None) is not None:
			print('POST request error ', returned_data['status_code'], ', ', returned_data['status_txt'], ', ', returned_data['error']['message'])
			exit()

		url_main = returned_data['data']['url']
		# url_thumb = returned_data['data']['medium']['url']
		# str_temp = f'[url={url_main}][img=320]{url_thumb}[/img][/url]'
		imageURLs += url_main + '\n'

	return imageURLs



if __name__ == '__main__':
	main()
