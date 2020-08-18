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

MEDIAINFO_COMPLETE_NAME_RE = r'(Complete name.+?:).+'

def main():
	videoFile = sys.argv[1]
	IFO_mediainfo = ''
	main_mediainfo = '[mediainfo]\n' + getMediaInfo(videoFile) + '[/mediainfo]'

	if videoFile.endswith(('.vob', '.VOB')):
		IFO_file = getIFOfile(videoFile)
		IFO_mediainfo = '[mediainfo]\n' + getMediaInfo(IFO_file) + '[/mediainfo]'

	images = generateScreenshots(videoFile, 6)
	imageURLs = uploadImages(images)

	pyperclip.copy(main_mediainfo + '\n\n' + IFO_mediainfo + '\n\n' + imageURLs)


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


def generateScreenshots(videoFilepath, n):
	savedImages = []
	timeStamp = 45
	increaseBy = 30

	for i in range(0, n + 2):
		now = datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S')
		outputFile = f'snapshot_{i} {now}'
		outputFilePath = os.path.join(IMAGE_SAVE_LOCATION, outputFile)

		subprocess.call(fr'ffmpeg -hide_banner -loglevel panic -ss {timeStamp} -i "{videoFilepath}" -vf "select=gt(scene\,0.01)" -r 1 -frames:v 1 "{outputFilePath}.png"', shell=True)

		# input(outputFile)

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

		url_main = returned_data['data']['url']
		# url_thumb = returned_data['data']['medium']['url']
		# str_temp = f'[url={url_main}][img=320]{url_thumb}[/img][/url]'
		imageURLs += url_main + '\n'

	return imageURLs



if __name__ == '__main__':
	main()
