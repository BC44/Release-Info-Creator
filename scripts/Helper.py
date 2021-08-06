import os


def get_largest_file(files: list) -> str:
    """
    Determines the largest file from a list of paths
    :param files (list<str>): file paths
    :return str:
    """
    largest_filepath = files[0]
    largest_filesize = os.path.getsize(files[0])

    for file in files:
        filesize = os.path.getsize(file)
        if filesize > largest_filesize:
            largest_filepath = file
            largest_filesize = filesize

    return largest_filepath


def get_gallery_name(input_path: str) -> str:
    """
    Determines movie name based on the filename, as well as year if applicable
    :param input_path (str): file path of video file
    :return (str): Name to use for gallery (for video hosts that have the option of creating a gallery)
    """
    from guessit import guessit

    guessed_data = guessit(input_path)
    gallery_name = guessed_data['title']
    if guessed_data.get('year') is not None:
        gallery_name += ' ({year})'.format(year=guessed_data['year'])

    if guessed_data.get('screen_size') is not None:
        gallery_name += ' - {res}'.format(res=guessed_data['screen_size'])

    return gallery_name
