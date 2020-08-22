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
PTPIMG_KEY = ''

ENDPOINT_IMGBB = 'https://api.imgbb.com/1/upload'
ENDPOINT_PTPIMG = 'http://ptpimg.me/upload.php'

MEDIAINFO_COMPLETE_NAME_RE = r'(Complete name *:).+'

DAR_RE = r'Display aspect ratio *: (\d+(?:\.\d+)?):(\d+)'
HEIGHT_RE = r'Height *: (\d+) pixels'
WIDTH_RE = r'Width *: (\d+) pixels'


def main():
	videoFile = sys.argv[1]
	IFO_mediainfo = ''
	main_mediainfo = '[mediainfo]\n' + getMediaInfo(videoFile).strip() + '\n[/mediainfo]\n\n'
	param_DAR = ''

	if videoFile.endswith(('.vob', '.VOB')):
		IFO_file = getIFOfile(videoFile)
		IFO_mediainfo = '[mediainfo]\n' + getMediaInfo(IFO_file).strip() + '\n[/mediainfo]\n\n'

		parentPath = os.path.dirname(videoFile)
		if parentPath.endswith(('VIDEO_TS', 'video_ts')):
			DVD_Name = os.path.dirname(parentPath)
			DVD_Name = os.path.basename(DVD_Name)
			IFO_mediainfo = f'[size=4][b]{DVD_Name}[/b][/size]\n\n' + IFO_mediainfo

		DAR = getDAR(IFO_mediainfo)
		param_DAR = f'-vf "scale={DAR}"'

	images = generateScreenshots(videoFile, n=6, param_DAR=param_DAR)
	imageURLs = upload_PTPIMG(images)

	pyperclip.copy(IFO_mediainfo + main_mediainfo + imageURLs)
	print('Mediainfo + image URLs pasted to clipboard.')


def getDAR(mediainfo):
	m = re.search(DAR_RE, mediainfo)
	aspect_width = float(m.group(1))
	aspect_height = float(m.group(2))

	pixel_height = re.search(HEIGHT_RE, mediainfo).group(1)
	pixel_height = int(pixel_height)
	pixel_width = re.search(WIDTH_RE, mediainfo).group(1)
	pixel_width = int(pixel_width)

	temp_pixel_width = pixel_height/aspect_height * aspect_width
	temp_pixel_width = int(pixel_width)

	if temp_pixel_width >= pixel_width:
		pixel_width = temp_pixel_width
	else:
		pixel_height = pixel_width/aspect_width * aspect_height
		pixel_height = int(pixel_height)

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
	timestamps = getTimestamps(videoFilepath, n + 2)

	for i, timestamp in enumerate(timestamps):
		now = datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S')
		outputFile = f'snapshot_{i} {now}'
		outputFilePath = os.path.join(IMAGE_SAVE_LOCATION, outputFile)

		subprocess.call(fr'ffmpeg -hide_banner -loglevel panic -ss {timestamp} -i "{videoFilepath}" -vf "select=gt(scene\,0.01)" {param_DAR} -r 1 -frames:v 1 "{outputFilePath}.png"', shell=True)

		picture = Image.open(f'{outputFilePath}.png')
		picture.save(f'{outputFilePath}.jpg',optimize=True,quality=15)

		compressedSize = os.path.getsize(f'{outputFilePath}.jpg')
		savedImages.append({'path': outputFilePath, 'size': compressedSize})

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


def upload_IMGBB(images):
	imageURLs = ''

	for i, image in enumerate(images):
		now = datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S')
		with open(image, 'rb') as f:
			formdata = {
				'key': IMGBB_KEY, 
				'image': base64.b64encode(f.read()),
				'name': f'{i}_snapshot {now}'
			}

			resp = requests.post(url=ENDPOINT_IMGBB, data=formdata)

		resp = json.loads(resp.text)
		if resp.get('status_code', None) is not None:
			print('POST request error ', resp['status_code'], ', ', resp['status_txt'], ', ', resp['error']['message'])
			exit()

		direct_URL = resp['data']['url']
		imageURLs += direct_URL + '\n'

	return imageURLs


def upload_PTPIMG(images):
	imageURLs = ''

	for i, image in enumerate(images):
		now = datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S')
		imageBasename = os.path.basename(image)
		with open(image, 'rb') as f:
			formdata = {'api_key': PTPIMG_KEY}
			files = {('file-upload[0]', (imageBasename, f, 'image/png'))}

			resp = requests.post(url=ENDPOINT_PTPIMG, files=files, data=formdata)
			resp = json.loads(resp.text)

			imageID = resp[0]['code']
			direct_URL = f'https://ptpimg.me/{imageID}.png'
			imageURLs += direct_URL + '\n'

	return imageURLs



def getTimestamps(videoFilepath, n):
	timestamps = []
	mediainfo_json = subprocess.check_output(f'mediainfo --Output=JSON "{videoFilepath}"', shell=True).decode()
	mediainfo_json = json.loads(mediainfo_json)
	totalRuntimeSecs = float(mediainfo_json['media']['track'][0]['Duration'])

	# initial timestamp set to 5% of total runtime
	minTimestampSecs = int(totalRuntimeSecs * 0.05)
	# max timestamp set to 60% of total runtime
	maxTimestampSecs = totalRuntimeSecs * 0.6

	increaseIntervalSecs = (maxTimestampSecs - minTimestampSecs) / n
	increaseIntervalSecs = int(increaseIntervalSecs)

	for i in range(0, n):
		nextTimestamp = minTimestampSecs + i*increaseIntervalSecs
		timestamps.append(nextTimestamp)

	return timestamps


if __name__ == '__main__':
	main()
