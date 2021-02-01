import os


def get_largest_file(files):
    largest_filepath = files[0]
    largest_filesize = os.path.getsize(files[0])

    for file in files:
        filesize = os.path.getsize(file)
        if filesize > largest_filesize:
            largest_filepath = file
            largest_filesize = filesize

    return largest_filepath


def get_gallery_name(input_path):
    from guessit import guessit

    guessed_data = guessit(input_path)
    gallery_name = guessed_data['title']
    if guessed_data.get('year', None) is not None:
        gallery_name += ' ({year})'.format(year=guessed_data['year'])

    if guessed_data.get('screen_size', None) is not None:
        gallery_name += ' - {res}'.format(res=guessed_data['screen_size'])

    return gallery_name
