import json
import os
import subprocess

CLEAR_FN = 'cls' if os.name == 'nt' else 'clear'
IMAGE_HOSTS_SKELETON = [
    {
        'name': 'ptpimg',
        'api_key': '',
        'default': False
    },
    {
        'name': 'imgbb',
        'api_key': '',
        'default': False
    },
    {
        'name': 'hdbimg',
        'username': '',
        'api_key': '',
        'default': False
    },
    {
        'name': 'ahdimg',
        'api_key': '',
        'default': False
    }
]


class Settings:
    settings_file_name = 'ReleaseInfoCreator.json'
    settings_file_path = os.path.join( os.path.dirname(os.path.abspath(__file__)), settings_file_name )

    new_settings_message = 'A new settings value has been created in this version of the script. ' \
                           'You will now be asked for your preference.'

    # upon adding a new setting, update _get_settings_dict(), _append_missing_settings(),
    # and load_settings() right below
    paths = {}
    image_hosts = IMAGE_HOSTS_SKELETON
    print_not_copy = False
    use_bbcode_tags = False

    @classmethod
    def load_settings(cls):
        """
        Reads .json file ReleaseInfoCreator.json for settings
        Updates Settings class attributes with the json file's attributes
        :return:
        """
        try:
            with open(cls.settings_file_path, 'r', encoding='utf8') as f:
                settings_from_file = json.load(f)

            cls.paths = settings_from_file['paths']
            cls.image_hosts = settings_from_file['image_hosts']
            cls.print_not_copy = settings_from_file.get('print_not_copy')
            cls.use_bbcode_tags = settings_from_file.get('use_bbcode_tags')

            cls._append_missing_settings(settings_from_file)
            cls._expand_paths()
        except FileNotFoundError:
            print(f'\nExisting settings file not found, a new one will be created '
                  f'and saved as {cls.settings_file_name}')
            cls._query_new_settings()
        except json.decoder.JSONDecodeError:
            print(f'Error reading from {cls.settings_file_path} (bad formatting?). Querying for new settings...')
            cls._query_new_settings()

        cls.assert_paths()

    @classmethod
    def assert_paths(cls):
        """
        Assert that paths in json settings file exist
        :return:
        """
        assert os.path.isdir(cls.paths['image_save_location']), \
            'Image save directory does not exist: {}'.format(cls.paths['image_save_location'])
        assert os.path.isfile(cls.paths['ffmpeg_bin_path']), \
            'FFmpeg file does not exist: {}'.format(cls.paths['ffmpeg_bin_path'])
        assert os.path.isfile(cls.paths['mediainfo_bin_path']), \
            'Mediainfo file does not exist: {}'.format(cls.paths['mediainfo_bin_path'])

    @classmethod
    def _query_new_settings(cls):
        """
        Get user input for new settings upon first run
        :return:
        """
        retry = True

        while retry:
            cls._query_image_host_info()
            cls._query_path_info()
            cls._query_print_not_copy()
            cls._query_bbcode_tags()

            subprocess.run(CLEAR_FN, shell=True)
            print('\nYour Settings:\n' + json.dumps(cls._get_settings_dict(), indent=4) + '\n')

            retry = False if input('Use these settings [Y/n]?').lower().strip() == 'y' else True
            subprocess.run(CLEAR_FN, shell=True)

        with open(cls.settings_file_path, 'w', encoding='utf8') as f:
            json.dump(cls._get_settings_dict(), f, indent=4)

    @classmethod
    def _expand_paths(cls):
        """
        Resolve tilde `~` and Windows `%path%` expansions
        :return:
        """
        for path_name in cls.paths:
            cls.paths[path_name] = os.path.expanduser(cls.paths[path_name])

    @classmethod
    def _query_image_host_info(cls):
        """
        Get user input for image host information: api key, username (if applicable), and default setting
        :return:
        """
        cls.image_hosts = IMAGE_HOSTS_SKELETON
        # to keep track of user has set a default host
        is_exist_default = False

        for i, _ in enumerate(IMAGE_HOSTS_SKELETON):
            host_name = cls.image_hosts[i]['name']
            cls.image_hosts[i]['api_key'] = input(f'\nInput the API key for {host_name} (to skip, leave blank): ').strip()

            if host_name == 'hdbimg':
                cls.image_hosts[i]['username'] = input(f'Input your username for {host_name} (to skip, leave blank): ')

            # Query for default if api key is is given a value
            if cls.image_hosts[i]['api_key'] and not is_exist_default:
                cls.image_hosts[i]['default'] = True if input(
                    f'Set {host_name} as the default [Y/n]? ').lower().strip() == 'y' else False
                if cls.image_hosts[i]['default']:
                    is_exist_default = True

    @classmethod
    def _query_path_info(cls):
        cls.paths['image_save_location'] = input('\nInput the image save directory: ').strip()
        cls.paths['ffmpeg_bin_path'] = input('Input the full path for the ffmpeg binary: ').strip()
        cls.paths['mediainfo_bin_path'] = input('Input the full path for the mediainfo binary: ').strip()

    @classmethod
    def _query_print_not_copy(cls):
        cls.print_not_copy = True if \
            input('\nPrint mediainfo + image URLs to console instead of copying '
                  'to clipboard [Y/n]? ').lower().strip() == 'y' else False
    @classmethod
    def _query_bbcode_tags(cls):
        cls.use_bbcode_tags = True if \
            input('\nUse [img][/img] bbcode tags for '
                  'image urls [Y/n]? ').lower().strip() == 'y' else False

    @classmethod
    def _get_settings_dict(cls) -> dict:
        return {
            'paths': cls.paths,
            'image_hosts': cls.image_hosts,
            'print_not_copy': cls.print_not_copy,
            'use_bbcode_tags': cls.use_bbcode_tags
        }

    @classmethod
    def get_preferred_host(cls) -> int:
        """
        Get user input for preferred host to upload with
        :return int: index of image host in list
        """
        default_host_index = cls._get_default_host()
        # If image host has 'default' flag set, skip query and use that
        if default_host_index != -1:
            return default_host_index

        bad_choice_msg = ''
        max_num = len(cls.image_hosts)

        while True:
            print(f'\n{bad_choice_msg}Choose an image host to use: \n')

            for i, image_host in enumerate(cls.image_hosts):
                host_name = image_host['name']

                # will be printed in the console-printed options menu to indicate if the image host key is not set
                set_str = '    (not set)' if image_host['api_key'].strip() == '' else ''
                print(f'  {i + 1}: {host_name}{set_str}')

            choice = input(f'\nYour choice (between {1} and {max_num}): ')
            if not choice.isnumeric() or not ( int(choice) >= 1 and int(choice) <= max_num ):
                bad_choice_msg = 'Bad choice. Try again.\n'
                subprocess.run(CLEAR_FN, shell=True)
                continue
            elif cls.image_hosts[ int(choice) - 1 ]['api_key'].strip() == '':
                bad_choice_msg = f'Your chosen image host ({choice}) has not been set.\n'
                subprocess.run(CLEAR_FN, shell=True)
                continue
            else:
                return int(choice) - 1

    @classmethod
    def _get_default_host(cls) -> int:
        """
        Find image host that has the `default` value set to True
        :return int: index of image host in list
        """
        for i, image_host in enumerate(cls.image_hosts):
            if image_host['default']:
                return i
        return -1

    # append keys and values to json file if it is missing them (if new settings were added since a
    # previous iteration of this script)
    @classmethod
    def _append_missing_settings(cls, settings_from_file: dict):
        """
        Checks IMAGE_HOSTS_SKELETON for any new keys or image hosts; gets user input for those new settings
        Updates class attributes with those new settings and saves them back into ReleaseInfoCreator.json
        :param settings_from_file (dict): settings read from ReleaseInfoCreator.json
        :return:
        """
        is_missing_settings = False

        # append new image hosts
        if len(cls.image_hosts) != len(IMAGE_HOSTS_SKELETON):
            is_missing_settings = True
            image_host_names_from_file = [d['name'] for d in cls.image_hosts]

            for image_host in IMAGE_HOSTS_SKELETON:
                if image_host['name'] not in image_host_names_from_file:
                    cls.image_hosts.append(image_host)

        if settings_from_file.get('print_not_copy') is None:
            print(cls.new_settings_message)
            is_missing_settings = True
            cls._query_print_not_copy()

        if settings_from_file.get('use_bbcode_tags') is None:
            print(cls.new_settings_message)
            is_missing_settings = True
            cls._query_bbcode_tags()

        if is_missing_settings:
            with open(cls.settings_file_path, 'w', encoding='utf8') as f:
                json.dump(cls._get_settings_dict(), f, indent=4)

    @staticmethod
    def query_options():
        pass
